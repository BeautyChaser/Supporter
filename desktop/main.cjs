const {app,BrowserWindow,ipcMain,screen,Tray,Menu,globalShortcut,nativeTheme,powerMonitor,clipboard,shell}=require('electron');
const {spawn}=require('node:child_process');
const path=require('node:path');
const fs=require('node:fs');
const readline=require('node:readline');
const {place}=require('./placement.cjs');
const {BoundsAnimator}=require('./motion.cjs');
const {createSettingsWindow}=require('./settings-window.cjs');
const {CompletionStore}=require('./completion-store.cjs');
const {initializePaths}=require('./runtime-paths.cjs');
const {applyGlass}=require('./glass.cjs');
const root=path.resolve(__dirname,'..');
const runtimePaths=initializePaths({app,sourceRoot:root});
const completionStore=new CompletionStore(runtimePaths.completionRoot);
process.on('uncaughtException',error=>{fs.appendFileSync(path.join(runtimePaths.runtimeRoot,'main-error.log'),String(error.stack||error)+'\n');app.quit();});
let win,worker,tray,anchor=null,quitting=false;
let settingsWin,inventory=[],settings={};
try{settings=JSON.parse(fs.readFileSync(runtimePaths.settingsPath,'utf8'));}catch{}
let currentAppearance=settings.appearance||{};
let glassState={enabled:true,native:false,opacity:.9};
let pendingSave=null,closeTimer=null;
let viewMode='assistant';
let sessionSnapshot=null,sessionEvents=[];
let pendingWake=false,pendingWrite=false;
let completionEnvironment='auto',latestGenerateId=null,lastResult=null,pendingCompletion=null;
let activeLocateRequest=null;
let pendingWakeId=null,wakeSequence=0;
let inventoryReady=false,startupError='';
const needsOnboarding=()=>settings.onboarding?.completed===false||runtimePaths.fresh&&settings.onboarding?.completed!==true;
const preview=process.argv.includes('--preview')||process.argv.includes('--preview-settings');
if(!app.requestSingleInstanceLock()) app.quit();
else app.whenReady().then(()=>{
  win=new BrowserWindow({width:520,height:186,frame:false,show:false,resizable:false,
    transparent:true,hasShadow:true,alwaysOnTop:true,skipTaskbar:true,backgroundColor:'#00000000',
    webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true}});
  win.setAlwaysOnTop(true,'floating');
  win.on('blur',()=>{
    if(viewMode!=='assistant'||quitting||closeTimer||!win.isVisible())return;
    win.hide();write({type:'suspend'});
  });
  const boundsMotion=new BoundsAnimator(()=>win.getBounds(),bounds=>{if(!win.isDestroyed())win.setBounds(bounds);});
  function welcomeData(){return {type:'onboarding-data',settings,backends:inventory,scanning:!inventoryReady,error:startupError,glassNative:glassState.native,systemDark:nativeTheme.shouldUseDarkColors};}
  async function showOnboarding(){
    if(viewMode==='onboarding'){win.show();win.focus();return;}
    try{sessionSnapshot=await win.webContents.executeJavaScript('window.supporterSession?.snapshot()||null');}catch{sessionSnapshot=null;}
    viewMode='onboarding';if(closeTimer){clearTimeout(closeTimer);closeTimer=null;}boundsMotion.stop();win.hide();write({type:'suspend'});
    win.setMinimumSize(780,620);win.setResizable(true);win.setAlwaysOnTop(false);win.setSkipTaskbar(false);win.setOpacity(1);win.setBackgroundColor('#17191f');win.setSize(880,690);win.center();win.setTitle('欢迎使用 Supporter');
    applyAppearance(settings.appearance||{});await win.loadFile(path.join(__dirname,'onboarding.html'));send(welcomeData());win.show();win.focus();
  }
  async function showSettings(command='/settings'){
    if(command==='/settings'){
      if(viewMode==='settings'||viewMode==='settings-loading'){win.show();win.focus();return;}
      viewMode='settings-loading';
      try{sessionSnapshot=await win.webContents.executeJavaScript('window.supporterSession?.snapshot()||null');}catch{sessionSnapshot=null;}
      if(closeTimer){clearTimeout(closeTimer);closeTimer=null;}
      boundsMotion.stop();win.hide();write({type:'suspend'});viewMode='settings';
      settingsWin=createSettingsWindow({window:win,directory:__dirname,getData:()=>({settings,backends:inventory}),
        onError:error=>fs.appendFileSync(path.join(runtimePaths.runtimeRoot,'settings-error.log'),String(error.stack||error)+'\n')});
      applyAppearance(settings.appearance||{});
      return;
    }
    if(!anchor){const a=screen.getPrimaryDisplay().workArea;anchor={x:a.x+a.width-550,y:a.y+a.height-70};}
    position(300);win.show();win.focus();send({type:'open-settings',command});
  }
  if(!preview){
    tray=new Tray(path.join(__dirname,'tray.png'));
    tray.setToolTip('Supporter · Ctrl+Space');
    tray.setContextMenu(Menu.buildFromTemplate([
      {label:'设置…',click:()=>showSettings()},
      {label:'入门与环境检测',click:()=>showOnboarding()},
      {label:'快捷键与使用说明',click:()=>showSettings('/help')},
      {type:'separator'},
      {label:'退出 Supporter',click:()=>app.quit()}
    ]));
    tray.on('double-click',()=>showSettings());
  }
  win.loadFile(path.join(__dirname,'index.html'));
  win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  win.webContents.on('will-navigate',e=>e.preventDefault());
  win.on('close',e=>{if(!quitting){e.preventDefault();hide();}});
  async function closeSettings(){
    if(!['settings','onboarding'].includes(viewMode))return;
    win.hide();settingsWin=null;viewMode='assistant';
    win.setMinimumSize(0,0);win.setResizable(false);win.setAlwaysOnTop(true,'floating');win.setSkipTaskbar(true);
    win.setBackgroundColor('#00000000');win.setTitle('Supporter');
    await win.loadFile(path.join(__dirname,'index.html'));
    applyAppearance(settings.appearance||{});send({type:'inventory',backends:inventory,settings});
    send({type:'completion-data',data:completionStore.snapshot()});
    if(sessionSnapshot)send({type:'restore-session',state:sessionSnapshot});
    for(const event of sessionEvents)send(event);sessionEvents=[];
  }
  function send(event){
    if(viewMode!=='assistant'&&['result','progress','error','accepted','clipboard-copied','locate-results','locate-error','backend-scan-error'].includes(event.type)){sessionEvents.push(event);return;}
    win.webContents.send('event',event);
  }
  function position(height=186,animate=win.isVisible()){
    if(viewMode!=='assistant'||!anchor)return;
    if(!Number.isFinite(Number(anchor.x))||!Number.isFinite(Number(anchor.y))){
      const a=screen.getPrimaryDisplay().workArea;anchor={...anchor,x:a.x+a.width/2-260,y:a.y+a.height/2};
    }
    height=Number.isFinite(height)?height:186;
    const point=screen.screenToDipPoint({x:Math.round(Number(anchor.x)),y:Math.round(Number(anchor.y))});
    const area=screen.getDisplayNearestPoint(point).workArea;
    boundsMotion.move(place(point,{width:Math.max(440,Math.min(760,Number(currentAppearance.width)||520)),height},area),animate&&currentAppearance.motion!==false);
  }
  function applyAppearance(appearance){
    if(!win||win.isDestroyed())return;
    currentAppearance=appearance;
    glassState=applyGlass(win,appearance);
    send({type:'appearance',appearance,systemDark:nativeTheme.shouldUseDarkColors,glassNative:glassState.native});
    if(viewMode!=='assistant'){win.setOpacity(1);return;}
    win.setOpacity(Math.max(.8,Math.min(1,Number(appearance.opacity)||1)));
    if(win.isVisible())position(win.getBounds().height);
  }
  function registerHotkey(accelerator){
    globalShortcut.unregisterAll();
    const key=accelerator||'Control+Space';
    function wake(){
      if(viewMode==='onboarding'){win.show();win.focus();return;}
      if(viewMode==='settings'){closeSettings();return;}
      if(closeTimer){clearTimeout(closeTimer);closeTimer=null;}
      if(win.isVisible()&&win.isFocused()){send({type:'focus-input'});return;}
      if(win.isVisible())win.hide();
      pendingWake=true;
      activeLocateRequest=null;
      write({type:'refresh',force:false});
      pendingWakeId='wake-'+(++wakeSequence);write({type:'capture',force:true,request_id:pendingWakeId});
    }
    try{if(globalShortcut.register(key,wake))return null;}catch{}
    if(key!=='Control+Space')globalShortcut.register('Control+Space',wake);
    return '快捷键 '+key+' 被占用或无效，已尝试恢复 Ctrl+Space';
  }
  function reveal(target,resume=false){if(closeTimer){clearTimeout(closeTimer);closeTimer=null;}anchor=target;position(186,false);win.show();win.focus();send({type:'wake',target,resume});}
  for(const event of ['resume','unlock-screen'])powerMonitor.on(event,()=>registerHotkey(settings.general?.hotkey));
  function fadeOut(action){
    if(closeTimer)clearTimeout(closeTimer);
    send({type:'closing'});
    closeTimer=setTimeout(()=>{closeTimer=null;win.hide();action();},currentAppearance.motion===false?0:95);
  }
  function hide(restore=true){
    if(['settings','onboarding'].includes(viewMode)){closeSettings();return;}
    pendingWake=false;pendingWrite=false;
    pendingWakeId=null;
    activeLocateRequest=null;
    // Context cancellation must not be delayed/cancelled by an animation timer.
    write({type:'cancel',restore:false});
    fadeOut(()=>{if(restore)write({type:'restore-target'});});
  }
  function write(data){if(worker&&!worker.killed)worker.stdin.write(JSON.stringify(data)+'\n');}
  function reloadCompletion(){send({type:'completion-data',data:completionStore.reload()});}
  function learnCompletion(value,environment,raw){
    const changed=completionStore.observe(value,environment,raw);
    if(changed||completionStore.errors.length)send({type:'completion-data',data:completionStore.snapshot()});
  }
  function learnAccepted(){
    if(pendingCompletion)learnCompletion(pendingCompletion.text,pendingCompletion.environment,true);
    pendingCompletion=null;
  }
  ipcMain.on('action',(event,data)=>{
    if(data.type==='onboarding-dismiss'){closeSettings();return;}
    if(data.type==='open-install-guide'){shell.openExternal('https://github.com/BeautyChaser/Supporter/blob/main/docs/QUICKSTART.md');return;}
    if(data.type==='completion-reload'){reloadCompletion();return;}
    if(data.type==='locate-window')activeLocateRequest=data.request_id;
    if(data.type==='locate-select'){activeLocateRequest=data.request_id;pendingWake=true;pendingWakeId=data.request_id;win.hide();write(data);return;}
    if(data.type==='open-settings'){showSettings();return;}
    if(data.type==='settings-close'){closeSettings();return;}
    if(data.type==='settings'){settings=data.settings;write(data);return;}
    if(data.type==='preview-appearance'){applyAppearance(data.appearance||{});return;}
    if(data.type==='settings-save'||data.type==='onboarding-save'){
      if(pendingSave)return;
      const next=data.settings||{};
      const error=registerHotkey(next.general?.hotkey);
      if(error){event.sender.send('event',{type:'settings-error',message:error});return;}
      const request_id=String(Date.now());pendingSave={request_id,next,sender:event.sender};
      write({type:'settings',settings:next,request_id});return;
    }
    if(data.type==='resize'){position(Math.max(166,Math.min(520,Number(data.height)||186)));return;}
    if(data.type==='cancel'){lastResult=null;pendingCompletion=null;hide();return;}
    if(data.type==='quit'){app.quit();return;}
    if(data.type==='generate'){
      completionEnvironment=data.completion_environment||settings.environment||'auto';latestGenerateId=data.client_request_id;lastResult=null;
      if(data.observe_completion===true)learnCompletion(data.request,completionEnvironment,false);
    }
    if(data.type==='refresh')reloadCompletion();
    if(data.type==='accept'||data.type==='copy'||data.type==='retarget'){
      pendingWrite=data.type!=='retarget';pendingCompletion=null;
      if(lastResult?.kind==='commands'&&lastResult.response_id===data.response_id&&Number.isInteger(data.candidate_index)){
        const choice=lastResult.candidates?.[data.candidate_index];if(choice)pendingCompletion={text:choice.text,environment:lastResult.completionEnvironment};
      }
      fadeOut(()=>write(data));return;
    }
    write(data);
  });
  win.webContents.once('did-finish-load',()=>{
    applyAppearance(settings.appearance||{});
    send({type:'completion-data',data:completionStore.snapshot()});
    if(preview){
      if(process.argv.includes('--preview-settings')){
        inventory=[{name:'codex',version:'codex-cli',error:'',models:['gpt-6.1-sol'],reasoning:{'gpt-6.1-sol':['low','medium','high','xhigh']}}];
        win.setBounds({x:120,y:100,width:850,height:650});
        win.loadFile(path.join(__dirname,'settings.html')).then(()=>{
          send({type:'settings-data',settings,backends:inventory});win.show();win.focus();
          setTimeout(async()=>{try{const img=await win.webContents.capturePage();fs.writeFileSync(path.join(runtimePaths.runtimeRoot,'settings-preview.png'),img.toPNG());}catch(error){fs.appendFileSync(path.join(runtimePaths.runtimeRoot,'main-error.log'),String(error.stack||error));}app.quit();},1500);
        });
        return;
      }
      const a=screen.getPrimaryDisplay().workArea;
      reveal({x:a.x+Math.round(a.width/2)-260,y:a.y+Math.round(a.height*.75),source:'uia-caret',terminal:false});
      send({type:'inventory',backends:[{name:'codex',error:'',models:['gpt-6.1-sol'],reasoning:{'gpt-6.1-sol':['low','medium','high','xhigh']},source:'Codex 模型目录'}],settings:{backend:'codex',models:{codex:'gpt-6.1-sol'}}});
      setTimeout(async()=>{const img=await win.webContents.capturePage();fs.writeFileSync(path.join(runtimePaths.runtimeRoot,'preview.png'),img.toPNG());app.quit();},1400);
      return;
    }
    worker=spawn(runtimePaths.python,['-B','-u','-m','supporter.service'],{cwd:runtimePaths.resourceRoot,windowsHide:true,stdio:['pipe','pipe','pipe'],env:runtimePaths.environment});
    const shortcutError=registerHotkey(settings.general?.hotkey);
    if(shortcutError){startupError=shortcutError;if(!needsOnboarding()){showSettings('/help');send({type:'error',message:shortcutError});}}
    readline.createInterface({input:worker.stdout}).on('line',async line=>{
      try{const event=JSON.parse(line);
      if(event.type==='ready'&&needsOnboarding())showOnboarding();
      // A cancelled capture/location request must not reopen a closed context.
      if(event.type==='wake'&&(!pendingWake||event.request_id!=null&&event.request_id!==pendingWakeId))return;
      if(event.type==='error'&&event.capture_request_id!=null&&event.capture_request_id!==pendingWakeId)return;
      if(event.type==='locate-error'&&event.request_id===activeLocateRequest){pendingWake=false;if(viewMode==='assistant'){win.show();win.focus();}}
      if(event.type==='result'&&(event.client_request_id==null||event.client_request_id===latestGenerateId))lastResult={...event,completionEnvironment};
      if(event.type==='copy-ready'){
        try{await clipboard.writeText(event.text);}
        catch(error){pendingWrite=false;pendingCompletion=null;send({type:'error',message:'复制失败，候选已保留：'+error.message});if(viewMode==='assistant'){win.show();win.focus();}return;}
        learnAccepted();pendingWrite=false;send({type:'clipboard-copied'});win.hide();write({type:'clipboard-written'});
        tray?.setToolTip('Supporter · 已复制候选，可 Ctrl+V 粘贴');
        setTimeout(()=>{if(!quitting)tray?.setToolTip('Supporter · Ctrl+Space');},3000).unref();
        return;
      }
      if(event.type==='settings-persisted'&&pendingSave?.request_id===event.request_id){
        const saved=pendingSave;pendingSave=null;
        if(Boolean(saved.next.general?.autoStart)!==Boolean(settings.general?.autoStart))app.setLoginItemSettings({openAtLogin:Boolean(saved.next.general?.autoStart),path:process.execPath,args:[root]});
        settings=saved.next;applyAppearance(settings.appearance||{});send({type:'inventory',backends:inventory,settings});
        if(!saved.sender.isDestroyed())saved.sender.send('event',{type:'settings-saved'});
      }
      if(event.type==='settings-persist-error'&&pendingSave?.request_id===event.request_id){
        registerHotkey(settings.general?.hotkey);if(!pendingSave.sender.isDestroyed())pendingSave.sender.send('event',{type:'settings-error',message:event.message});pendingSave=null;
      }
      if(event.type==='accepted'){learnAccepted();pendingWrite=false;}
      const revealError=event.type==='error'&&(pendingWake||pendingWrite);
      if(event.type==='error'){pendingWake=false;pendingWrite=false;pendingCompletion=null;}
      if(event.type==='inventory'){inventoryReady=true;inventory=event.backends;settings=event.settings||settings;if(viewMode!=='settings')applyAppearance(settings.appearance||{});if(viewMode==='onboarding')send(welcomeData());if(settingsWin&&!settingsWin.isDestroyed())settingsWin.webContents.send('event',{type:'settings-data',settings,backends:inventory});}if(event.type==='wake'){
        pendingWake=false;
        if(!win.isVisible())reveal(event.target,event.resume);
      }else{send(event);if(revealError&&viewMode==='assistant'){win.show();win.focus();}if(event.type==='ready'&&event.error){reveal({x:160,y:400});send({type:'error',message:event.error});}}}catch(e){console.error(e);}
    });
    worker.stderr.on('data',data=>fs.appendFileSync(path.join(runtimePaths.runtimeRoot,'service.log'),data));
    worker.on('error',e=>{startupError='后台组件无法启动，请重新安装 Supporter。'+e.message;if(needsOnboarding()||viewMode==='onboarding')showOnboarding().then(()=>send(welcomeData()));else{reveal({x:160,y:400});send({type:'error',message:startupError});}});
    worker.on('exit',code=>{if(!quitting){reveal({x:160,y:400});send({type:'error',message:'后台退出，请重启 Supporter。退出码 '+code});}});
  });
  app.on('before-quit',()=>{quitting=true;boundsMotion.stop();if(closeTimer)clearTimeout(closeTimer);globalShortcut.unregisterAll();tray?.destroy();if(worker){write({type:'quit'});setTimeout(()=>worker.kill(),500).unref();}});
});
app.on('window-all-closed',()=>app.quit());
