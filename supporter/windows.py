"""Windows focus, hotkey, caret and Unicode input integration (no dependencies)."""
import ctypes as C
from ctypes import wintypes as W
import time
import subprocess
from pathlib import Path
import json
import threading
import queue
import re
import sys
from contextlib import contextmanager
from .targets import describe_target
from .anchors import choose_anchor
from .terminal import parse_prompt
from .paths import RESOURCE_ROOT,VENDOR_ROOT,RUNTIME_ROOT,helper_path

try:
    C.WinDLL('user32').SetProcessDpiAwarenessContext(C.c_void_p(-4))
except (OSError,AttributeError):
    pass
_probe = None
_probe_path = None
_probe_lock=threading.Lock()

def probe_caret(request=None):
    with _probe_lock:return _probe_caret(request)

def _probe_caret(request=None):
    global _probe, _probe_path
    native=(VENDOR_ROOT/'comtypes').is_dir()
    exe=helper_path('caret-probe')
    if not native and exe is None:return None
    identity='native-uia' if native else exe
    if _probe is not None and _probe_path!=identity:
        _probe.kill();_probe=None
    if _probe is None or _probe.poll() is not None:
        argv=[sys.executable,'-B','-u','-m','supporter.uia_native'] if native else [str(exe)]
        _probe=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                text=True,encoding='utf-8',cwd=RESOURCE_ROOT,creationflags=subprocess.CREATE_NO_WINDOW)
        _probe_path=identity
    answers=queue.Queue()
    child=_probe
    def query():
        try:
            child.stdin.write((json.dumps(request) if request else 'caret')+'\n'); child.stdin.flush()
            answers.put(json.loads(child.stdout.readline()))
        except (OSError,ValueError): answers.put(None)
    threading.Thread(target=query,daemon=True).start()
    try: return answers.get(timeout=1.2)
    except queue.Empty:
        child.kill(); _probe=None
        return None

u = C.WinDLL('user32', use_last_error=True)
k = C.WinDLL('kernel32', use_last_error=True)
u.GetForegroundWindow.restype = W.HWND
u.SetForegroundWindow.argtypes = [W.HWND]
u.IsWindow.argtypes = [W.HWND]
u.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
u.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
u.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
u.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
u.ClientToScreen.argtypes = [W.HWND, C.POINTER(W.POINT)]

class GUI(C.Structure):
    _fields_ = [('cbSize', W.DWORD), ('flags', W.DWORD),
                *[(s, W.HWND) for s in ['active','focus','capture','menu','move','caret']],
                ('rect', W.RECT)]

class KEY(C.Structure):
    _fields_ = [('vk', W.WORD), ('scan', W.WORD), ('flags', W.DWORD),
                ('time', W.DWORD), ('extra', C.c_size_t)]
class MOUSE(C.Structure):
    _fields_ = [('dx', W.LONG), ('dy', W.LONG), ('data', W.DWORD),
                ('flags', W.DWORD), ('time', W.DWORD), ('extra', C.c_size_t)]
class UNION(C.Union):
    _fields_ = [('ki', KEY), ('mi', MOUSE)]
class INPUT(C.Structure):
    _anonymous_ = ('value',)
    _fields_ = [('type', W.DWORD), ('value', UNION)]
u.SendInput.argtypes = [W.UINT, C.POINTER(INPUT), C.c_int]

def capture():
    hwnd = u.GetForegroundWindow()
    info = GUI(cbSize=C.sizeof(GUI))
    tid = u.GetWindowThreadProcessId(hwnd, None)
    has_native = u.GetGUIThreadInfo(tid, C.byref(info)) and info.caret
    native=None
    if has_native:
        pt = W.POINT(info.rect.left, info.rect.top)
        u.ClientToScreen(info.caret, C.byref(pt))
        native={'x':pt.x,'y':pt.y,'width':info.rect.right-info.rect.left,'height':info.rect.bottom-info.rect.top}
    rect=W.RECT();u.GetWindowRect(hwnd,C.byref(rect))
    result=C.c_size_t()
    u.SendMessageTimeoutW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM,W.UINT,W.UINT,C.POINTER(C.c_size_t)]
    u.SendMessageTimeoutW(hwnd,0x003D,0,-4,2,100,C.byref(result))
    context=probe_caret() or {}
    if u.GetForegroundWindow()!=hwnd:
        raise RuntimeError('读取输入位置时焦点已切换，请在目标输入处重新唤起')
    anchor=choose_anchor(native,context,(rect.left,rect.top,rect.right,rect.bottom))
    cls = C.create_unicode_buffer(256)
    title = C.create_unicode_buffer(512)
    u.GetClassNameW(hwnd, cls, 256)
    u.GetWindowTextW(hwnd, title, 512)
    terminal = bool(context.get('terminal')) or any(s in cls.value.lower() for s in ['cascadia','consolewindow','mintty'])
    if re.search(r'Visual Studio Code|Cursor|Windsurf|Jupyter|Notebook|Colab',title.value,re.I):context['paste_mode']='standard'
    return {'hwnd': hwnd,'focus':info.focus, 'terminal':terminal,'title':title.value,
            'physical_terminal':terminal,**anchor,**describe_target(context,terminal)}

def restore(target):
    if not u.IsWindow(target['hwnd']):
        raise RuntimeError('原窗口已经关闭，请重新唤起')
    thread=u.GetWindowThreadProcessId(target['hwnd'],None)
    own=k.GetCurrentThreadId()
    u.SetFocus.argtypes=[W.HWND]
    foreground_thread=u.GetWindowThreadProcessId(u.GetForegroundWindow(),None)
    attached_foreground=u.AttachThreadInput(own,foreground_thread,True) if foreground_thread!=thread else False
    attached=u.AttachThreadInput(own,thread,True)
    try:
        u.SetForegroundWindow(target['hwnd'])
        if target.get('focus') and u.IsWindow(target['focus']): u.SetFocus(target['focus'])
    finally:
        if attached:u.AttachThreadInput(own,thread,False)
        if attached_foreground:u.AttachThreadInput(own,foreground_thread,False)

def list_inputs(target):
    if not target.get('hwnd') or not u.IsWindow(target['hwnd']):raise RuntimeError('原窗口已关闭，请在目标窗口重新唤醒')
    result=probe_caret({'hwnd':target['hwnd'],'locate_inputs':True})
    if not isinstance(result,dict) or 'controls' not in result:raise RuntimeError('此窗口未能提供输入区域列表；可先键盘聚焦输入区再唤醒')
    return result

def focus_input(target,identifier):
    if not isinstance(identifier,str) or len(identifier)>200:raise RuntimeError('输入区域标识无效，请重新定位')
    restore(target)
    result=probe_caret({'hwnd':target['hwnd'],'focus_runtime_id':identifier})
    if not result or not result.get('focused'):raise RuntimeError((result or {}).get('error','无法聚焦该输入区，请重新定位'))
    captured=capture()
    if captured['hwnd']!=target['hwnd']:raise RuntimeError('原窗口焦点已切换，请重新定位')
    return captured

def insert(target, text, replace=False):
    if '\n' in text or '\r' in text:
        if target.get('terminal'):raise RuntimeError('终端多行内容请先复制到脚本编辑器，避免粘贴时自动执行')
        with prepared_paste(text):return _insert(target,text,replace,paste=True)
    return _insert(target,text,replace)

def _insert(target,text,replace=False,paste=False):
    restore(target)
    time.sleep(.15)
    if u.GetForegroundWindow() != target['hwnd']:
        raise RuntimeError('无法恢复原窗口焦点，未输入任何文本')
    # Wait for acceptance shortcut modifiers to be released.
    for _ in range(100):
        if not any(u.GetAsyncKeyState(v) & 0x8000 for v in [9,13,16,17,18]):
            break
        time.sleep(.01)
    else:
        raise RuntimeError('请松开快捷键后再接受')
    selection_keys=[]
    if replace:
        scope=target.get('scope','insert')
        if scope not in ('selection','editor','terminal-line'):
            raise RuntimeError('当前位置不可编辑；候选已保留，请聚焦输入框后按唤醒快捷键继续')
        current=probe_caret()
        if not current or current.get('editor_id')!=target.get('editor_id'):
            raise RuntimeError('原编辑控件已变化，未替换；请重新唤起')
        expected=target.get('context','')
        actual=current.get('selection','') if scope=='selection' else current.get('text','')
        if scope=='terminal-line':
            prompt=parse_prompt(current.get('line',''))
            if target.get('command') is None or not prompt or prompt['command']!=target['command'] or (target.get('prompt_line') and prompt['line']!=target['prompt_line']):
                raise RuntimeError('当前命令行已变化，未替换；请重新唤起')
            # PSReadLine / cmd / common shell editors: select current input line.
            # Home and Shift+End are deliberately used instead of terminal Ctrl+A.
            if target.get('shell')=='posix':
                selection_keys=[(0x11,0),(0x41,0),(0x41,2),(0x4B,0),(0x4B,2),(0x11,2)]
            else:selection_keys=[(0x24,0),(0x24,2),(0x10,0),(0x23,0),(0x23,2),(0x10,2)]
        elif actual!=expected:
            raise RuntimeError('原文或选区已变化，未替换；请重新唤起')
        elif scope=='editor':
            selection_keys=[(0x11,0),(0x41,0),(0x41,2),(0x11,2)]
    if paste:
        if target.get('paste_mode')=='soft-lines':type_softlines(text,target['hwnd'],selection_keys)
        else:paste_keys(target['hwnd'],selection_keys)
        return
    if selection_keys:key_events(selection_keys)
    data = text.encode('utf-16-le')
    events = []
    for i in range(0,len(data),2):
        unit = int.from_bytes(data[i:i+2], 'little')
        for flags in [4,6]:
            events.append(INPUT(type=1, ki=KEY(scan=unit,flags=flags)))
    for offset in range(0,len(events),128):
        batch = events[offset:offset+128]
        array = (INPUT * len(batch))(*batch)
        if u.SendInput(len(batch),array,C.sizeof(INPUT)) != len(batch):
            raise RuntimeError('目标拒绝输入（可能权限不同）；可能已填入部分文本，请检查后重试')

def key_events(keys):
    events=(INPUT*len(keys))(*(INPUT(type=1,ki=KEY(vk=vk,flags=flags)) for vk,flags in keys))
    if u.SendInput(len(keys),events,C.sizeof(INPUT))!=len(keys):
        raise RuntimeError('目标拒绝键盘输入，替换已停止')

@contextmanager
def prepared_paste(text):
    path=helper_path('paste-bridge')
    if path is None:raise RuntimeError('多行写回组件缺失，请重新安装 Supporter')
    child=subprocess.Popen([str(path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
    reply=queue.Queue()
    def read():
        try:reply.put(child.stdout.readline().strip())
        except OSError:reply.put('error:剪贴板桥接中断')
    try:
        child.stdin.write(json.dumps({'text':text},ensure_ascii=False)+'\n');child.stdin.flush()
        threading.Thread(target=read,daemon=True).start()
        result=reply.get(timeout=3)
        if result!='ready':raise RuntimeError('多行写回未开始：'+result)
        yield
        child.stdin.write('consumed\n');child.stdin.flush()
    except queue.Empty:raise RuntimeError('剪贴板暂时不可用，请稍后重试或复制候选')
    finally:
        child.stdin.close()
        try:child.wait(timeout=3)
        except subprocess.TimeoutExpired:child.kill()
        child.stdout.close()

def paste_keys(expected_hwnd=None,prefix=(),plain=False):
    if expected_hwnd and u.GetForegroundWindow()!=expected_hwnd:
        raise RuntimeError('焦点已变化，未发送粘贴按键；完整结果已在剪贴板，可 Ctrl+V 粘贴')
    modifiers=[(0x11,0)]+([(0x10,0)] if plain else [])
    release=([(0x10,2)] if plain else [])+[(0x11,2)]
    key_events([*prefix,*modifiers,(0x56,0),(0x56,2),*release])
    time.sleep(.3)

def paste_text(text,expected_hwnd=None,plain=False):
    with prepared_paste(text):paste_keys(expected_hwnd,plain=plain)

def type_softlines(text,expected_hwnd,prefix=()):
    """Chrome rich input: use soft line breaks, never a submit Enter."""
    groups=[]
    if prefix:groups.append([INPUT(type=1,ki=KEY(vk=vk,flags=flags)) for vk,flags in prefix])
    for i,line in enumerate(text.replace('\r\n','\n').replace('\r','\n').split('\n')):
        if i:groups.append([INPUT(type=1,ki=KEY(vk=vk,flags=flags)) for vk,flags in [(0x10,0),(13,0),(13,2),(0x10,2)]])
        for char in line:
            encoded=char.encode('utf-16-le');group=[]
            for offset in range(0,len(encoded),2):
                unit=int.from_bytes(encoded[offset:offset+2],'little')
                group.extend(INPUT(type=1,ki=KEY(scan=unit,flags=flag)) for flag in (4,6))
            groups.append(group)
    def send_batch(batch):
        if u.GetForegroundWindow()!=expected_hwnd:raise RuntimeError('焦点已变化，停止写回；完整结果仍在剪贴板')
        array=(INPUT*len(batch))(*batch)
        if u.SendInput(len(batch),array,C.sizeof(INPUT))!=len(batch):raise RuntimeError('目标未完整接收文本；完整结果仍在剪贴板')
    batch=[]
    for group in groups:
        if len(batch)+len(group)>512:send_batch(batch);batch=[]
        batch.extend(group)
    if batch:send_batch(batch)

def hotkeys(queue, ready):
    if not u.RegisterHotKey(None, 1, 0x4002, 0x20):
        ready.put('Ctrl+Space 被占用，无法注册全局快捷键')
        return
    ready.put(None)
    msg = W.MSG()
    try:
        while u.GetMessageW(C.byref(msg),None,0,0) > 0:
            if msg.message == 0x312:
                queue.put(('wake', capture()))
    finally:
        u.UnregisterHotKey(None,1)
