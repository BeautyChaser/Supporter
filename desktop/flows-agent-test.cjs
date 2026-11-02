/* Full application harness: real Electron main/renderer/settings, fake CLI and
 * clipboard only. It never launches an agent or types in another application. */
const electron=require('electron');
const {app,BrowserWindow}=electron;
const {PassThrough,Writable}=require('node:stream');
const {EventEmitter}=require('node:events');
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const dataDirectory=fs.mkdtempSync(path.join(root,'.runtime','desktop-data-agent-'));
process.env.SUPPORTER_DATA_DIR=dataDirectory;
process.env.SUPPORTER_COMPLETION_ROOT=path.join(dataDirectory,'completions','user');
const chromiumDirectory=path.join(dataDirectory,'chromium');fs.mkdirSync(chromiumDirectory,{recursive:true});app.setPath('userData',chromiumDirectory);app.setPath('sessionData',chromiumDirectory);
const reportFile=path.join(root,'.runtime','frontend-agent-report.json');
const report={runId:new Date().toISOString(),passed:false,tests:[],running:true,windowEvents:[]};
fs.writeFileSync(reportFile,JSON.stringify({...report,running:true},null,2));
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const keys=new Map();const commands=[];const copies=[];
let clipboardFailure=false;
electron.globalShortcut.register=(key,fn)=>{keys.set(key,fn);return true;};
electron.globalShortcut.unregisterAll=()=>keys.clear();
electron.clipboard.writeText=value=>clipboardFailure?Promise.reject(new Error('fixture: Clipboard unavailable')):copies.push(value);
app.setLoginItemSettings=()=>{throw new Error('Test must not mutate Windows login settings');};
let currentTarget={scope:'editor',context:'原始内容',source:'uia-caret',shell:null};
let suspended=false,resultId=0,fixtureResult=null,persistError=false,activeGenerate=null;
let captureAutomatic=true,locateAutomatic=true,locateSelectionError=false;
const locateControls=[
  {id:11,name:'说明编辑器',class:'Edit',bounds:{left:120,top:180,right:720,bottom:320},focused:true,terminal:false},
  {id:22,name:'PowerShell 终端',class:'TermControl',bounds:{left:200,top:400,right:1000,bottom:700},focused:false,terminal:true},
  {id:33,name:'搜索输入框',class:'SearchBox',bounds:{left:140,top:80,right:600,bottom:130},focused:false,terminal:false}
];
const inventory={backends:[
  {name:'codex',error:'',version:'fixture',models:['gpt-6-luna','gpt-6.1-terra','provider/model:tag'],reasoning:{'gpt-6-luna':['low','high'],'gpt-6.1-terra':['low','high']}},
  {name:'opencode',error:'',version:'fixture',models:['provider/model:tag'],reasoning:{'provider/model:tag':['low']}}
],settings:{backend:'codex',models:{codex:'gpt-6-luna'},reasoning:{},environment:'auto',general:{hotkey:'Control+Space',autoStart:false},onboarding:{completed:true}}};
fs.writeFileSync(path.join(dataDirectory,'settings.json'),JSON.stringify(inventory.settings));
const worker=new EventEmitter();worker.stdout=new PassThrough();worker.stderr=new PassThrough();worker.killed=false;
worker.kill=()=>{worker.killed=true;worker.emit('exit',0);};
const emit=event=>worker.stdout.write(JSON.stringify(event)+'\n');
function command(data){
  commands.push(data);
  if(data.type==='capture'){if(!suspended)activeGenerate=null;if(captureAutomatic)emit({type:'wake',request_id:data.request_id,target:{x:500,y:800,terminal:false,...currentTarget},resume:suspended});suspended=false;}
  if(data.type==='suspend')suspended=true;
  if(data.type==='cancel'){suspended=false;fixtureResult=null;activeGenerate=null;}
  if(data.type==='generate')activeGenerate=data;
  if(data.type==='locate-window'&&locateAutomatic)setTimeout(()=>emit({type:'locate-results',request_id:data.request_id,controls:locateControls,title:'隔离测试原窗口',limited:false}),20);
  if(data.type==='locate-select')setTimeout(()=>{
    if(locateSelectionError){emit({type:'locate-error',request_id:data.request_id,message:'fixture: 所选输入区已经关闭'});return;}
    const control=locateControls.find(item=>item.id===data.candidate_id);
    assert.ok(control,'locate-select must carry a returned control id');
    currentTarget={x:450,y:700,scope:control.terminal?'terminal-line':'editor',context:control.terminal?'Get-Location':'定位后的编辑内容',source:'uia-caret-active',terminal:control.terminal,shell:control.terminal?'powershell':null};
    suspended=false;emit({type:'wake',request_id:data.request_id,target:currentTarget,resume:true});
  },30);
  if(data.type==='cancel-generation'){
    const id=data.client_request_id||activeGenerate?.client_request_id;activeGenerate=null;
    setTimeout(()=>emit({type:'generation-stopped',...(id?{client_request_id:id}:{})}),30);
  }
  if(data.type==='settings'){
    if(!data.request_id)inventory.settings=data.settings;
    else setTimeout(()=>{
      if(persistError){emit({type:'settings-persist-error',request_id:data.request_id,message:'fixture: 文件不可写'});return;}
      inventory.settings=data.settings;emit({type:'settings-persisted',request_id:data.request_id});
    },30);
  }
  if(data.type==='accept'||data.type==='copy'){
    const text=fixtureResult?.candidates?.[data.candidate_index]?.text;
    if(!text)return;
    if(currentTarget.scope==='reference'||data.type==='copy')emit({type:'copy-ready',text});else emit({type:'accepted'});
  }
}
let buffer='';worker.stdin=new Writable({write(chunk,encoding,done){buffer+=chunk;let n;while((n=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,n);buffer=buffer.slice(n+1);if(line)command(JSON.parse(line));}done();}});
require('node:child_process').spawn=(file,args)=>{
  assert.ok(args.includes('supporter.service'),'unexpected process launch');
  setTimeout(()=>{emit({type:'ready',error:null});emit({type:'inventory',...inventory});},20);return worker;
};
require('./main.cjs');
app.on('before-quit',()=>{if(report.running){report.running=false;report.harnessError='Application quit before harness completed';fs.writeFileSync(reportFile,JSON.stringify(report,null,2));}});
async function waitFor(predicate,message,ms=3500){const deadline=Date.now()+ms;while(Date.now()<deadline){if(await predicate())return;await sleep(25);}throw new Error(message);}
async function test(name,fn){try{await fn();report.tests.push({name,passed:true});}catch(error){report.tests.push({name,passed:false,error:String(error.stack||error)});}fs.writeFileSync(reportFile,JSON.stringify({...report,running:true},null,2));}
let win;
const run=code=>win.webContents.executeJavaScript(code);
const key=(key,extra={})=>run('(()=>{const event=new KeyboardEvent("keydown",'+JSON.stringify({key,bubbles:true,cancelable:true,...extra})+');document.dispatchEvent(event);return event.defaultPrevented})()');
const type=value=>run('document.getElementById("prompt").value='+JSON.stringify(value)+';document.getElementById("prompt").dispatchEvent(new Event("input",{bubbles:true}))');
const edit=(value,caret=value.length,end=caret)=>run('(()=>{const input=document.getElementById("prompt");input.value='+JSON.stringify(value)+';input.dispatchEvent(new Event("input",{bubbles:true}));input.focus();input.setSelectionRange('+caret+','+end+');document.dispatchEvent(new Event("selectionchange"));})()');
const read=id=>run('document.getElementById('+JSON.stringify(id)+').textContent');
async function wake(resume=false){suspended=resume;keys.get('Control+Space')();await sleep(150);}
async function result(choices,reply='独立说明，不写回',kind='text'){fixtureResult={type:'result',kind,reply,candidates:choices,response_id:++resultId,...(activeGenerate?.client_request_id?{client_request_id:activeGenerate.client_request_id}:{})};emit(fixtureResult);await sleep(100);}
async function clear(){await key('Escape');await sleep(150);captureAutomatic=true;locateAutomatic=true;locateSelectionError=false;currentTarget={scope:'editor',context:'原始内容',source:'uia-caret'};await wake(false);}
const completionDirectory=process.env.SUPPORTER_COMPLETION_ROOT;
function habits(){return JSON.parse(fs.readFileSync(path.join(completionDirectory,'habits.json'),'utf8')).environments;}
function useCount(env,name){return habits()[env]?.find(item=>item.name===name)?.count||0;}
async function reloadCompletion(){await type('/tool:completion');await key('Enter');await sleep(35);}
async function showSettingsPage(){await key(',',{ctrlKey:true});await waitFor(async()=>!win.webContents.isLoading()&&await run('Boolean(document.getElementById("form"))'),'settings DOM did not load',5000);}
async function returnFromSettings(save=false){await run('document.getElementById('+JSON.stringify(save?'save':'windowClose')+').click()');await waitFor(async()=>win.webContents.getURL().endsWith('index.html')&&!win.webContents.isLoading(),'settings did not return',4000);await wake(true);}
async function installSettings(settings){inventory.settings=settings;emit({type:'inventory',...inventory});await sleep(45);}
async function publishInventory(backends,settings=inventory.settings,notice=''){inventory.backends=backends;inventory.settings=settings;emit({type:'inventory',...inventory,...(notice?{notice}:{})});await sleep(45);}
const clone=value=>JSON.parse(JSON.stringify(value));

app.whenReady().then(async()=>{
  try{
    await waitFor(()=>keys.size&&BrowserWindow.getAllWindows().length,'main did not register its hotkey');
    win=BrowserWindow.getAllWindows()[0];win.setFocusable(false);
    const glassCalls=[];const hostGlassApi=process.platform==='win32'&&Number(require('node:os').release().split('.')[2])>=22621&&typeof win.setBackgroundMaterial==='function';
    if(typeof win.setBackgroundMaterial==='function'){const original=win.setBackgroundMaterial.bind(win);win.setBackgroundMaterial=material=>{glassCalls.push(material);return original(material);};}
    report.glassNative={supportedByHost:hostGlassApi,calls:glassCalls};
    win.on('close',event=>report.windowEvents.push({event:'close',prevented:event.defaultPrevented}));
    win.on('closed',()=>report.windowEvents.push({event:'closed'}));
    win.webContents.on('did-fail-load',(_,code,description)=>report.windowEvents.push({event:'load-failed',code,description}));
    win.webContents.on('render-process-gone',(_,details)=>report.windowEvents.push({event:'renderer-gone',details}));
    const destroy=win.destroy.bind(win);win.destroy=(...args)=>{report.windowEvents.push({event:'destroy-call',stack:new Error().stack});return destroy(...args);};
    const setBounds=win.setBounds.bind(win);
    win.setBounds=(bounds,...args)=>{if(!['x','y','width','height'].every(k=>Number.isFinite(bounds[k])))throw new Error('Invalid bounds observed by harness: '+JSON.stringify(bounds)+' from '+JSON.stringify(win.getBounds()));return setBounds(bounds,...args);};
    await wake();
    await test('colon environments bash / powershell / markdown',async()=>{
      for(const env of ['bash','powershell','markdown']){
        await type('/env:'+env);await key('Tab');assert.equal(await run('document.getElementById("prompt").value'),'/env:'+env);
        await key('Enter');assert.equal(await read('environment'),env);
        assert.equal(commands.filter(c=>c.type==='settings').at(-1).settings.environment,env);
      }
    });
    await test('colon model / backend / reasoning retain model colon',async()=>{
      await type('/model:gpt-6.1-terra');await key('Enter');assert.equal(await read('model'),'gpt-6.1-terra');
      await type('/reasoning:low');await key('Enter');assert.ok((await read('effort')).includes('低'));
      await type('/backend:opencode');await key('Enter');assert.equal(await read('backend'),'opencode');
      await type('/model:provider/model:tag');await key('Tab');await key('Enter');assert.equal(await read('model'),'provider/model:tag');
      await type('/backend:codex');await key('Enter');
    });
    await test('Ctrl+M interrupts generation and retries same request',async()=>{
      await clear();await type('请简化这句话');await key('Enter');const first=commands.filter(c=>c.type==='generate').at(-1);
      const count=commands.filter(c=>c.type==='cancel-generation').length;
      await key('m',{ctrlKey:true});assert.ok(commands.filter(c=>c.type==='cancel-generation').length>count);
      await type('gpt-6-luna');await key('Enter');await sleep(30);
      const latest=commands.filter(c=>c.type==='generate').at(-1);
      assert.equal(latest.request,first.request);assert.equal(latest.model,'gpt-6-luna');assert.deepEqual(latest.history,first.history);
      await result([{label:'结果',detail:'',text:'简短内容'}]);
    });
    await test('/model: during generation interrupts and retries',async()=>{
      await clear();await type('保留同一请求');await key('Enter');
      const cancels=commands.filter(c=>c.type==='cancel-generation').length;
      const generates=commands.filter(c=>c.type==='generate').length;
      await type('/model:gpt-6.1-terra');await key('Enter');await sleep(40);
      assert.ok(commands.filter(c=>c.type==='cancel-generation').length>cancels,'colon selector must cancel in-flight request');
      assert.equal(commands.filter(c=>c.type==='generate').length,generates+1,'colon selector must restart original request');
      await result([{label:'结果',detail:'',text:'同一请求结果'}]);
    });
    await test('blur hides, keeps draft/history/candidate; wake resumes',async()=>{
      await clear();await type('初始要求');await key('Enter');await result([{label:'结果',text:'候选内容'}]);
      await type('未发送的修改草稿');const messages=await run('document.querySelectorAll("#conversation .message").length');
      win.emit('blur');await sleep(80);assert.equal(win.isVisible(),false);assert.equal(commands.at(-1).type,'suspend');
      await wake(true);assert.equal(await run('document.getElementById("prompt").value'),'未发送的修改草稿');
      assert.equal(await read('candidate'),'候选内容');assert.equal(await run('document.querySelectorAll("#conversation .message").length'),messages);
    });
    await test('Esc closes context even in a selector',async()=>{
      await type('/model:');const before=commands.length;await key('Escape');await sleep(150);assert.ok(commands.slice(before).some(c=>c.type==='cancel'));
      await wake(false);assert.equal(await run('document.getElementById("prompt").value'),'');
      assert.equal(await run('document.querySelectorAll("#conversation .message").length'),0);
      assert.equal(await run('document.getElementById("result").hidden'),true);
    });
    await test('generation can finish while hidden without losing draft',async()=>{
      await clear();await type('后台生成要求');await key('Enter');await type('生成期间的草稿');
      win.emit('blur');await sleep(60);assert.equal(win.isVisible(),false);
      await result([{label:'后台候选',text:'后台完成的内容'}]);assert.equal(win.isVisible(),false,'a completed hidden request must not steal focus');
      await wake(true);assert.equal(await read('candidate'),'后台完成的内容');assert.equal(await run('document.getElementById("prompt").value'),'生成期间的草稿');
    });
    await test('multiple branches require selection; Tab only accepts one',async()=>{
      await clear();await result([{label:'NVIDIA',text:'nvidia-smi'},{label:'AMD',text:'rocm-smi'}]);
      const count=commands.filter(c=>c.type==='accept').length;await key('Tab');assert.equal(commands.filter(c=>c.type==='accept').length,count);
      await key('2',{altKey:true});await key('Tab');await sleep(150);
      const accepted=commands.filter(c=>c.type==='accept').at(-1);assert.equal(accepted.candidate_index,1);assert.ok(!('text' in accepted));
    });
    await test('readonly Tab copies entire multiline candidate, no auto-paste',async()=>{
      await clear();currentTarget={scope:'reference',context:'只读页面选区',source:'uia-selection'};await wake(false);
      const markdown='# 标题\n\n第一行\n第二行\n';await result([{label:'Markdown',text:markdown}]);
      await key('Tab');await sleep(180);assert.equal(copies.at(-1),markdown);assert.equal(win.isVisible(),false);
      assert.ok(commands.some(c=>c.type==='clipboard-written'));
    });
    await test('clipboard failure does not claim success or discard candidate',async()=>{
      await clear();currentTarget={scope:'reference',context:'只读位置',source:'uia-selection'};await wake(false);
      await result([{label:'候选',text:'复制失败后应保留'}]);const copiedCount=commands.filter(c=>c.type==='clipboard-written').length;
      clipboardFailure=true;
      try{
        await key('Tab');await waitFor(async()=>win.isVisible()&&(await read('status')).includes('Clipboard unavailable'),'copy failure feedback was not shown');
        assert.equal(commands.filter(c=>c.type==='clipboard-written').length,copiedCount);assert.equal(await read('candidate'),'复制失败后应保留');
      }finally{clipboardFailure=false;}
    });
    await test('auto environment follows detected Bash and PowerShell terminal',async()=>{
      await clear();await type('/env:auto');await key('Enter');
      for(const [shell,expected] of [['posix','bash'],['powershell','powershell']]){
        currentTarget={scope:'terminal-line',context:'',source:'uia-caret-active',terminal:true,shell};await wake(false);
        await type('列出文件');await key('Enter');const request=commands.filter(c=>c.type==='generate').at(-1);
        assert.equal(request.environment,expected);assert.equal(request.terminal,true);
        await result([{label:'命令',text:'fixture-command'}]);await key('Escape');await sleep(150);
      }
    });
    await test('progress resize settles; footer stays visible',async()=>{
      await clear();await result(Array.from({length:8},(_,i)=>({label:'分支 '+i,detail:'完整描述 '.repeat(12),text:'command-'+i})));await key('ArrowDown');
      const start=commands.filter(c=>c.type==='resize').length;for(let i=0;i<30;i++)emit({type:'progress',message:'正在生成'});
      await sleep(400);const settled=commands.filter(c=>c.type==='resize').length;await sleep(250);
      assert.equal(commands.filter(c=>c.type==='resize').length,settled);assert.ok(settled-start<=3);
      const rect=await run('({bottom:document.querySelector("footer").getBoundingClientRect().bottom,height:innerHeight})');assert.ok(rect.bottom<=rect.height);
    });
    await test('actual settings route loads, failure stays, success closes',async()=>{
      await clear();await key(',',{ctrlKey:true});
      await waitFor(async()=>!win.webContents.isLoading()&&await run('Boolean(document.getElementById("form"))'),'settings DOM did not load',5000);
      assert.equal(await run('document.querySelectorAll("nav button").length'),4);
      assert.equal(await run('document.querySelectorAll("#colors button").length'),6);
      const image=await win.webContents.capturePage();const bitmap=image.toBitmap();const colorSet=new Set();
      for(let i=0;i<bitmap.length;i+=16)colorSet.add(bitmap.readUInt32LE(i));
      assert.ok(colorSet.size>50,'settings compositor must paint content, not a flat blank background');
      fs.writeFileSync(path.join(root,'.runtime','frontend-agent-settings.png'),image.toPNG());
      persistError=true;await run('document.getElementById("save").click()');await sleep(180);
      assert.ok((await run('document.getElementById("feedback").textContent')).includes('不可写'));
      assert.equal(await run('document.getElementById("save").disabled'),false);
      persistError=false;await run('document.getElementById("save").click()');
      await waitFor(async()=>win.webContents.getURL().endsWith('index.html')&&!win.webContents.isLoading(),'settings did not close after save',4000);
      assert.equal(win.isVisible(),false);
    });
    await test('settings round trip preserves existing conversation context',async()=>{
      await wake();await type('上下文不要丢失');await key('Enter');await result([{label:'结果',text:'保留候选'}]);await type('未发送草稿');
      const count=await run('document.querySelectorAll("#conversation .message").length');
      await key(',',{ctrlKey:true});await waitFor(async()=>!win.webContents.isLoading()&&await run('Boolean(document.getElementById("form"))'),'settings did not open',5000);
      await run('document.getElementById("windowClose").click()');await waitFor(async()=>win.webContents.getURL().endsWith('index.html')&&!win.webContents.isLoading(),'settings did not return',4000);
      await wake(true);assert.equal(await read('candidate'),'保留候选');
      assert.equal(await run('document.getElementById("prompt").value'),'未发送草稿');assert.equal(await run('document.querySelectorAll("#conversation .message").length'),count);
    });
    await test('result arriving during settings is replayed after return',async()=>{
      await clear();await type('设置期间继续生成');await key('Enter');await key(',',{ctrlKey:true});
      await waitFor(async()=>!win.webContents.isLoading()&&await run('Boolean(document.getElementById("form"))'),'settings did not open',5000);
      await result([{label:'延迟结果',text:'设置页面打开期间返回'}]);
      await run('document.getElementById("windowClose").click()');await waitFor(async()=>win.webContents.getURL().endsWith('index.html')&&!win.webContents.isLoading(),'settings did not return',4000);
      await wake(true);assert.equal(await read('candidate'),'设置页面打开期间返回');assert.equal(await run('document.getElementById("busy").hidden'),true);
    });
    await test('rapid Esc then wake cannot cancel the context-close action',async()=>{
      await clear();await type('必须关闭的请求');await key('Enter');const before=commands.filter(c=>c.type==='cancel').length;
      const originalFocus=win.isFocused.bind(win);win.isFocused=()=>true;
      try{await key('Escape');keys.get('Control+Space')();await sleep(160);}
      finally{win.isFocused=originalFocus;}
      assert.ok(commands.filter(c=>c.type==='cancel').length>before,'Esc must cancel server context even if the close animation is interrupted');
    });
    await test('/cancel menu completes, stops generation and keeps context; /stop is absent',async()=>{
      await clear();await type('请慢慢生成本轮内容');await key('Enter');
      const history=await run('window.supporterSession.snapshot().history');const cancelCount=commands.filter(c=>c.type==='cancel-generation').length;
      await type('/');assert.ok(!(await read('options')).includes('/stop'),'old /stop command must not remain in catalog');
      await type('/can');assert.ok((await read('options')).includes('/cancel'));
      await key('Tab');assert.equal(await run('document.getElementById("prompt").value'),'/cancel');await key('Enter');
      await waitFor(async()=>await run('document.getElementById("busy").hidden'),'stop did not end busy state');
      assert.ok(commands.filter(c=>c.type==='cancel-generation').length>cancelCount);assert.ok(win.isVisible());
      assert.deepEqual(await run('window.supporterSession.snapshot().history'),history,'stop must keep prior user turns');
    });
    await test('Ctrl+C stops only while busy and preserves unsent draft',async()=>{
      await clear();await type('需要停止的生成');await key('Enter');await type('不要清掉这段草稿');
      const history=await run('window.supporterSession.snapshot().history');const count=commands.filter(c=>c.type==='cancel-generation').length;
      assert.equal(await key('c',{ctrlKey:true}),true,'busy Ctrl+C is handled as stop');
      await waitFor(async()=>await run('document.getElementById("busy").hidden'),'Ctrl+C did not stop generation');
      assert.equal(commands.filter(c=>c.type==='cancel-generation').length,count+1);
      assert.equal(await run('document.getElementById("prompt").value'),'不要清掉这段草稿');
      assert.deepEqual(await run('window.supporterSession.snapshot().history'),history);
      const stoppedCount=commands.filter(c=>c.type==='cancel-generation').length;
      assert.equal(await key('c',{ctrlKey:true}),false,'idle Ctrl+C keeps normal copy behavior');
      assert.equal(commands.filter(c=>c.type==='cancel-generation').length,stoppedCount);
    });
    await test('stopped request late events cannot revive UI or affect a new request',async()=>{
      await clear();await type('即将停止的旧请求');await key('Enter');const old=commands.filter(c=>c.type==='generate').at(-1);
      assert.equal(typeof old.client_request_id,'string');await key('c',{ctrlKey:true});await sleep(80);
      const history=await run('window.supporterSession.snapshot().history');
      const late={client_request_id:old.client_request_id};
      emit({type:'progress',message:'旧请求的迟到进度',...late});
      emit({type:'result',kind:'text',reply:'旧请求迟到回复',candidates:[{label:'旧候选',text:'不能显示的旧结果'}],response_id:999,...late});
      emit({type:'error',message:'旧请求迟到错误',...late});await sleep(60);
      assert.equal(await run('document.getElementById("busy").hidden'),true);assert.equal(await run('document.getElementById("result").hidden'),true);
      assert.deepEqual(await run('window.supporterSession.snapshot().history'),history);
      await type('继续同一上下文的新请求');await key('Enter');const next=commands.filter(c=>c.type==='generate').at(-1);
      assert.notEqual(next.client_request_id,old.client_request_id);
      emit({type:'generation-stopped',...late});emit({type:'error',message:'旧请求又迟到',...late});await sleep(40);
      assert.equal(await run('document.getElementById("busy").hidden'),false,'an old stop receipt cannot stop the new request');
      await result([{label:'新候选',text:'新请求正常完成'}]);assert.equal(await read('candidate'),'新请求正常完成');
      assert.equal(await run('document.getElementById("busy").hidden'),true);
    });
    await test('/tool:completion menu opens inspector with documentation sources',async()=>{
      await clear();await type('/tool:comp');await key('Tab');assert.equal(await run('document.getElementById("prompt").value'),'/tool:completion');
      await key('Enter');assert.equal(await run('document.getElementById("completion").hidden'),false);
      assert.ok((await read('completionDetails')).includes('不执行输入'));
      assert.ok((await read('completionSource')).length>10);
    });
    await test('explicit bash powershell cmd enable backtick completion automatically',async()=>{
      const cases=[['bash','`nvid`',5,'nvidia-smi'],['powershell','`Get-Chi`',8,'Get-ChildItem'],['cmd','`di`',3,'dir']];
      for(const [env,draft,caret,expected] of cases){
        await clear();await type('/env:'+env);await key('Enter');await edit(draft,caret);
        assert.equal(await run('document.getElementById("completion").hidden'),false);
        assert.equal(await read('menuTitle'),env+' 命令补全 · ↑↓ 选择 · Tab / Enter 补全');await key('Tab');
        assert.equal(await run('document.getElementById("prompt").value'),'`'+expected+'`');
      }
    });
    await test('auto detected Bash and Markdown do not enable explicit completion',async()=>{
      await clear();await type('/env:auto');await key('Enter');currentTarget={scope:'terminal-line',context:'',source:'uia-caret-active',terminal:true,shell:'posix'};await wake(false);
      await result([{label:'候选',text:'nvidia-smi'}]);let before=commands.filter(c=>c.type==='accept').length;await edit('`nvid`',5);await key('Tab');
      assert.equal(await run('document.getElementById("prompt").value'),'`nvid`');assert.equal(commands.filter(c=>c.type==='accept').length,before);
      assert.ok((await read('completionCheck')).includes('/env:bash'));
      await clear();await type('/env:markdown');await key('Enter');await result([{label:'候选',text:'# AI 候选'}]);before=commands.filter(c=>c.type==='accept').length;
      await edit('`nvid`',5);await key('Tab');assert.equal(await run('document.getElementById("prompt").value'),'`nvid`');assert.equal(commands.filter(c=>c.type==='accept').length,before);
    });
    await test('flags subcommands and documented parameter values complete with Tab',async()=>{
      await clear();await type('/env:bash');await key('Enter');
      for(const [draft,expected] of [['`ls --hum`','`ls --human-readable`'],['`git sta`','`git status`'],['`git status --sh`','`git status --short`'],['`nvidia-smi --query-gpu=name,mem`','`nvidia-smi --query-gpu=name,memory.used`']]){
        await edit(draft,draft.length-1);await key('Tab');assert.equal(await run('document.getElementById("prompt").value'),expected);
      }
    });
    await test('completion in middle changes only current word and preserves surroundings',async()=>{
      await clear();await type('/env:bash');await key('Enter');
      const draft='说明 `nvidx --help` 保留结尾';const caret=draft.indexOf('nvid')+4;
      await edit(draft,caret);await key('Tab');assert.equal(await run('document.getElementById("prompt").value'),'说明 `nvidia-smi --help` 保留结尾');
      assert.equal(await run('document.getElementById("prompt").selectionStart'),'说明 `nvidia-smi'.length);
    });
    await test('moving caret refreshes completion without replacing a stale token',async()=>{
      await clear();await type('/env:bash');await key('Enter');
      const draft='`ls --hum | nvid`';await edit(draft,draft.length-1);assert.ok((await read('options')).includes('nvidia-smi'));
      await run('(()=>{const input=document.getElementById("prompt");const caret=input.value.indexOf("--hum")+5;input.setSelectionRange(caret,caret);document.dispatchEvent(new Event("selectionchange"));})()');
      await key('Tab');assert.equal(await run('document.getElementById("prompt").value'),'`ls --human-readable | nvid`');
    });
    await test('backtick Tab never accepts AI candidate including unknown commands',async()=>{
      await clear();await type('/env:bash');await key('Enter');await result([{label:'AI候选',text:'must-not-be-accepted'}]);
      const count=commands.filter(c=>c.type==='accept').length;
      await edit('`nvid`',5);await key('Tab');assert.equal(commands.filter(c=>c.type==='accept').length,count);
      await edit('`unknown-user-command --xyz`',26);await key('Tab');assert.equal(commands.filter(c=>c.type==='accept').length,count);
      assert.ok((await read('completionCheck')).includes('未收录'));
      assert.ok(!(await read('completionCheck')).includes('已安装'));
    });
    await test('completion preserves quoted arguments paths comments and selections',async()=>{
      await clear();await type('/env:bash');await key('Enter');
      for(const draft of ['`grep "--hum"`','`cat ~/some/path`','`ls # --hum`']){
        await edit(draft,draft.length-1);await key('Tab');assert.equal(await run('document.getElementById("prompt").value'),draft);
      }
      await edit('`nvid`',1,5);await key('Tab');assert.equal(await run('document.getElementById("prompt").value'),'`nvid`');
    });
    await test('completion draft and caret survive blur and settings route',async()=>{
      await clear();await type('/env:bash');await key('Enter');const draft='补全 `nvid --help` 末尾';const caret=draft.indexOf('nvid')+4;
      await edit(draft,caret);win.emit('blur');await sleep(70);await wake(true);
      assert.equal(await run('document.getElementById("prompt").value'),draft);assert.equal(await run('document.getElementById("prompt").selectionStart'),caret);
      await key(',',{ctrlKey:true});await waitFor(async()=>!win.webContents.isLoading()&&await run('Boolean(document.getElementById("form"))'),'settings did not open',5000);
      await run('document.getElementById("windowClose").click()');await waitFor(async()=>win.webContents.getURL().endsWith('index.html')&&!win.webContents.isLoading(),'settings did not return',4000);await wake(true);
      assert.equal(await run('document.getElementById("prompt").value'),draft);assert.equal(await run('document.getElementById("prompt").selectionStart'),caret);
      await key('Tab');assert.equal(await run('document.getElementById("prompt").value'),'补全 `nvidia-smi --help` 末尾');
    });
    await test('completion and tool inspector do not interrupt active AI generation',async()=>{
      await clear();await type('/env:bash');await key('Enter');await type('生成仍在进行');await key('Enter');const request=commands.filter(c=>c.type==='generate').at(-1);
      const count=commands.filter(c=>c.type==='cancel-generation').length;
      await edit('`nvid`',5);await key('Tab');assert.equal(await run('document.getElementById("prompt").value'),'`nvidia-smi`');
      assert.equal(commands.filter(c=>c.type==='cancel-generation').length,count);assert.equal(await run('document.getElementById("busy").hidden'),false);
      await type('/tool:completion');await key('Enter');assert.equal(commands.filter(c=>c.type==='cancel-generation').length,count);assert.equal(await run('document.getElementById("busy").hidden'),false);
      await result([{label:'正常结果',text:'仍然完成'}]);assert.equal(await read('candidate'),'仍然完成');assert.equal(commands.filter(c=>c.type==='generate').at(-1).client_request_id,request.client_request_id);
    });
    await test('user Bash command file reloads through tool and completes script flags',async()=>{
      await clear();await type('/env:bash');await key('Enter');
      const file=path.join(completionDirectory,'bash.json');
      fs.writeFileSync(file,JSON.stringify({version:1,commands:[{name:'train-local',description:'本地自定义脚本',flags:[['--epochs','训练轮数'],['--device=','选择设备']],values:{'--device=':[['cpu','CPU'],['gpu','GPU']]}}]}));
      await reloadCompletion();assert.ok((await read('completionCheck')).includes('自定义 1'));assert.ok((await read('completionSource')).includes(completionDirectory));
      for(const [draft,expected] of [['`train-`','`train-local`'],['`train-local --ep`','`train-local --epochs`'],['`train-local --device=gp`','`train-local --device=gpu`']]){
        await edit(draft,draft.length-1);await key('Tab');assert.equal(await run('document.getElementById("prompt").value'),expected);
      }
      const data=JSON.parse(fs.readFileSync(file,'utf8'));data.commands.push({name:'gpu-health',description:'新增加的本地命令'});fs.writeFileSync(file,JSON.stringify(data));
      await key('F5');await sleep(35);await edit('`gpu-he`',7);await key('Tab');assert.equal(await run('document.getElementById("prompt").value'),'`gpu-health`');
    });
    await test('sent backtick prompt learns names and flags only and persists across store reload',async()=>{
      await clear();await type('/env:bash');await key('Enter');
      const request='解释 `local-analysis --threads=TEST_PRIVATE_VALUE --api-key=TEST_SECRET_VALUE /private/DO_NOT_SAVE_PATH`';
      await type(request);await key('Enter');await waitFor(()=>useCount('bash','local-analysis')===1,'submitted command was not learned');
      const {CompletionStore}=require('./completion-store.cjs');const restarted=new CompletionStore(completionDirectory);
      const item=restarted.snapshot().usage.bash.find(row=>row.name==='local-analysis');assert.equal(item.count,1);assert.ok(item.flags.some(flag=>flag.value==='--threads'));
      assert.ok(!item.flags.some(flag=>flag.value==='--api-key'));
      const serialized=fs.readFileSync(path.join(completionDirectory,'habits.json'),'utf8');
      for(const value of ['TEST_PRIVATE_VALUE','TEST_SECRET_VALUE','DO_NOT_SAVE_PATH'])assert.ok(!serialized.includes(value),'parameter values must not be persisted: '+value);
      await result([{label:'说明',text:'完成'}]);
    });
    await test('learned frequency ranks a used command ahead of untouched entries',async()=>{
      await clear();await type('/env:bash');await key('Enter');const initial=useCount('bash','git');
      for(let i=0;i<2;i++){await type('解释 `git status --short`');await key('Enter');await result([{label:'解释',text:'状态说明'}]);}
      assert.equal(useCount('bash','git'),initial+2);
      await edit('`g`',2);assert.equal(await run('document.querySelector("#options .option > span").textContent'),'git');
      assert.ok((await read('options')).includes('常用'));
    });
    await test('auto environment never learns even when a Bash terminal was detected',async()=>{
      await clear();await type('/env:auto');await key('Enter');currentTarget={scope:'terminal-line',context:'',source:'uia-caret-active',terminal:true,shell:'posix'};await wake(false);
      await type('解释 `auto-not-learned --flag`');await key('Enter');await sleep(35);
      const sent=commands.filter(c=>c.type==='generate').at(-1);assert.equal(sent.environment,'bash');assert.equal(sent.completion_environment,'auto');
      assert.equal(useCount('bash','auto-not-learned'),0);assert.ok(!habits().auto);await result([{label:'说明',text:'说明'}]);
    });
    await test('model-switch retry does not count a submitted command twice',async()=>{
      await clear();await type('/env:bash');await key('Enter');await type('解释 `retry-local --flag=value`');await key('Enter');
      await waitFor(()=>useCount('bash','retry-local')===1,'first request should count once');
      await key('m',{ctrlKey:true});await type('gpt-6-luna');await key('Enter');await sleep(40);
      const retry=commands.filter(c=>c.type==='generate').at(-1);assert.equal(retry.observe_completion,false);assert.equal(useCount('bash','retry-local'),1);
      await result([{label:'解释',text:'完成'}]);
    });
    await test('preview-only AI commands are not learned; accept learns only selected branch',async()=>{
      await clear();await type('/env:bash');await key('Enter');await type('给我候选');await key('Enter');
      await result([{label:'第一个',text:'ai-preview-only --secret-value=DO_NOT_SAVE'},{label:'第二个',text:'ai-accepted-choice --safe=value'}],'说明','commands');
      assert.equal(useCount('bash','ai-preview-only'),0);assert.equal(useCount('bash','ai-accepted-choice'),0);
      await key('2',{altKey:true});await key('Tab');await waitFor(()=>useCount('bash','ai-accepted-choice')===1,'successful accept should learn selected command');
      assert.equal(useCount('bash','ai-preview-only'),0);const item=habits().bash.find(row=>row.name==='ai-accepted-choice');assert.deepEqual(item.flags.map(flag=>flag.value),['--safe']);
    });
    await test('successful clipboard copy learns chosen AI command; failed copy does not',async()=>{
      await clear();await type('/env:bash');await key('Enter');currentTarget={scope:'reference',context:'只读选区',source:'uia-selection'};await wake(false);
      await type('给我一个命令');await key('Enter');await result([{label:'复制',text:'ai-copied-command --verbose'}],'说明','commands');await key('Tab');
      await waitFor(()=>useCount('bash','ai-copied-command')===1,'successful copy was not learned');
      await clear();currentTarget={scope:'reference',context:'只读选区',source:'uia-selection'};await wake(false);await type('给我另一个命令');await key('Enter');
      await result([{label:'失败',text:'ai-failed-copy --verbose'}],'说明','commands');clipboardFailure=true;
      try{await key('Tab');await waitFor(async()=>win.isVisible()&&(await read('status')).includes('Clipboard unavailable'),'copy failure not reported');assert.equal(useCount('bash','ai-failed-copy'),0);}
      finally{clipboardFailure=false;}
    });
    await test('learning-off configuration remains usable without saving habits',async()=>{
      await clear();await type('/env:bash');await key('Enter');const file=path.join(completionDirectory,'config.json');fs.writeFileSync(file,JSON.stringify({version:1,learning:false}));
      try{await reloadCompletion();assert.ok((await read('completionCheck')).includes('学习关闭'));await type('解释 `learning-disabled --safe`');await key('Enter');await sleep(30);assert.equal(useCount('bash','learning-disabled'),0);await result([{label:'解释',text:'完成'}]);}
      finally{fs.writeFileSync(file,JSON.stringify({version:1,learning:true}));await reloadCompletion();}
    });
    await test('/loc menu and colon form expose keyboard-only window detection',async()=>{
      await clear();await type('/lo');assert.ok((await read('options')).includes('/loc'));await key('Tab');assert.equal(await run('document.getElementById("prompt").value'),'/loc');
      await key('Enter');assert.equal(await run('window.supporterSession.snapshot().menu'),'loc');assert.ok((await read('options')).includes('window'));
      await key('Enter');await waitFor(async()=>await run('window.supporterSession.snapshot().menu==="location"&&window.supporterSession.snapshot().locations.length===3'),'location controls not shown');
      const first=commands.filter(item=>item.type==='locate-window').at(-1);assert.equal(typeof first.request_id,'string');
      await clear();await type('/loc:win');await key('Tab');assert.equal(await run('document.getElementById("prompt").value'),'/loc:window');await key('Enter');
      await waitFor(async()=>await run('window.supporterSession.snapshot().locations.length===3'),'colon location detection not shown');
      assert.notEqual(commands.filter(item=>item.type==='locate-window').at(-1).request_id,first.request_id);assert.ok((await read('status')).includes('3 个可输入区域'));
    });
    await test('location filtering and arrow selection preserve conversation and AI candidate',async()=>{
      await clear();await type('先生成内容再定位');await key('Enter');await result([{label:'保留候选',text:'定位后仍可接受的内容'}]);const history=await run('window.supporterSession.snapshot().history');
      await type('/loc:window');await key('Enter');await waitFor(async()=>await run('window.supporterSession.snapshot().locations.length===3'),'no location list');
      await type('搜索');assert.equal(await run('document.querySelectorAll("#options .option").length'),1);assert.ok((await read('options')).includes('搜索输入框'));
      await type('');await key('ArrowDown');await key('ArrowDown');await key('ArrowUp');assert.ok((await run('document.querySelector("#options .active").textContent')).includes('PowerShell'));
      await key('Enter');assert.equal(win.isVisible(),false,'main must hide while focus is transferring');
      await waitFor(()=>win.isVisible(),'successful locate did not reveal floating window');
      const select=commands.filter(item=>item.type==='locate-select').at(-1);assert.equal(select.candidate_id,22);assert.equal(select.request_id,commands.filter(item=>item.type==='locate-window').at(-1).request_id);
      assert.equal(await read('original'),'Get-Location');assert.equal(await read('candidate'),'定位后仍可接受的内容');assert.deepEqual(await run('window.supporterSession.snapshot().history'),history);
      assert.equal(await run('window.supporterSession.snapshot().menu'),null);assert.ok((await read('scope')).includes('当前命令'));
    });
    await test('locating a new input during generation does not cancel or restart the AI request',async()=>{
      await clear();await type('定位期间继续生成');await key('Enter');const request=activeGenerate;const count=commands.filter(item=>item.type==='cancel-generation').length;const generated=commands.filter(item=>item.type==='generate').length;
      await type('/loc');await key('Enter');await key('Enter');await waitFor(async()=>await run('window.supporterSession.snapshot().locations.length===3'),'no location list while busy');
      await type('PowerShell');await key('Enter');await waitFor(()=>win.isVisible(),'busy locate did not return');
      assert.equal(commands.filter(item=>item.type==='cancel-generation').length,count);assert.equal(commands.filter(item=>item.type==='generate').length,generated);assert.equal(activeGenerate.client_request_id,request.client_request_id);
      assert.equal(await run('document.getElementById("busy").hidden'),false);await result([{label:'生成完成',text:'定位后生成正常完成'}]);assert.equal(await read('candidate'),'定位后生成正常完成');
    });
    await test('failed location reveals the existing busy conversation without cancelling it',async()=>{
      await clear();await type('错误定位仍然生成');await key('Enter');const history=await run('window.supporterSession.snapshot().history');const count=commands.filter(item=>item.type==='cancel-generation').length;locateSelectionError=true;
      await type('/loc:window');await key('Enter');await waitFor(async()=>await run('window.supporterSession.snapshot().locations.length===3'),'no location list before failure');await key('Enter');assert.equal(win.isVisible(),false);
      await waitFor(async()=>win.isVisible()&&(await read('status')).includes('所选输入区已经关闭'),'location error did not restore visible UI');
      assert.equal(await run('document.getElementById("busy").hidden'),false);assert.equal(commands.filter(item=>item.type==='cancel-generation').length,count);assert.deepEqual(await run('window.supporterSession.snapshot().history'),history);
      await result([{label:'结果',text:'失败定位不影响生成'}]);assert.equal(await read('candidate'),'失败定位不影响生成');
    });
    await test('late different-request locate results and errors cannot replace current controls',async()=>{
      await clear();locateAutomatic=false;await type('/loc:window');await key('Enter');const first=commands.filter(item=>item.type==='locate-window').at(-1);
      await type('/loc:window');await key('Enter');const current=commands.filter(item=>item.type==='locate-window').at(-1);assert.notEqual(first.request_id,current.request_id);
      emit({type:'locate-results',request_id:current.request_id,controls:[locateControls[2]],title:'当前窗口',limited:false});await sleep(30);assert.ok((await read('options')).includes('搜索输入框'));
      emit({type:'locate-results',request_id:first.request_id,controls:[{...locateControls[0],name:'不应出现的旧区域'}],title:'旧窗口'});emit({type:'locate-error',request_id:first.request_id,message:'不应显示的旧错误'});await sleep(35);
      assert.ok(!(await read('options')).includes('不应出现'));assert.ok((await read('options')).includes('搜索输入框'));assert.ok(!(await read('status')).includes('旧错误'));assert.equal(await run('window.supporterSession.snapshot().menu'),'location');
    });
    await test('empty or limited location lists explain their availability without unsafe fallback',async()=>{
      await clear();locateAutomatic=false;await type('/loc:window');await key('Enter');let request=commands.filter(item=>item.type==='locate-window').at(-1);
      emit({type:'locate-results',request_id:request.request_id,controls:[],title:'无编辑器窗口'});await sleep(30);assert.ok((await read('status')).includes('未找到'));const count=commands.filter(item=>item.type==='locate-select').length;await key('Enter');assert.equal(commands.filter(item=>item.type==='locate-select').length,count);
      await type('/loc:window');await key('Enter');request=commands.filter(item=>item.type==='locate-window').at(-1);emit({type:'locate-results',request_id:request.request_id,controls:[locateControls[0]],title:'限量窗口',limited:true});await sleep(30);assert.ok((await read('status')).includes('列表已限量'));
    });
    await test('location menu survives blur and settings round trip with its selected controls',async()=>{
      await clear();await type('定位前的对话');await key('Enter');await result([{label:'候选',text:'保持候选'}]);await type('/loc:window');await key('Enter');await waitFor(async()=>await run('window.supporterSession.snapshot().locations.length===3'),'no location list');await type('PowerShell');
      win.emit('blur');await sleep(70);await wake(true);assert.equal(await run('window.supporterSession.snapshot().menu'),'location');assert.equal(await run('document.getElementById("prompt").value'),'PowerShell');assert.equal(await run('document.querySelectorAll("#options .option").length'),1);
      await key(',',{ctrlKey:true});await waitFor(async()=>!win.webContents.isLoading()&&await run('Boolean(document.getElementById("form"))'),'settings did not open',5000);await run('document.getElementById("windowClose").click()');await waitFor(async()=>win.webContents.getURL().endsWith('index.html')&&!win.webContents.isLoading(),'settings did not return',4000);await wake(true);
      assert.equal(await run('window.supporterSession.snapshot().menu'),'location');assert.equal(await run('document.getElementById("prompt").value'),'PowerShell');assert.ok((await read('options')).includes('PowerShell'));assert.equal(await read('candidate'),'保持候选');await key('Enter');await waitFor(()=>win.isVisible(),'restored location selection did not return');assert.equal(await read('original'),'Get-Location');
    });
    await test('Esc while locating clears context and ignores the outstanding detection response',async()=>{
      await clear();await type('需要关闭的上下文');await key('Enter');locateAutomatic=false;await type('/loc:window');await key('Enter');const request=commands.filter(item=>item.type==='locate-window').at(-1);await key('Escape');await sleep(150);assert.equal(win.isVisible(),false);
      emit({type:'locate-results',request_id:request.request_id,controls:locateControls,title:'关闭后迟到'});emit({type:'locate-error',request_id:request.request_id,message:'关闭后的错误'});await sleep(40);assert.equal(win.isVisible(),false);
      await wake(false);assert.equal(await run('window.supporterSession.snapshot().menu'),null);assert.deepEqual(await run('window.supporterSession.snapshot().history'),[]);assert.deepEqual(await run('window.supporterSession.snapshot().locations'),[]);assert.equal(await run('document.getElementById("result").hidden'),true);
    });
    await test('late capture and locate wakes after Esc stay hidden; the next hotkey still wakes normally',async()=>{
      await clear();await type('已经关闭的上一轮');await key('Enter');await result([{label:'旧候选',text:'关闭后不应恢复'}]);await key('Escape');await sleep(150);assert.equal(win.isVisible(),false);
      const oldCapture=commands.filter(item=>item.type==='capture').at(-1);
      for(const resume of [true,false]){
        emit({type:'wake',request_id:resume?'loc-old-after-close':oldCapture.request_id,target:{x:450,y:700,scope:'editor',context:'不应被迟到唤醒恢复的旧内容',source:'uia-caret-active',terminal:false},resume});await sleep(50);
        assert.equal(win.isVisible(),false,'unsolicited '+(resume?'locate':'capture')+' wake must not reopen a closed context');
        assert.deepEqual(await run('window.supporterSession.snapshot().history'),[]);assert.deepEqual(await run('window.supporterSession.snapshot().choices'),[]);
      }
      currentTarget={scope:'editor',context:'下一次正常捕获的位置',source:'uia-caret-active',terminal:false};await wake(false);
      assert.equal(win.isVisible(),true,'next deliberate hotkey must still work');assert.equal(await read('original'),'下一次正常捕获的位置');assert.deepEqual(await run('window.supporterSession.snapshot().history'),[]);assert.equal(await run('document.getElementById("result").hidden'),true);
      await type('新上下文继续正常使用');await key('Enter');await result([{label:'新候选',text:'重新唤醒后可以正常生成'}]);assert.equal(await read('candidate'),'重新唤醒后可以正常生成');
    });
    await test('old wake and capture errors cannot hijack the next pending capture request',async()=>{
      await clear();const old=commands.filter(item=>item.type==='capture').at(-1);await key('Escape');await sleep(150);captureAutomatic=false;
      try{
        const count=commands.filter(item=>item.type==='capture').length;keys.get('Control+Space')();await waitFor(()=>commands.filter(item=>item.type==='capture').length>count,'new capture was not requested');const latest=commands.filter(item=>item.type==='capture').at(-1);
        assert.equal(typeof latest.request_id,'string');assert.notEqual(latest.request_id,old.request_id);
        emit({type:'wake',request_id:old.request_id,target:{x:450,y:700,scope:'editor',context:'不该劫持新唤醒的旧位置',source:'uia-caret-active'},resume:false});
        emit({type:'error',capture_request_id:old.request_id,message:'旧捕获错误不该打断当前捕获'});await sleep(70);assert.equal(win.isVisible(),false);
        const target={x:470,y:710,scope:'editor',context:'等待后正确捕获的输入位置',source:'uia-caret-active',terminal:false};
        emit({type:'wake',request_id:latest.request_id,target,resume:false});await waitFor(()=>win.isVisible(),'matching pending capture did not wake');await sleep(40);
        assert.equal(await read('original'),target.context);assert.ok(!(await read('status')).includes('旧捕获错误'));assert.deepEqual(await run('window.supporterSession.snapshot().history'),[]);
      }finally{captureAutomatic=true;}
    });
    await test('unconfigured Codex Luna defaults to low effort in both overlay and settings',async()=>{
      await clear();await installSettings({...inventory.settings,backend:'codex',models:{...inventory.settings.models,codex:'gpt-6-luna'},reasoning:{}});
      assert.ok((await read('effort')).includes('低'));await type('快速补写请求');await key('Enter');assert.equal(activeGenerate.model,'gpt-6-luna');assert.equal(activeGenerate.reasoning,'low');await result([{label:'结果',text:'低强度生成'}]);
      await showSettingsPage();try{assert.equal(await run('document.getElementById("reasoning").value'),'low','saving unrelated preferences must not silently change Luna back to CLI default');}finally{await returnFromSettings();}
    });
    await test('explicit Luna default effort remains default across model switches and settings',async()=>{
      await clear();await installSettings({...inventory.settings,backend:'codex',models:{...inventory.settings.models,codex:'gpt-6-luna'},reasoning:{'codex|gpt-6-luna':'default'}});
      assert.ok((await read('effort')).includes('默认'));await type('/model:gpt-6.1-terra');await key('Enter');await type('/model:gpt-6-luna');await key('Enter');assert.ok((await read('effort')).includes('默认'));
      await type('使用用户显式默认');await key('Enter');assert.equal(activeGenerate.reasoning,'default');await result([{label:'结果',text:'保留显式设置'}]);
      await showSettingsPage();try{assert.equal(await run('document.getElementById("reasoning").value'),'default');}finally{await returnFromSettings();}
    });
    await test('other models and Luna without low capability are not forced to low',async()=>{
      await clear();await installSettings({...inventory.settings,backend:'codex',models:{...inventory.settings.models,codex:'gpt-6.1-terra'},reasoning:{}});
      assert.ok((await read('effort')).includes('默认'));await type('普通模型请求');await key('Enter');assert.equal(activeGenerate.reasoning,'default');await result([{label:'结果',text:'普通默认'}]);
      await showSettingsPage();try{assert.equal(await run('document.getElementById("reasoning").value'),'default');}finally{await returnFromSettings();}
      const supported=inventory.backends[0].reasoning['gpt-6-luna'];inventory.backends[0].reasoning['gpt-6-luna']=['high'];
      try{
        await installSettings({...inventory.settings,backend:'codex',models:{...inventory.settings.models,codex:'gpt-6-luna'},reasoning:{}});assert.ok((await read('effort')).includes('默认'));await type('不支持 low 的 Luna');await key('Enter');assert.equal(activeGenerate.reasoning,'default');await result([{label:'结果',text:'能力匹配'}]);
        await showSettingsPage();try{assert.equal(await run('document.getElementById("reasoning").value'),'default');}finally{await returnFromSettings();}
      }finally{inventory.backends[0].reasoning['gpt-6-luna']=supported;emit({type:'inventory',...inventory});await sleep(30);}
    });
    await test('AI settings show all connection choices and proxy row follows mode',async()=>{
      await clear();const next={...inventory.settings};delete next.codexConnection;await installSettings(next);await showSettingsPage();
      try{
        await run('document.querySelector("[data-page=ai]").click()');assert.deepEqual(await run('[...document.getElementById("codexConnection").options].map(option=>option.value)'),['inherit','direct','proxy']);assert.equal(await run('document.getElementById("codexConnection").value'),'inherit');
        assert.ok(await run('document.getElementById("codexConnection").getBoundingClientRect().height>0'));
        for(const mode of ['proxy','direct','inherit']){await run('document.getElementById("codexConnection").value='+JSON.stringify(mode)+';document.getElementById("codexConnection").dispatchEvent(new Event("change",{bubbles:true}))');assert.equal(await run('document.getElementById("codexProxyRow").hidden'),mode!=='proxy');}
      }finally{await returnFromSettings();}
    });
    await test('connection inherit direct and proxy save and reopen without starting an AI request',async()=>{
      await clear();const generated=commands.filter(item=>item.type==='generate').length;
      for(const mode of ['proxy','direct','inherit']){
        const proxyUrl=mode==='proxy'?'http://127.0.0.1:17777':'';await showSettingsPage();await run('document.querySelector("[data-page=ai]").click();document.getElementById("codexConnection").value='+JSON.stringify(mode)+';document.getElementById("codexConnection").dispatchEvent(new Event("change",{bubbles:true}));document.getElementById("codexProxy").value="  http://127.0.0.1:17777  "');
        await returnFromSettings(true);assert.deepEqual(inventory.settings.codexConnection,{mode,proxyUrl});await showSettingsPage();
        try{assert.equal(await run('document.getElementById("codexConnection").value'),mode);assert.equal(await run('document.getElementById("codexProxy").value'),proxyUrl);assert.equal(await run('document.getElementById("codexProxyRow").hidden'),mode!=='proxy');}finally{await returnFromSettings();}
      }
      assert.equal(commands.filter(item=>item.type==='generate').length,generated);
    });
    await test('changing only proxy URL preserves chosen models effort and appearance',async()=>{
      await clear();const appearance={theme:'light',accent:'#90d9be',fontSize:16,width:640,opacity:.94,radius:24,showProcess:true,motion:false,glass:true,glassOpacity:.8};
      const models={codex:'gpt-6.1-terra',opencode:'provider/model:tag'};const reasoning={'codex|gpt-6.1-terra':'high','codex|gpt-6-luna':'default'};
      await installSettings({...inventory.settings,backend:'codex',models,reasoning,appearance,codexConnection:{mode:'proxy',proxyUrl:'http://127.0.0.1:17777'}});await showSettingsPage();await run('document.getElementById("codexProxy").value=" http://127.0.0.1:17778 "');await returnFromSettings(true);
      assert.deepEqual(inventory.settings.models,models);assert.deepEqual(inventory.settings.reasoning,reasoning);assert.deepEqual(inventory.settings.appearance,appearance);assert.deepEqual(inventory.settings.codexConnection,{mode:'proxy',proxyUrl:'http://127.0.0.1:17778'});
      assert.equal(await read('model'),'gpt-6.1-terra');assert.ok((await read('effort')).includes('高'));assert.equal(await run('document.documentElement.dataset.theme'),'light');
      await type('新连接配置后的下一次请求');await key('Enter');assert.equal(activeGenerate.model,'gpt-6.1-terra');assert.equal(activeGenerate.reasoning,'high');await result([{label:'结果',text:'连接与模型偏好独立'}]);
    });
    await test('changing a connection preserves existing custom numeric appearance values',async()=>{
      await clear();const appearance={theme:'dark',accent:'#91bfff',fontSize:15,width:560,opacity:.93,radius:12,showProcess:true,motion:false,glass:true,glassOpacity:.8};
      await installSettings({...inventory.settings,appearance,codexConnection:{mode:'inherit',proxyUrl:''}});await showSettingsPage();
      for(const [id,value] of [['fontSize',15],['width',560],['radius',12]]){
        assert.equal(await run('document.getElementById('+JSON.stringify(id)+').value'),String(value),'existing custom '+id+' must remain selectable');
        assert.ok(await run('[...document.getElementById('+JSON.stringify(id)+').options].some(option=>option.value==='+JSON.stringify(String(value))+')'));
      }
      await run('document.getElementById("codexConnection").value="proxy";document.getElementById("codexConnection").dispatchEvent(new Event("change",{bubbles:true}));document.getElementById("codexProxy").value="http://127.0.0.1:17779"');await returnFromSettings(true);
      assert.deepEqual(inventory.settings.appearance,appearance);assert.deepEqual(inventory.settings.codexConnection,{mode:'proxy',proxyUrl:'http://127.0.0.1:17779'});
      await showSettingsPage();try{for(const [id,value] of [['fontSize',15],['width',560],['radius',12]])assert.equal(await run('document.getElementById('+JSON.stringify(id)+').value'),String(value));}finally{await returnFromSettings();}
      assert.deepEqual(inventory.settings.appearance,appearance);
    });
    await test('wake and backend model reasoning selectors request lightweight inventory detection',async()=>{
      await clear();let before=commands.filter(item=>item.type==='refresh').length;await wake(true);assert.ok(commands.filter(item=>item.type==='refresh').length>before);assert.equal(commands.filter(item=>item.type==='refresh').at(-1).force,false);
      for(const shortcut of ['b','m','r']){before=commands.filter(item=>item.type==='refresh').length;await key(shortcut,{ctrlKey:true});await sleep(20);assert.ok(commands.filter(item=>item.type==='refresh').length>before,shortcut+' selector must trigger detection');assert.equal(commands.filter(item=>item.type==='refresh').at(-1).force,false);}
    });
    await test('opened backend menu adds and removes dynamically detected plugins immediately',async()=>{
      await clear();const baseline=clone(inventory);const plugin={name:'fixture-plugin',version:'plugin fixture',error:'',models:['fixture-fast','fixture-deep'],reasoning:{'fixture-fast':['low'],'fixture-deep':['high']}};
      try{
        await key('b',{ctrlKey:true});await publishInventory([...baseline.backends,plugin],baseline.settings,'已发现 fixture-plugin');assert.ok((await read('options')).includes('fixture-plugin'));assert.ok((await read('status')).includes('已发现 fixture-plugin'));
        await publishInventory([baseline.backends[0],plugin],baseline.settings,'opencode 已移除');assert.ok(!(await read('options')).includes('opencode'));assert.ok((await read('options')).includes('fixture-plugin'));assert.equal(await run('window.supporterSession.snapshot().menu'),'backend');
        await type('fixture-plugin');await key('Enter');assert.equal(await read('backend'),'fixture-plugin');await key('m',{ctrlKey:true});assert.ok((await read('options')).includes('fixture-fast'));assert.ok((await read('options')).includes('fixture-deep'));
      }finally{await publishInventory(baseline.backends,baseline.settings);}
    });
    await test('open model and reasoning lists update when detected capabilities change',async()=>{
      await clear();const baseline=clone(inventory);
      try{
        await installSettings({...baseline.settings,backend:'codex',models:{...baseline.settings.models,codex:'gpt-6-luna'},reasoning:{}});await key('m',{ctrlKey:true});const changed=clone(baseline.backends);changed[0].models=['gpt-6-luna','fixture-new-model'];changed[0].reasoning={'gpt-6-luna':['minimal','high'],'fixture-new-model':['low']};
        await publishInventory(changed,inventory.settings);assert.ok((await read('options')).includes('fixture-new-model'));assert.ok(!(await read('options')).includes('gpt-6.1-terra'));
        await key('r',{ctrlKey:true});assert.ok((await read('options')).includes('minimal'));assert.ok(!(await run('[...document.querySelectorAll("#options .option > span")].map(item=>item.textContent)')).includes('low'));
        changed[0].reasoning['gpt-6-luna']=['low','max'];await publishInventory(changed,inventory.settings);assert.ok((await read('options')).includes('max'));assert.ok(!(await read('options')).includes('minimal'));
      }finally{await publishInventory(baseline.backends,baseline.settings);}
    });
    await test('automatic backend fallback preserves conversation candidate and draft',async()=>{
      await clear();const baseline=clone(inventory);
      try{
        await installSettings({...baseline.settings,backend:'codex',models:{...baseline.settings.models,codex:'gpt-6-luna'}});await type('切换前的对话');await key('Enter');await result([{label:'候选',text:'自动切换后保留的候选'}]);await type('自动更新不能清掉草稿');const state=await run('window.supporterSession.snapshot()');
        const cancelled=commands.filter(item=>item.type==='cancel-generation').length,generated=commands.filter(item=>item.type==='generate').length;
        const nextSettings={...inventory.settings,backend:'opencode',models:{...inventory.settings.models,opencode:'provider/model:tag'}};await publishInventory([baseline.backends[1]],nextSettings,'Codex 已不可用，切换到 opencode');
        assert.equal(await read('backend'),'opencode');assert.equal(await read('candidate'),'自动切换后保留的候选');assert.equal(await run('document.getElementById("prompt").value'),state.draft);assert.deepEqual(await run('window.supporterSession.snapshot().history'),state.history);
        assert.equal(commands.filter(item=>item.type==='cancel-generation').length,cancelled);assert.equal(commands.filter(item=>item.type==='generate').length,generated);assert.ok((await read('status')).includes('切换到 opencode'));
      }finally{await publishInventory(baseline.backends,baseline.settings);}
    });
    await test('automatic inventory fallback cannot cancel or restart an active generation',async()=>{
      await clear();const baseline=clone(inventory);
      try{
        await installSettings({...baseline.settings,backend:'codex',models:{...baseline.settings.models,codex:'gpt-6-luna'}});await type('后台自动检测期间继续生成');await key('Enter');await type('原请求未完成时的草稿');const state=await run('window.supporterSession.snapshot()');const request=activeGenerate;
        const cancelled=commands.filter(item=>item.type==='cancel-generation').length,generated=commands.filter(item=>item.type==='generate').length;
        await publishInventory([baseline.backends[1]],{...inventory.settings,backend:'opencode'},'检测后下次请求改用 opencode');
        assert.equal(await run('document.getElementById("busy").hidden'),false);assert.equal(await run('window.supporterSession.snapshot().activeClientId'),request.client_request_id);assert.equal(await run('document.getElementById("prompt").value'),state.draft);assert.deepEqual(await run('window.supporterSession.snapshot().history'),state.history);
        assert.equal(commands.filter(item=>item.type==='cancel-generation').length,cancelled);assert.equal(commands.filter(item=>item.type==='generate').length,generated);
        await result([{label:'原请求完成',text:'原 Codex 请求正常返回'}]);assert.equal(await read('candidate'),'原 Codex 请求正常返回');
        await type('下一次请求使用新后端');await key('Enter');assert.equal(activeGenerate.backend,'opencode');await result([{label:'新后端完成',text:'新后端正常使用'}]);
      }finally{await publishInventory(baseline.backends,baseline.settings);}
    });
    await test('no detected backend shows an empty state and preserves unsent prompt without generating',async()=>{
      await clear();const baseline=clone(inventory);
      try{
        for(const unavailable of [[],baseline.backends.map(item=>({...item,error:'fixture: CLI not installed'}))]){
          await clear();await publishInventory(unavailable,{...baseline.settings,backend:''},'没有可用的 AI CLI');const count=commands.filter(item=>item.type==='generate').length;await type('安装后继续使用的请求');await key('Enter');
          assert.equal(commands.filter(item=>item.type==='generate').length,count);assert.equal(await run('document.getElementById("prompt").value'),'安装后继续使用的请求');assert.equal(await read('backend'),'无可用 CLI');assert.ok((await read('status')).includes('CLI'));assert.equal(await run('document.getElementById("busy").hidden'),true);
          await key('b',{ctrlKey:true});assert.equal(await run('document.querySelectorAll("#options .option").length'),0);assert.ok((await read('options')).includes('没有匹配项'));
        }
      }finally{await publishInventory(baseline.backends,baseline.settings);}
    });
    await test('settings inventory updates capabilities without overwriting unsaved appearance or connection',async()=>{
      await clear();const baseline=clone(inventory);
      try{
        await showSettingsPage();await run('document.getElementById("theme").value="light";document.getElementById("fontSize").value="18";document.getElementById("theme").dispatchEvent(new Event("input",{bubbles:true}));document.getElementById("codexConnection").value="proxy";document.getElementById("codexConnection").dispatchEvent(new Event("change",{bubbles:true}));document.getElementById("codexProxy").value="http://127.0.0.1:17780";document.getElementById("model").value="gpt-6-luna";document.getElementById("model").dispatchEvent(new Event("change",{bubbles:true}));document.getElementById("reasoning").value="high"');
        const changed=clone(baseline.backends);changed[0].models.push('fixture-model-added-while-editing');changed.push({name:'fixture-settings-plugin',version:'fixture',error:'',models:['fixture-one'],reasoning:{}});await publishInventory(changed,baseline.settings,'检测到新的后端与模型');
        assert.equal(await run('document.getElementById("theme").value'),'light');assert.equal(await run('document.getElementById("fontSize").value'),'18');assert.equal(await run('document.getElementById("codexConnection").value'),'proxy');assert.equal(await run('document.getElementById("codexProxy").value'),'http://127.0.0.1:17780');assert.equal(await run('document.getElementById("codexProxyRow").hidden'),false);
        assert.equal(await run('document.getElementById("model").value'),'gpt-6-luna');assert.equal(await run('document.getElementById("reasoning").value'),'high');
        assert.ok((await run('[...document.getElementById("backend").options].map(option=>option.value)')).includes('fixture-settings-plugin'));assert.ok((await run('[...document.getElementById("model").options].map(option=>option.value)')).includes('fixture-model-added-while-editing'));
        await returnFromSettings(true);assert.equal(inventory.settings.appearance.theme,'light');assert.equal(inventory.settings.appearance.fontSize,18);assert.deepEqual(inventory.settings.codexConnection,{mode:'proxy',proxyUrl:'http://127.0.0.1:17780'});assert.equal(inventory.settings.models.codex,'gpt-6-luna');assert.equal(inventory.settings.reasoning['codex|gpt-6-luna'],'high');
      }finally{if(win.webContents.getURL().endsWith('settings.html'))await returnFromSettings();await publishInventory(baseline.backends,baseline.settings);}
    });
    await test('glass controls preview the native switch and cancellation restores saved appearance',async()=>{
      await clear();const saved={...inventory.settings.appearance,opacity:1,glass:true,glassOpacity:.8};await installSettings({...inventory.settings,appearance:saved});await showSettingsPage();
      assert.equal(await run('document.getElementById("glass").checked'),true);assert.equal(await run('document.getElementById("glassOpacity").min'),'50');assert.equal(await run('document.getElementById("glassOpacity").max'),'96');assert.equal(await run('document.getElementById("glassOpacity").value'),'80');
      const calls=glassCalls.length;await run('document.getElementById("glass").checked=false;document.getElementById("glass").dispatchEvent(new Event("input",{bubbles:true}))');await sleep(50);
      assert.equal(await run('document.documentElement.dataset.glass'),'false');assert.equal(await run('document.documentElement.style.getPropertyValue("--surface-opacity")'),'1');assert.equal(win.getOpacity(),1);
      if(hostGlassApi)assert.ok(glassCalls.slice(calls).includes('none'),'native acrylic must be disabled during preview');
      await returnFromSettings();assert.equal(await run('document.documentElement.dataset.glass'),'true');assert.deepEqual(inventory.settings.appearance,saved);if(hostGlassApi)assert.equal(glassCalls.at(-1),'acrylic');
    });
    await test('glass concentration previews background alpha without fading text and saves the chosen value',async()=>{
      await clear();await installSettings({...inventory.settings,appearance:{...inventory.settings.appearance,opacity:1,glass:true,glassOpacity:.8}});await showSettingsPage();await run('window.supporter.onEvent(event=>{if(event.type==="appearance")window.__lastAppearance=event});void 0');
      for(const percent of [50,96,73]){
        await run('document.getElementById("glassOpacity").value='+percent+';document.getElementById("glassOpacity").dispatchEvent(new Event("input",{bubbles:true}))');await waitFor(async()=>await run('window.__lastAppearance?.appearance.glassOpacity==='+percent+'/100'),'glass preview event did not arrive');
        const state=await run('({native:window.__lastAppearance.glassNative,alpha:Number(document.documentElement.style.getPropertyValue("--surface-opacity")),sampleOpacity:getComputedStyle(document.getElementById("sample")).opacity,bodyOpacity:getComputedStyle(document.body).opacity,rootOpacity:getComputedStyle(document.documentElement).opacity})');
        assert.equal(state.alpha,state.native?percent/100:Math.max(.9,percent/100));assert.equal(await read('glassOpacityValue'),percent+'%');assert.equal(state.sampleOpacity,'1');assert.equal(state.bodyOpacity,'1');assert.equal(state.rootOpacity,'1');assert.equal(win.getOpacity(),1);
      }
      await returnFromSettings(true);assert.equal(inventory.settings.appearance.glass,true);assert.equal(inventory.settings.appearance.glassOpacity,.73);assert.equal(await run('getComputedStyle(document.getElementById("prompt")).opacity'),'1');assert.equal(await run('getComputedStyle(document.getElementById("card")).opacity'),'1');
    });
    await test('glass and concentration persist on reopen and disabled glass restores the ordinary surface',async()=>{
      await clear();await installSettings({...inventory.settings,appearance:{...inventory.settings.appearance,opacity:1,glass:true,glassOpacity:.73}});await showSettingsPage();assert.equal(await run('document.getElementById("glass").checked'),true);assert.equal(await run('document.getElementById("glassOpacity").value'),'73');
      await run('document.getElementById("glass").checked=false;document.getElementById("glass").dispatchEvent(new Event("input",{bubbles:true}))');await returnFromSettings(true);
      assert.equal(inventory.settings.appearance.glass,false);assert.equal(inventory.settings.appearance.glassOpacity,.73);assert.equal(await run('document.documentElement.dataset.glass'),'false');assert.equal(await run('document.documentElement.style.getPropertyValue("--surface-opacity")'),'1');assert.equal(await run('getComputedStyle(document.getElementById("card")).backdropFilter'),'none');
      if(hostGlassApi)assert.equal(glassCalls.at(-1),'none');await showSettingsPage();try{assert.equal(await run('document.getElementById("glass").checked'),false);assert.equal(await run('document.getElementById("glassOpacity").value'),'73');}finally{await returnFromSettings();}
    });
    await test('failed glass save and cancellation restore the original surface while keeping active generation',async()=>{
      await clear();const saved={...inventory.settings.appearance,opacity:1,glass:false,glassOpacity:.88};await installSettings({...inventory.settings,appearance:saved});await type('调整背景时继续生成');await key('Enter');await type('未发送的外观测试草稿');const state=await run('window.supporterSession.snapshot()');const cancelled=commands.filter(item=>item.type==='cancel-generation').length,generated=commands.filter(item=>item.type==='generate').length;
      await showSettingsPage();await run('document.getElementById("glass").checked=true;document.getElementById("glassOpacity").value="64";document.getElementById("glass").dispatchEvent(new Event("input",{bubbles:true}));document.getElementById("glassOpacity").dispatchEvent(new Event("input",{bubbles:true}))');await sleep(40);assert.equal(await run('document.documentElement.dataset.glass'),'true');persistError=true;
      try{await run('document.getElementById("save").click()');await waitFor(async()=>(await read('feedback')).includes('不可写'),'glass save failure not shown');assert.equal(await run('document.getElementById("save").disabled'),false);}finally{persistError=false;await returnFromSettings();}
      assert.deepEqual(inventory.settings.appearance,saved);assert.equal(await run('document.documentElement.dataset.glass'),'false');assert.equal(await run('document.documentElement.style.getPropertyValue("--surface-opacity")'),'1');assert.equal(await run('document.getElementById("busy").hidden'),false);assert.equal(await run('document.getElementById("prompt").value'),state.draft);assert.deepEqual(await run('window.supporterSession.snapshot().history'),state.history);
      assert.equal(commands.filter(item=>item.type==='cancel-generation').length,cancelled);assert.equal(commands.filter(item=>item.type==='generate').length,generated);await result([{label:'结果',text:'外观调整后原请求正常完成'}]);assert.equal(await read('candidate'),'外观调整后原请求正常完成');
    });
    await test('background inventory updates preserve the unsaved glass preview as well as its controls',async()=>{
      await clear();const baseline=clone(inventory);await installSettings({...inventory.settings,appearance:{...inventory.settings.appearance,opacity:1,glass:true,glassOpacity:.8}});await showSettingsPage();
      try{
        await run('document.getElementById("glass").checked=false;document.getElementById("glassOpacity").value="61";document.getElementById("glass").dispatchEvent(new Event("input",{bubbles:true}));document.getElementById("glassOpacity").dispatchEvent(new Event("input",{bubbles:true}))');await sleep(40);assert.equal(await run('document.documentElement.dataset.glass'),'false');
        const updated=clone(inventory.backends);updated[0].version='fixture background refresh';await publishInventory(updated,inventory.settings,'后台目录刷新');assert.equal(await run('document.getElementById("glass").checked'),false);assert.equal(await run('document.getElementById("glassOpacity").value'),'61');
        assert.equal(await run('document.documentElement.dataset.glass'),'false','backend refresh must not visually re-enable an unsaved disabled-glass preview');assert.equal(await run('document.documentElement.style.getPropertyValue("--surface-opacity")'),'1');
      }finally{await returnFromSettings();await publishInventory(baseline.backends,baseline.settings);}
    });
    report.passed=report.tests.every(t=>t.passed);
  }catch(error){report.harnessError=String(error.stack||error);}
  finally{report.running=false;fs.writeFileSync(reportFile,JSON.stringify(report,null,2));console.log(JSON.stringify(report));app.quit();}
});
