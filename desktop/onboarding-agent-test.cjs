/* Real first-run Electron routes with a fake private worker and isolated profile. */
const electron=require('electron');
const {app,BrowserWindow}=electron;
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {PassThrough,Writable}=require('node:stream');const {EventEmitter}=require('node:events');
const root=path.resolve(__dirname,'..');
const dataDirectory=fs.mkdtempSync(path.join(root,'.runtime','onboarding-data-agent-'));
process.env.SUPPORTER_DATA_DIR=dataDirectory;process.env.SUPPORTER_COMPLETION_ROOT=path.join(dataDirectory,'completions','user');
const chromiumDirectory=path.join(dataDirectory,'chromium');fs.mkdirSync(chromiumDirectory,{recursive:true});app.setPath('userData',chromiumDirectory);app.setPath('sessionData',chromiumDirectory);
const settingsFile=path.join(dataDirectory,'settings.json'),reportFile=path.join(root,'.runtime','onboarding-agent-report.json');
const report={runId:new Date().toISOString(),passed:false,running:true,tests:[]};const commands=[],keys=new Map(),links=[];
let trayTemplate=[],persistFailure=false,blockedHotkey=null,workerLaunch=null,settings={},suspended=false,win;
fs.writeFileSync(reportFile,JSON.stringify(report,null,2));
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
electron.globalShortcut.register=(key,fn)=>{if(key===blockedHotkey)return false;keys.set(key,fn);return true;};electron.globalShortcut.unregisterAll=()=>keys.clear();
electron.shell.openExternal=url=>{links.push(url);return Promise.resolve();};
const buildMenu=electron.Menu.buildFromTemplate.bind(electron.Menu);electron.Menu.buildFromTemplate=template=>{trayTemplate=template;return buildMenu(template);};
app.setLoginItemSettings=()=>{throw new Error('Onboarding tests must not change Windows login settings');};
const worker=new EventEmitter();worker.stdout=new PassThrough();worker.stderr=new PassThrough();worker.killed=false;worker.kill=()=>{worker.killed=true;worker.emit('exit',0);};
const emit=event=>worker.stdout.write(JSON.stringify(event)+'\n');
const backends=[
  {name:'codex',adapter:'codex',error:'',version:'fixture Codex',models:['gpt-6.1-terra','gpt-6-luna'],reasoning:{'gpt-6-luna':['low','high'],'gpt-6.1-terra':['high']}},
  {name:'opencode',error:'',version:'fixture OpenCode',models:['fixture-fast','fixture-deep'],reasoning:{'fixture-fast':['low'],'fixture-deep':['high']}},
  {name:'missing-plugin',error:'fixture: not installed',status:'missing',version:'',models:[],reasoning:{}}
];
function command(data){
  commands.push(data);
  if(data.type==='suspend')suspended=true;
  if(data.type==='cancel')suspended=false;
  if(data.type==='settings'&&data.request_id)setTimeout(()=>{
    if(persistFailure){emit({type:'settings-persist-error',request_id:data.request_id,message:'fixture: 保存目录不可写'});return;}
    settings=data.settings;fs.writeFileSync(settingsFile,JSON.stringify(settings));emit({type:'settings-persisted',request_id:data.request_id});
  },45);
  if(data.type==='capture'){emit({type:'wake',request_id:data.request_id,target:{x:500,y:720,scope:'editor',context:'欢迎流程后的原编辑内容',source:'uia-caret',terminal:false},resume:suspended});suspended=false;}
}
let buffer='';worker.stdin=new Writable({write(chunk,encoding,done){buffer+=chunk;let end;while((end=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,end);buffer=buffer.slice(end+1);if(line)command(JSON.parse(line));}done();}});
require('node:child_process').spawn=(file,args,options)=>{
  assert.ok(args.includes('supporter.service'),'test must never launch a real CLI');assert.equal(options.env.SUPPORTER_DATA_DIR,dataDirectory);workerLaunch={file,args,cwd:options.cwd,dataRoot:options.env.SUPPORTER_DATA_DIR};
  settings=JSON.parse(fs.readFileSync(settingsFile,'utf8'));setTimeout(()=>emit({type:'ready',error:null}),30);return worker;
};
require('./main.cjs');
app.on('before-quit',()=>{if(report.running){report.running=false;report.harnessError='Application quit before onboarding regression completed';fs.writeFileSync(reportFile,JSON.stringify(report,null,2));}});
const run=code=>win.webContents.executeJavaScript(code);
const read=id=>run('document.getElementById('+JSON.stringify(id)+').textContent');
const value=id=>run('document.getElementById('+JSON.stringify(id)+').value');
const key=(key,extra={})=>run('document.dispatchEvent(new KeyboardEvent("keydown",'+JSON.stringify({key,bubbles:true,cancelable:true,...extra})+'))');
async function waitFor(check,message,ms=4000){const end=Date.now()+ms;while(Date.now()<end){if(await check())return;await sleep(20);}throw new Error(message);}
async function test(name,fn){try{await fn();report.tests.push({name,passed:true});}catch(error){report.tests.push({name,passed:false,error:String(error.stack||error)});}fs.writeFileSync(reportFile,JSON.stringify(report,null,2));}
async function welcome(){await waitFor(async()=>!win.webContents.isLoading()&&await run('Boolean(document.getElementById("welcomeForm"))'),'welcome route did not load');}
async function assistant(){await waitFor(async()=>!win.webContents.isLoading()&&await run('Boolean(document.getElementById("prompt"))'),'assistant route did not return');}
async function publish(found=backends){emit({type:'inventory',backends:found,settings});await sleep(70);}
async function reopen(){const item=trayTemplate.find(item=>item.label==='入门与环境检测');assert.ok(item,'tray must expose onboarding');await item.click();await welcome();await sleep(40);}
app.whenReady().then(async()=>{
  try{
    await waitFor(()=>BrowserWindow.getAllWindows().length&&keys.size,'main window or hotkey missing');win=BrowserWindow.getAllWindows()[0];win.setFocusable(false);await welcome();
    await test('fresh isolated installation opens a painted first-run welcome without CLI detection yet',async()=>{
      assert.equal(win.isVisible(),true);assert.equal(settings.onboarding.completed,false);assert.ok((await read('welcomeDetection')).includes('检测'));assert.equal(await run('document.getElementById("welcomeFinish").disabled'),true);assert.equal(await run('document.getElementById("welcomeLater").disabled'),false);
      const image=await win.webContents.capturePage();const bitmap=image.toBitmap(),colors=new Set();for(let i=0;i<bitmap.length;i+=16)colors.add(bitmap.readUInt32LE(i));assert.ok(colors.size>50,'welcome must paint real content');fs.writeFileSync(path.join(root,'.runtime','onboarding-agent.png'),image.toPNG());
    });
    await test('F5 requests detection and CtrlSpace stays in welcome without capturing another app',async()=>{
      const refresh=commands.filter(item=>item.type==='refresh').length,captures=commands.filter(item=>item.type==='capture').length;await key('F5');await sleep(25);assert.equal(commands.filter(item=>item.type==='refresh').length,refresh+1);
      keys.get('Control+Space')();await sleep(30);assert.equal(commands.filter(item=>item.type==='capture').length,captures);assert.equal(win.webContents.getURL().endsWith('onboarding.html'),true);
    });
    await test('no installed CLI and checking CLI states keep finish disabled while allowing later setup',async()=>{
      await publish([backends[2]]);assert.ok((await read('welcomeDetection')).includes('尚未'));assert.equal(await run('document.getElementById("welcomeBackend").disabled'),true);assert.equal(await run('document.getElementById("welcomeFinish").disabled'),true);assert.equal(await run('document.getElementById("welcomeLater").disabled'),false);
      await publish([{name:'codex',status:'checking',error:'正在检测 fixture CLI',models:[],reasoning:{}}]);assert.equal(await run('document.getElementById("welcomeFinish").disabled'),true);assert.ok((await read('welcomeTools')).includes('正在检测'));
    });
    await test('detected backends populate choices and unconfigured Codex prefers Luna low effort',async()=>{
      await publish();assert.deepEqual(await run('[...document.getElementById("welcomeBackend").options].map(option=>option.value)'),['codex','opencode']);assert.equal(await value('welcomeModel'),'gpt-6-luna');assert.equal(await value('welcomeReasoning'),'low');assert.equal(await run('document.getElementById("welcomeFinish").disabled'),false);
    });
    await test('welcome preserves selected backend model effort and hotkey across live inventory updates',async()=>{
      await run('document.getElementById("welcomeBackend").value="opencode";document.getElementById("welcomeBackend").dispatchEvent(new Event("change",{bubbles:true}));document.getElementById("welcomeModel").value="fixture-deep";document.getElementById("welcomeModel").dispatchEvent(new Event("change",{bubbles:true}));document.getElementById("welcomeReasoning").value="high";document.getElementById("welcomeHotkey").value="Control+Alt+Space"');
      await publish([...backends,{name:'fixture-added',error:'',version:'fixture',models:['fixture-model'],reasoning:{}}]);assert.equal(await value('welcomeBackend'),'opencode');assert.equal(await value('welcomeModel'),'fixture-deep');assert.equal(await value('welcomeReasoning'),'high');assert.equal(await value('welcomeHotkey'),'Control+Alt+Space');
    });
    await test('Esc dismisses incomplete onboarding without marking complete and tray can reopen it',async()=>{
      await key('Escape');await assistant();assert.equal(win.isVisible(),false);assert.equal(JSON.parse(fs.readFileSync(settingsFile,'utf8')).onboarding.completed,false);await reopen();assert.equal(win.isVisible(),true);
    });
    await test('installation guide action uses the public documentation link without launching a browser in tests',async()=>{
      await run('document.getElementById("welcomeGuide").click()');await sleep(25);assert.equal(links.length,1);assert.equal(links[0],'https://github.com/BeautyChaser/Supporter/blob/main/docs/QUICKSTART.md');
    });
    await test('conflicting hotkey keeps welcome open and does not write completed onboarding',async()=>{
      blockedHotkey='Control+Shift+Space';await run('document.getElementById("welcomeHotkey").value="Control+Shift+Space"');const saves=commands.filter(item=>item.type==='settings').length;
      try{await key('s',{ctrlKey:true});await waitFor(async()=>(await read('welcomeFeedback')).includes('占用'),'hotkey conflict not shown');assert.equal(commands.filter(item=>item.type==='settings').length,saves);assert.equal(settings.onboarding.completed,false);assert.equal(await run('document.getElementById("welcomeFinish").disabled'),false);}finally{blockedHotkey=null;await run('document.getElementById("welcomeHotkey").value="Control+Alt+Space"');}
    });
    await test('failed welcome save waits for its acknowledgement and preserves editable choices',async()=>{
      persistFailure=true;
      try{await key('s',{ctrlKey:true});assert.equal(win.webContents.getURL().endsWith('onboarding.html'),true);await waitFor(async()=>(await read('welcomeFeedback')).includes('不可写'),'save error not shown');assert.equal(settings.onboarding.completed,false);assert.equal(await value('welcomeHotkey'),'Control+Alt+Space');assert.equal(await run('document.getElementById("welcomeFinish").disabled'),false);assert.equal(await run('document.getElementById("welcomeLater").disabled'),false);}finally{persistFailure=false;}
    });
    await test('keyboard completion persists preferences once and closes only after successful save',async()=>{
      await run('document.getElementById("welcomeBackend").value="codex";document.getElementById("welcomeBackend").dispatchEvent(new Event("change",{bubbles:true}));document.getElementById("welcomeModel").value="gpt-6-luna";document.getElementById("welcomeModel").dispatchEvent(new Event("change",{bubbles:true}));document.getElementById("welcomeReasoning").value="low"');const saves=commands.filter(item=>item.type==='settings').length;
      await run('for(let i=0;i<2;i++)document.dispatchEvent(new KeyboardEvent("keydown",{key:"s",ctrlKey:true,bubbles:true,cancelable:true}))');assert.equal(win.webContents.getURL().endsWith('onboarding.html'),true);await assistant();
      assert.equal(commands.filter(item=>item.type==='settings').length,saves+1);assert.equal(settings.onboarding.completed,true);assert.equal(settings.backend,'codex');assert.equal(settings.models.codex,'gpt-6-luna');assert.equal(settings.reasoning['codex|gpt-6-luna'],'low');assert.equal(settings.general.hotkey,'Control+Alt+Space');assert.equal(win.isVisible(),false);assert.equal(JSON.parse(fs.readFileSync(settingsFile,'utf8')).onboarding.completed,true);
    });
    await test('completed onboarding does not reopen on another ready event and new hotkey starts normal input',async()=>{
      emit({type:'ready',error:null});await sleep(50);assert.equal(win.isVisible(),false);assert.ok(keys.has('Control+Alt+Space'));keys.get('Control+Alt+Space')();await waitFor(()=>win.isVisible(),'configured hotkey did not wake assistant');assert.equal(await read('original'),'欢迎流程后的原编辑内容');
      await run('document.getElementById("prompt").value="欢迎配置后的第一条请求";document.getElementById("prompt").dispatchEvent(new Event("input",{bubbles:true}))');await key('Enter');await sleep(20);const request=commands.filter(item=>item.type==='generate').at(-1);assert.ok(request);assert.equal(request.backend,'codex');assert.equal(request.model,'gpt-6-luna');assert.equal(request.reasoning,'low');
      emit({type:'result',client_request_id:request.client_request_id,response_id:1,kind:'text',reply:'fixture',candidates:[{label:'候选',text:'第一条请求完成'}]});await sleep(50);assert.equal(await read('candidate'),'第一条请求完成');
    });
    await test('reopening and dismissing completed welcome preserves conversation candidate and draft',async()=>{
      await run('document.getElementById("prompt").value="保留欢迎页往返草稿";document.getElementById("prompt").dispatchEvent(new Event("input",{bubbles:true}))');const history=await run('window.supporterSession.snapshot().history');await reopen();await key('Escape');await assistant();keys.get('Control+Alt+Space')();await sleep(100);
      assert.equal(await read('candidate'),'第一条请求完成');assert.equal(await value('prompt'),'保留欢迎页往返草稿');assert.deepEqual(await run('window.supporterSession.snapshot().history'),history);assert.equal(settings.onboarding.completed,true);
    });
    await test('worker environment and diagnostic log stay inside the isolated data directory',async()=>{
      assert.equal(workerLaunch.dataRoot,dataDirectory);assert.equal(workerLaunch.cwd,root);assert.ok(workerLaunch.args.includes('-B'));assert.ok(path.resolve(app.getPath('userData')).startsWith(dataDirectory+path.sep));
      worker.stderr.write('fixture onboarding diagnostic\n');await waitFor(()=>fs.existsSync(path.join(dataDirectory,'.runtime','service.log')),'diagnostic not written under data directory');assert.ok(fs.readFileSync(path.join(dataDirectory,'.runtime','service.log'),'utf8').includes('fixture onboarding diagnostic'));
    });
    await test('welcome applies glass alpha to its background while keeping text fully opaque',async()=>{
      const saved=structuredClone(settings.appearance);await reopen();
      try{
        settings={...settings,appearance:{...saved,glass:false,glassOpacity:.67}};await publish();assert.equal(await run('document.documentElement.dataset.glass'),'false');assert.equal(win.getOpacity(),1);
        await run('window.supporter.onEvent(event=>{if(event.type==="onboarding-data")window.__lastWelcome=event});void 0');settings={...settings,appearance:{...saved,glass:true,glassOpacity:.67}};await publish();
        const state=await run('({glass:document.documentElement.dataset.glass,native:window.__lastWelcome.glassNative,alpha:Number(document.documentElement.style.getPropertyValue("--surface-opacity")),body:getComputedStyle(document.body).opacity,text:getComputedStyle(document.getElementById("welcomeDetection")).opacity})');
        assert.equal(state.glass,'true');assert.equal(state.alpha,state.native ? .67 : .92);assert.equal(state.body,'1');assert.equal(state.text,'1');assert.equal(win.getOpacity(),1);
      }finally{settings={...settings,appearance:saved};await publish();await key('Escape');await assistant();keys.get('Control+Alt+Space')();await sleep(100);}
    });
    await test('without a CLI keyboard later setup completes onboarding while preserving existing preferences',async()=>{
      settings={...settings,onboarding:{completed:false}};fs.writeFileSync(settingsFile,JSON.stringify(settings));const models=structuredClone(settings.models),reasoning=structuredClone(settings.reasoning);await publish([backends[2]]);await reopen();
      assert.equal(await run('document.getElementById("welcomeFinish").disabled'),true);assert.equal(await run('document.getElementById("welcomeLater").disabled'),false);const generated=commands.filter(item=>item.type==='generate').length;await key('s',{ctrlKey:true});await assistant();
      assert.equal(settings.onboarding.completed,true);assert.equal(JSON.parse(fs.readFileSync(settingsFile,'utf8')).onboarding.completed,true);assert.deepEqual(settings.models,models);assert.deepEqual(settings.reasoning,reasoning);assert.equal(commands.filter(item=>item.type==='generate').length,generated);
      keys.get('Control+Alt+Space')();await waitFor(()=>win.isVisible(),'later setup did not leave the assistant available');assert.equal(await read('backend'),'无可用 CLI');assert.equal(await value('prompt'),'保留欢迎页往返草稿');
    });
    report.passed=report.tests.every(item=>item.passed);
  }catch(error){report.harnessError=String(error.stack||error);}
  finally{report.running=false;fs.writeFileSync(reportFile,JSON.stringify(report,null,2));console.log(JSON.stringify(report));app.quit();}
});
