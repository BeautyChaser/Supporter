const {app,BrowserWindow}=require('electron');const path=require('node:path');const fs=require('node:fs');const assert=require('node:assert/strict');
const {createSettingsWindow}=require('./settings-window.cjs');const root=path.resolve(__dirname,'..');
app.on('window-all-closed',()=>{});
app.whenReady().then(async()=>{
  const floating=new BrowserWindow({width:520,height:186,frame:false,show:false,transparent:true,
    webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true}});
  let settingsWindow;
  try{
    await floating.loadFile(path.join(__dirname,'index.html'));
    for(let i=0;i<3;i++){
      settingsWindow=createSettingsWindow({window:floating,directory:__dirname,getData:()=>({settings:{appearance:{theme:'dark'}},backends:[]})});
      await settingsWindow.supporterReady;
      const dom=await settingsWindow.webContents.executeJavaScript('({title:document.querySelector("h1").textContent,form:document.querySelector("#form").getBoundingClientRect().width,colors:document.querySelectorAll("#colors button").length})');
      assert.equal(dom.title,'外观');assert.ok(dom.form>300);assert.equal(dom.colors,6);assert.ok(settingsWindow.isVisible());
      if(i===2)fs.writeFileSync(path.join(root,'.runtime','settings-actual-window.png'),(await settingsWindow.webContents.capturePage()).toPNG());
      settingsWindow.hide();
    }
    fs.writeFileSync(path.join(root,'.runtime','settings-window-test.json'),JSON.stringify({passed:true,realSettingsRoute:true,openCloseCycles:3}));
  }catch(error){fs.writeFileSync(path.join(root,'.runtime','settings-window-test.json'),JSON.stringify({passed:false,error:error.stack}));}
  finally{if(!floating.isDestroyed())floating.destroy();app.quit();}
});
