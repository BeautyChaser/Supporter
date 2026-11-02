const {app,BrowserWindow}=require('electron');
const {execFile}=require('node:child_process');const path=require('node:path');const fs=require('node:fs');const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..');const file=path.join(root,'.runtime','locate-electron-test.json');
const profile=path.join(root,'.runtime','locate-electron-profile');fs.mkdirSync(profile,{recursive:true});app.setPath('userData',profile);
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function bridge(data){return new Promise((resolve,reject)=>{const child=execFile('python.exe',['-m','tests.locate_window_bridge'],{cwd:root,windowsHide:true,encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}},(error,out,stderr)=>error?reject(new Error(stderr||error.message)):resolve(JSON.parse(out)));child.stdin.end(JSON.stringify(data));});}
app.on('window-all-closed',()=>{});
app.whenReady().then(async()=>{
  let window;const report={passed:false,noKeyboardMouseOrTextInput:true,fixtureOnly:true};
  const deadline=setTimeout(()=>{report.error='fixture deadline';fs.writeFileSync(file,JSON.stringify(report,null,2));app.exit(2);},12000);
  try{
    app.setAccessibilitySupportEnabled(true);window=new BrowserWindow({width:900,height:700,frame:false,show:false});
    await window.loadFile(path.join(__dirname,'editor.html'));window.show();window.focus();await sleep(150);
    const hwnd=Number(window.getNativeWindowHandle().readBigUInt64LE());const common={hwnd,pid:process.pid};
    report.setup=await bridge({...common,action:'setup'});
    const listing=await bridge({...common,action:'list'});report.listedNames=listing.controls.map(control=>control.name).sort();
    assert.deepEqual(report.listedNames,['Fixture browser plain','Fixture browser rich']);
    assert.ok(!JSON.stringify(listing).includes('sentinel'),'enumeration never exposes text values');report.metadataPassed=true;
    const chosen=listing.controls.find(control=>control.name==='Fixture browser rich');
    const result=await bridge({...common,action:'focus',id:chosen.id,expected:'fixture rich sentinel'});
    if(result.skipped){report.skipped=result.skipped;report.foregroundUnavailable=result.foregroundUnavailable;}
    else{
      assert.equal(result.hwnd,hwnd);assert.equal(result.scope,'editor');assert.equal(result.unchanged,true);
      assert.equal(await window.webContents.executeJavaScript('document.activeElement.id'),'rich');
      assert.equal(await window.webContents.executeJavaScript('document.getElementById("rich").innerText'),'fixture rich sentinel');
      assert.equal(await window.webContents.executeJavaScript('document.getElementById("plain").value'),'fixture plain sentinel');
      report.focusSelection={passed:true,scope:result.scope,domFocus:'rich',valuesUnchanged:true};report.passed=true;
    }
  }catch(error){report.error=error.stack;}
  finally{clearTimeout(deadline);report.status=report.passed?'passed':report.skipped?'skipped-focus':'failed';fs.writeFileSync(file,JSON.stringify(report,null,2));if(window&&!window.isDestroyed())window.destroy();app.quit();}
});
