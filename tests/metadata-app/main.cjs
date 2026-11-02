const {app,BrowserWindow}=require('electron');const {execFile}=require('node:child_process');
const path=require('node:path');const fs=require('node:fs');
const root=path.resolve(__dirname,'../..');const file=path.join(root,'.runtime','edit-metadata.json');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function python(args,input){return new Promise((resolve,reject)=>{const child=execFile('python.exe',args,{cwd:root,windowsHide:true,encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}},(e,out,err)=>e?reject(new Error(err||e.message)):resolve(out));if(input!==undefined)child.stdin.end(JSON.stringify(input));});}
app.on('window-all-closed',()=>{});
app.whenReady().then(async()=>{
  let window;const report={readOnly:true,startedAt:new Date().toISOString()};
  const deadline=setTimeout(()=>{report.error='diagnostic deadline';fs.writeFileSync(file,JSON.stringify(report,null,2));app.exit(2);},10000);
  try{
    app.setAccessibilitySupportEnabled(true);window=new BrowserWindow({width:960,height:700,frame:false,show:false});
    await window.loadFile(path.join(__dirname,'../terminal-fixture-app/editor.html'));window.show();window.focus();
    const hwnd=Number(window.getNativeWindowHandle().readBigUInt64LE());
    await python(['-c','from supporter.windows import restore;restore({"hwnd":'+hwnd+'})']);
    report.fixturePid=process.pid;report.fixtureHwnd=hwnd;
    for(const [id,name] of [['plain','普通多行编辑框'],['rich','富文本多行编辑框']]){
      await window.webContents.executeJavaScript('document.getElementById('+JSON.stringify(id)+').focus();getSelection().removeAllRanges()');
      await sleep(120);
      const foreground=Number((await python(['-c','from supporter.windows import u;print(u.GetForegroundWindow())'])).trim());
      const scoped=JSON.parse(await python(['-m','tests.inspect_fixture_metadata'],{hwnd,name}));
      report[id]={scoped,foregroundVerified:foreground===hwnd};
      if(foreground===hwnd)report[id].focused=JSON.parse(await python(['-m','tests.inspect_fixture_metadata'],{focused:true}));
      else report[id].focusedSkipped='fixture not foreground';
    }
  }catch(error){report.error=error.stack;}
  finally{clearTimeout(deadline);report.finishedAt=new Date().toISOString();fs.writeFileSync(file,JSON.stringify(report,null,2));if(window&&!window.isDestroyed())window.destroy();app.quit();}
});
