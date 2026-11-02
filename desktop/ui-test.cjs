// Exercise real renderer keyboard handlers and layout without calling a model
// or sending input to another application.
const {app,BrowserWindow,ipcMain}=require('electron');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const root=path.resolve(__dirname,'..');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const inventory={type:'inventory',backends:[{name:'codex',error:'',models:['gpt-6.1-sol'],reasoning:{}}],settings:{backend:'codex',models:{codex:'gpt-6.1-sol'}}};
const gpuChoices=[{label:'NVIDIA · 概览',detail:'适用于已安装 NVIDIA 驱动的环境',text:'nvidia-smi'},
  {label:'AMD · ROCm',detail:'适用于 ROCm 环境',text:'rocm-smi'},
  {label:'Intel · 实时监控',detail:'适用于 Intel GPU 工具环境',text:'intel_gpu_top'}];
app.on('window-all-closed',()=>{});
app.whenReady().then(async()=>{
  fs.writeFileSync(path.join(root,'.runtime','ui-test.json'),JSON.stringify({running:true}));
  let actions=[],win;
  try{
    win=new BrowserWindow({width:520,height:186,show:false,frame:false,transparent:true,
      webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true}});
    ipcMain.on('action',(e,data)=>{actions.push(data);if(e.sender===win.webContents&&data.type==='resize')win.setSize(520,Math.max(166,Math.min(520,data.height)));if(data.type==='settings-close')win.hide();});
    await win.loadFile(path.join(__dirname,'index.html'));win.showInactive();
    const emit=event=>win.webContents.send('event',event);
    const run=code=>win.webContents.executeJavaScript(code);
    const key=(key,extra={})=>run('document.dispatchEvent(new KeyboardEvent("keydown",'+JSON.stringify({key,bubbles:true,...extra})+'))');
    emit(inventory);emit({type:'wake',target:{scope:'editor',context:'原始请求',source:'uia-caret'}});await sleep(100);
    emit({type:'result',reply:'不同硬件使用不同工具，请先选择适用场景。',kind:'commands',candidates:gpuChoices,response_id:7});await sleep(300);
    await key('Tab');await sleep(50);assert.equal(actions.filter(a=>a.type==='accept').length,0,'Tab must not pick a hardware branch silently');
    await key('2',{altKey:true});assert.equal(await run('document.getElementById("candidate").textContent'),'rocm-smi');
    await key('Tab');await sleep(50);
    const accepted=actions.find(a=>a.type==='accept');assert.deepEqual(accepted,{type:'accept',response_id:7,candidate_index:1});
    assert.ok(!('text' in accepted),'renderer cannot paste reply text');
    const start=actions.filter(a=>a.type==='resize').length;
    for(let i=0;i<30;i++)emit({type:'progress',message:'正在生成候选'});
    await sleep(500);const settled=actions.filter(a=>a.type==='resize').length;
    await sleep(350);assert.equal(actions.filter(a=>a.type==='resize').length,settled,'resize must settle');
    assert.ok(settled-start<=3,'repeated progress must not create a resize loop');
    emit({type:'wake',target:{scope:'reference',context:'网页只读选区',source:'uia-caret'}});
    emit({type:'result',reply:'已保留一条命令。',kind:'commands',candidates:[gpuChoices[0]],response_id:8});await sleep(100);
    const oldAccepts=actions.filter(a=>a.type==='accept').length;
    await key('Tab');await sleep(30);assert.equal(actions.filter(a=>a.type==='accept').length,oldAccepts+1);assert.equal(actions.filter(a=>a.type==='accept').at(-1).response_id,8);
    emit({type:'wake',resume:true,target:{scope:'editor',context:'',source:'uia-editor'}});await sleep(50);
    assert.equal(await run('document.getElementById("candidate").textContent'),'nvidia-smi','candidate survives target handoff');
    await key('Tab');await sleep(30);assert.equal(actions.filter(a=>a.type==='accept').at(-1).response_id,8);
    emit({type:'wake',target:{scope:'editor',context:'',source:'uia-editor'}});
    emit({type:'result',reply:'请说明硬件环境。',kind:'clarification',candidates:[],response_id:9});await sleep(50);
    assert.equal(await run('document.getElementById("result").hidden'),true);
    // Capture the branch UI using deterministic fixture data, never live user text.
    emit({type:'wake',target:{scope:'editor',context:'我要 Linux 中查看 GPU 状态的命令',source:'uia-caret'}});
    emit({type:'result',reply:'请按显卡类型选择一条命令。说明不会写入原文。',kind:'commands',candidates:gpuChoices,response_id:10});await sleep(50);await key('ArrowDown');
    win.show();await sleep(250);
    const layout=await run('({footer:document.querySelector("footer").getBoundingClientRect().bottom,height:innerHeight})');
    assert.ok(layout.footer<=layout.height,'footer stays visible when content is long');
    fs.writeFileSync(path.join(root,'.runtime','branches-preview.png'),(await win.webContents.capturePage()).toPNG());
    await win.loadFile(path.join(__dirname,'settings.html'));emit({...inventory,type:'settings-data'});await sleep(100);
    await run('document.getElementById("save").click()');await sleep(30);assert.ok(!win.isDestroyed(),'wait for persistence acknowledgement');
    emit({type:'settings-error',message:'快捷键冲突'});await sleep(30);assert.ok(!win.isDestroyed());
    assert.equal(await run('document.getElementById("save").disabled'),false);
    emit({type:'settings-saved'});await sleep(120);assert.ok(actions.some(a=>a.type==='settings-close'),'successful save requests host route close');assert.ok(!win.isVisible());assert.ok(!win.isDestroyed(),'the host survives settings close');
    fs.writeFileSync(path.join(root,'.runtime','ui-test.json'),JSON.stringify({passed:true,branchSelection:true,noProsePaste:true,readonlyAcceptRequest:true,resumePreservesCandidate:true,stableResize:true,settingsAutoClose:true},null,2));
    console.log('Renderer regression tests passed');
  }catch(error){console.error(error);fs.writeFileSync(path.join(root,'.runtime','ui-test.json'),JSON.stringify({passed:false,error:error.stack}));}
  finally{if(win&&!win.isDestroyed())win.destroy();app.quit();}
});
