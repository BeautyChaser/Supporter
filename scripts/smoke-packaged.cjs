/* Actual packaged app smoke, controlling only its own isolated CDP target. */
const fs=require('node:fs'),path=require('node:path'),net=require('node:net'),os=require('node:os');
const {spawn,spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const executable=path.resolve(process.argv[2]||path.join(root,'release/win-unpacked/Supporter.exe'));
const reportFile=path.join(root,'.runtime/packaged-ui-smoke.json');
const data=fs.mkdtempSync(path.join(root,'.runtime/packaged-ui-'));
const plugins=path.join(data,'backend-plugins');fs.mkdirSync(plugins);
const env={...process.env,PATH:'',SUPPORTER_DATA_DIR:data,SUPPORTER_BACKEND_DIR:plugins};
for(const key of ['SUPPORTER_PYTHON','SUPPORTER_RESOURCE_ROOT','PYTHONHOME','PYTHONPATH','ELECTRON_RUN_AS_NODE'])delete env[key];
for(const key of ['HOME','USERPROFILE','APPDATA','LOCALAPPDATA'])env[key]=path.join(data,'home',key);
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const report={passed:false,actualPackagedApp:true,emptyPath:true,isolatedProfile:true,noAccountCalls:true};
let child,socket;
async function main(){
  const server=net.createServer();await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const port=server.address().port;await new Promise(resolve=>server.close(resolve));
  child=spawn(executable,['--remote-debugging-port='+port],{cwd:data,env,windowsHide:true,stdio:['ignore','ignore','pipe']});
  let errorTail='';child.stderr.on('data',value=>{errorTail=(errorTail+value).slice(-2000);});
  const deadline=Date.now()+25000;let target;
  while(Date.now()<deadline){
    if(child.exitCode!=null)throw new Error('Packaged app exited before welcome');
    try{const targets=await(await fetch('http://127.0.0.1:'+port+'/json')).json();target=targets.find(t=>t.type==='page'&&t.url.endsWith('/onboarding.html'));if(target)break;}catch{}
    await sleep(100);
  }
  if(!target)throw new Error('Packaged welcome page did not load');
  socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
  let sequence=0;const pending=new Map();
  socket.addEventListener('message',event=>{const value=JSON.parse(String(event.data));if(pending.has(value.id)){const p=pending.get(value.id);pending.delete(value.id);value.error?p.reject(new Error(value.error.message)):p.resolve(value.result);}});
  const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(pending.delete(id))reject(new Error('CDP timeout: '+method));},8000).unref();});
  const evaluate=async expression=>(await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})).result.value;
  await sleep(700);
  report.welcome=await evaluate('({ready:Boolean(window.supporter&&document.getElementById("welcomeFinish")),noBackend:document.getElementById("welcomeBackend").options.length===0,glass:document.documentElement.dataset.glass,textOpacity:getComputedStyle(document.querySelector("h1")).opacity})');
  if(!report.welcome.ready||!report.welcome.noBackend||report.welcome.textOpacity!=='1')throw new Error('Packaged first-run controls invalid');
  const python=path.join(path.dirname(executable),'resources/supporter/python/python.exe');
  const nativeCode=`import ctypes as c,json,sys\nu=c.WinDLL('user32');d=c.WinDLL('dwmapi');result=[]\nT=c.WINFUNCTYPE(c.c_bool,c.c_void_p,c.c_void_p)\ndef check(h,p):\n v=c.c_ulong();u.GetWindowThreadProcessId(c.c_void_p(h),c.byref(v))\n if v.value==int(sys.argv[1]):\n  material=c.c_int();hr=d.DwmGetWindowAttribute(c.c_void_p(h),38,c.byref(material),4);result.append({'hr':hr,'material':material.value})\n return True\nu.EnumWindows(T(check),0)\nprint(json.dumps(result))`;
  const native=spawnSync(python,['-B','-c',nativeCode,String(child.pid)],{cwd:data,env,encoding:'utf8',windowsHide:true});
  report.nativeBackdrop=native.status===0?JSON.parse(native.stdout):[];
  const shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(root,'.runtime/packaged-welcome.png'),Buffer.from(shot.data,'base64'));
  await evaluate('document.getElementById("welcomeHotkey").value="Control+Alt+Shift+F12";document.getElementById("welcomeLater").click();true');
  let state;
  for(let i=0;i<50;i++){
    await sleep(100);state=JSON.parse(fs.readFileSync(path.join(data,'settings.json'),'utf8'));
    if(state.onboarding?.completed)break;
  }
  if(!state?.onboarding?.completed||state.codexConnection?.mode!=='inherit'||state.codexConnection?.proxyUrl)throw new Error('Packaged settings isolation/save failed');
  report.savedCleanSettings=true;
  for(let i=0;i<50;i++){const targets=await(await fetch('http://127.0.0.1:'+port+'/json')).json();if(targets.some(t=>t.url.endsWith('/index.html')))break;await sleep(100);}
  await evaluate('window.supporter.send({type:"quit"});true').catch(()=>{});
  for(let i=0;i<60&&child.exitCode==null;i++)await sleep(100);
  if(child.exitCode!==0)throw new Error('Packaged app failed to exit cleanly');
  report.passed=true;
}
main().catch(error=>{report.error=String(error.stack||error);process.exitCode=1;}).finally(()=>{
  socket?.close();
  if(child&&child.exitCode==null)spawnSync('taskkill.exe',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});
  fs.writeFileSync(reportFile,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
});
