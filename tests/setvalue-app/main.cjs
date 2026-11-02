const {app,BrowserWindow}=require('electron');const {execFile}=require('node:child_process');
const fs=require('node:fs');const path=require('node:path');
const root=path.resolve(__dirname,'../..');const reportPath=path.join(root,'.runtime','setvalue-test.json');
function writer(data){return new Promise((resolve,reject)=>{const child=execFile('python.exe',['-m','tests.uia_setvalue_writer'],{cwd:root,windowsHide:true,encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}},(e,out,err)=>e?reject(new Error(err||e.message)):resolve(JSON.parse(out)));child.stdin.end(JSON.stringify(data));});}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
app.on('window-all-closed',()=>{});
app.whenReady().then(async()=>{
  let window;const report={startedAt:new Date().toISOString(),strategy:'targeted UIA ValuePattern.SetValue',noKeyboardInput:true};
  const deadline=setTimeout(()=>{report.error='fixture deadline';fs.writeFileSync(reportPath,JSON.stringify(report,null,2));app.exit(2);},12000);
  try{
    app.setAccessibilitySupportEnabled(true);window=new BrowserWindow({width:960,height:700,frame:false,show:false});
    await window.loadFile(path.join(__dirname,'../terminal-fixture-app/editor.html'));window.showInactive();await sleep(200);
    const hwnd=Number(window.getNativeWindowHandle().readBigUInt64LE());
    await window.webContents.executeJavaScript('window.testEvents=[];for(const type of ["beforeinput","input","change"]){document.addEventListener(type,event=>window.testEvents.push({type,target:event.target.id,inputType:event.inputType||null,dataLength:typeof event.data==="string"?event.data.length:null,trusted:event.isTrusted}));}');
    for(const [id,name,text] of [
      ['plain','普通多行编辑框','# 标题\n\n第一段 Ω\n第二段\n'],
      ['rich','富文本多行编辑框','## Markdown 标题\n\n第一段\n第二段'],
    ]){
      await window.webContents.executeJavaScript('window.testEvents=[]');
      const response=await writer({hwnd,processId:process.pid,name,text});await sleep(120);
      const state=await window.webContents.executeJavaScript('({value:document.getElementById('+JSON.stringify(id)+').'+(id==='plain'?'value':'innerText')+',events:window.testEvents})');
      report[id]={...response,expectedLength:text.length,actualLength:state.value.length,exact:state.value===text,events:state.events,inputTriggered:state.events.some(e=>e.type==='input'&&e.target===id),changeTriggered:state.events.some(e=>e.type==='change'&&e.target===id)};
      if(state.value!==text)report[id].fixtureActual=JSON.stringify(state.value);
    }
    report.passed=report.plain.exact&&report.rich.exact&&report.plain.inputTriggered&&report.rich.inputTriggered;
  }catch(error){report.error=error.stack;report.passed=false;}
  finally{clearTimeout(deadline);report.finishedAt=new Date().toISOString();fs.writeFileSync(reportPath,JSON.stringify(report,null,2));if(window&&!window.isDestroyed())window.destroy();app.quit();}
});
