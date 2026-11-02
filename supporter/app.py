import json
import queue
import threading
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from .backends import DEFAULT, ROOT, discover, generate, prompt_for, sanitize, stop
from . import windows

COMMANDS = {
    '/help': '显示命令和键盘操作',
    '/backend': '选择 CLI 后端（方向键选择，回车确认）',
    '/model': '选择当前 CLI 的模型（输入文字筛选）',
    '/terminal': '切换终端模式；接受时转成单行且不回车',
    '/refresh': '重新检测已安装 CLI 和模型列表',
    '/clear': '清除候选和本轮修改历史',
    '/cancel': '取消生成、关闭浮层并恢复原窗口',
    '/quit': '退出 Supporter 常驻进程',
}

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Supporter')
        self.root.withdraw()
        self.root.attributes('-topmost', True)
        self.root.protocol('WM_DELETE_WINDOW', self.hide)
        self.events = queue.Queue()
        self.ready = queue.Queue()
        self.cancel = threading.Event()
        self.job = 0
        self.busy = False
        self.process = None
        self.backends = []
        self.target = None
        self.candidate = ''
        self.previous = ''
        self.picker = None
        self.choices = []
        self.settings_file = ROOT/'settings.json'
        try:
            self.settings = json.loads(self.settings_file.read_text(encoding='utf-8'))
        except (OSError,ValueError):
            self.settings = {}
        self.backend = tk.StringVar(value=self.settings.get('backend','codex'))
        self.model = tk.StringVar(value=DEFAULT)
        self.terminal = tk.BooleanVar(value=False)
        body = ttk.Frame(self.root, padding=16)
        body.pack(fill='both',expand=True)
        self.heading = ttk.Label(body,text='Supporter · 正在检测 CLI',font=('Microsoft YaHei UI',12,'bold'))
        self.heading.pack(anchor='w')
        self.status = ttk.Label(body,text='Ctrl+Space 唤起 · 输入 / 查看命令',wraplength=610)
        self.status.pack(anchor='w',pady=(6,10))
        self.entry = tk.Text(body,height=3,font=('Microsoft YaHei UI',11),wrap='word',undo=True)
        self.entry.pack(fill='x')
        self.listbox = tk.Listbox(body,height=6,font=('Microsoft YaHei UI',10),exportselection=False)
        self.listbox.bind('<Return>',self.choose)
        self.listbox.bind('<Tab>',self.complete)
        self.entry.bind('<KeyRelease>',self.changed)
        self.entry.bind('<Return>',self.enter)
        self.entry.bind('<Shift-Return>',lambda e: None)
        self.entry.bind('<Tab>',self.tab)
        self.entry.bind('<Down>',lambda e:self.move(1))
        self.entry.bind('<Up>',lambda e:self.move(-1))
        self.preview = tk.Text(body,height=10,font=('Consolas',11),wrap='word',state='disabled',foreground='#606b78')
        self.preview.pack(fill='both',expand=True,pady=(10,8))
        ttk.Label(body,text='Enter 生成/修改 · Tab 接受/补全 · Esc 取消\nCtrl+B 后端 · Ctrl+M 模型 · Ctrl+T 终端 · F5 检测 · Ctrl+Q 退出').pack(anchor='w')
        for key,fn in [('<Escape>',self.escape),('<Control-Return>',self.accept),
                       ('<Control-b>',lambda e:self.open_picker('backend')),
                       ('<Control-m>',lambda e:self.open_picker('model')),
                       ('<Control-t>',self.toggle_terminal),('<F5>',self.refresh),
                       ('<Control-q>',self.quit)]:
            self.root.bind(key,fn)
        threading.Thread(target=windows.hotkeys,args=(self.events,self.ready),daemon=True).start()
        self.root.after(50,self.poll)
        self.refresh()

    def text(self):
        return self.entry.get('1.0','end-1c').strip()

    def set_entry(self,text=''):
        self.entry.delete('1.0','end')
        self.entry.insert('1.0',text)

    def update_heading(self):
        self.heading.config(text=f'Supporter · {self.backend.get()} · {self.model.get()} · {"终端" if self.terminal.get() else "文本"}')

    def refresh(self,event=None):
        if self.busy:
            return 'break'
        self.status.config(text='正在检测 CLI 和模型…')
        threading.Thread(target=lambda:self.events.put(('discovered',discover())),daemon=True).start()
        return 'break'

    def poll(self):
        try:
            err = self.ready.get_nowait()
            if err:
                self.root.deiconify()
                self.status.config(text=err)
        except queue.Empty:
            pass
        try:
            while True:
                kind,value = self.events.get_nowait()
                if kind == 'wake':
                    if self.root.state() != 'withdrawn':
                        self.entry.focus_set()
                        continue
                    self.target = value
                    self.terminal.set(value['terminal'])
                    self.previous = self.candidate = ''
                    self.show_preview('')
                    self.set_entry()
                    self.picker = None
                    self.listbox.pack_forget()
                    x = min(value['x'], max(0,self.root.winfo_screenwidth()-680))
                    y = min(value['y']+8,max(0,self.root.winfo_screenheight()-560))
                    self.root.geometry(f'660x530+{x}+{y}')
                    self.root.deiconify()
                    self.root.lift()
                    self.root.focus_force()
                    self.entry.focus_set()
                    self.status.config(text='输入要求或 / 命令。' + ('已定位输入光标。' if value['caret'] else '应用未提供原生光标坐标，浮层定位到窗口附近。'))
                    self.update_heading()
                elif kind == 'discovered':
                    self.backends = value
                    available = [b.name for b in value if not b.error]
                    if self.backend.get() not in available:
                        self.backend.set(available[0] if available else '')
                    self.select_backend(self.backend.get())
                    self.status.config(text='；'.join(f'{b.name}: {"可启动" if not b.error else b.error[:90]}' for b in value))
                elif kind in ('result','error'):
                    job,payload = value
                    if job != self.job:
                        continue
                    self.busy = False
                    if kind == 'result':
                        self.candidate = sanitize(payload,self.terminal.get())
                        self.previous = self.candidate
                        self.show_preview(self.candidate)
                        self.status.config(text='候选尚未写入。Tab 接受，或继续输入修改要求后回车。')
                    else:
                        self.status.config(text='生成失败：'+str(payload))
        except queue.Empty:
            pass
        self.root.after(50,self.poll)

    def show_preview(self,text):
        self.preview.config(state='normal')
        self.preview.delete('1.0','end')
        self.preview.insert('1.0',text)
        self.preview.config(state='disabled')

    def selected(self):
        indexes = self.listbox.curselection()
        return self.choices[indexes[0]] if indexes and self.choices else None

    def show_choices(self,choices,labels=None):
        self.choices = choices
        self.listbox.delete(0,'end')
        for label in labels or choices:
            self.listbox.insert('end',label)
        if choices:
            self.listbox.pack(fill='x',before=self.preview)
            self.listbox.selection_set(0)
        else:
            self.listbox.pack_forget()

    def changed(self,event=None):
        if event and event.keysym in ('Up','Down','Tab','Return','Escape'):
            return
        text = self.text()
        if self.picker:
            values = ([b.name for b in self.backends if not b.error] if self.picker == 'backend' else self.current().models if self.current() else [])
            self.show_choices([v for v in values if text.lower() in v.lower()])
        elif text.startswith('/') and '\n' not in text:
            choices = [c for c in COMMANDS if c.startswith(text)]
            self.show_choices(choices,[f'{c}   {COMMANDS[c]}' for c in choices])
        else:
            self.show_choices([])

    def move(self,delta):
        if self.choices:
            i = self.listbox.curselection()
            n = ((i[0] if i else 0)+delta)%len(self.choices)
            self.listbox.selection_clear(0,'end')
            self.listbox.selection_set(n)
            self.listbox.see(n)
            return 'break'

    def complete(self,event=None):
        value = self.selected()
        if value:
            if self.picker:
                self.choose()
            else:
                self.set_entry(value)
                self.changed()
        return 'break'

    def tab(self,event=None):
        if self.choices:
            return self.complete()
        return self.accept()

    def current(self):
        return next((b for b in self.backends if b.name == self.backend.get() and not b.error),None)

    def save(self):
        self.settings['backend'] = self.backend.get()
        self.settings.setdefault('models',{})[self.backend.get()] = self.model.get()
        self.settings_file.write_text(json.dumps(self.settings,ensure_ascii=False,indent=2),encoding='utf-8')

    def select_backend(self,name):
        self.backend.set(name)
        b = self.current()
        saved = self.settings.get('models',{}).get(name,DEFAULT)
        self.model.set(saved if b and saved in b.models else DEFAULT)
        self.update_heading()

    def open_picker(self,kind):
        if self.busy:
            return 'break'
        self.picker = kind
        self.set_entry()
        self.changed()
        b = self.current()
        self.status.config(text='方向键选择，输入筛选，Enter 确认。'+(b.source if kind=='model' and b else '仅显示版本检查通过的 CLI。'))
        self.entry.focus_set()
        return 'break'

    def choose(self,event=None):
        value = self.selected()
        if not value:
            return 'break'
        if self.picker:
            if self.picker == 'backend':
                self.select_backend(value)
            else:
                self.model.set(value)
            self.save()
            self.picker = None
            self.show_choices([])
            self.set_entry()
            self.update_heading()
            self.entry.focus_set()
        else:
            self.run_command(value)
        return 'break'

    def toggle_terminal(self,event=None):
        self.terminal.set(not self.terminal.get())
        self.update_heading()
        return 'break'

    def run_command(self,cmd):
        self.set_entry()
        self.show_choices([])
        if cmd in ('/backend','/model'):
            return self.open_picker(cmd[1:])
        if cmd == '/terminal': self.toggle_terminal()
        elif cmd == '/refresh': self.refresh()
        elif cmd == '/cancel': self.hide()
        elif cmd == '/quit': self.quit()
        elif cmd == '/clear':
            self.job += 1
            self.cancel.set()
            self.busy = False
            self.candidate = self.previous = ''
            self.show_preview('')
        elif cmd == '/help':
            self.candidate = ''
            self.show_preview('\n'.join(f'{c}  {d}' for c,d in COMMANDS.items()))

    def enter(self,event=None):
        if event and event.state & 1:
            return None
        if self.picker or self.text().startswith('/'):
            return self.choose()
        if self.busy:
            return 'break'
        b = self.current()
        request = self.text()
        if not b or not request:
            self.status.config(text='请先选择可用 CLI，再输入要求。')
            return 'break'
        self.job += 1
        job = self.job
        self.cancel = threading.Event()
        cancel = self.cancel
        prompt = prompt_for(request,self.previous,self.terminal.get())
        model = self.model.get()
        self.candidate = ''
        self.busy = True
        self.set_entry()
        self.status.config(text='正在生成… Esc 可取消。')
        def work():
            try:
                text = generate(b,model,prompt,cancel,lambda p:setattr(self,'process',p))
                self.events.put(('result',(job,text)))
            except Exception as e:
                self.events.put(('error',(job,str(e))))
        threading.Thread(target=work,daemon=True).start()
        return 'break'

    def accept(self,event=None):
        if self.busy or not self.candidate or not self.target:
            return 'break'
        text = sanitize(self.candidate,self.terminal.get())
        self.root.withdraw()
        try:
            windows.insert(self.target,text)
            self.candidate = ''
        except Exception as e:
            self.root.deiconify()
            self.entry.focus_set()
            self.status.config(text=str(e))
        return 'break'

    def escape(self,event=None):
        if self.picker:
            self.picker = None
            self.set_entry()
            self.show_choices([])
            return 'break'
        return self.hide()

    def hide(self,event=None):
        self.job += 1
        self.cancel.set()
        self.busy = False
        self.root.withdraw()
        if self.target:
            try: windows.restore(self.target)
            except RuntimeError: pass
        return 'break'

    def quit(self,event=None):
        self.cancel.set()
        stop(self.process)
        self.root.destroy()
        return 'break'

    def run(self):
        self.root.mainloop()
