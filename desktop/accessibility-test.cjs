const {app,BrowserWindow}=require('electron');
const {execFile}=require('node:child_process');const assert=require('node:assert/strict');
const path=require('node:path');const fs=require('node:fs');const root=path.resolve(__dirname,'..');
function python(code){return new Promise((resolve,reject)=>execFile('python.exe',['-c',code],{cwd:root,windowsHide:true,encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}},(e,out,err)=>e?reject(new Error(err)):resolve(out)));}
app.whenReady().then(async()=>{
  app.setAccessibilitySupportEnabled(true);
  const win=new BrowserWindow({width:900,height:650,show:false});
  try{
    await win.loadFile(path.join(__dirname,'selftest.html'));win.showInactive();await new Promise(r=>setTimeout(r,500));
    const hwnd=Number(win.getNativeWindowHandle().readBigUInt64LE());
    async function query(name){return JSON.parse(await python('import json;from supporter.windows import probe_caret;from supporter.targets import describe_target;print(json.dumps(describe_target(probe_caret('+JSON.stringify({hwnd,name})+') or {}),ensure_ascii=False))'));}
    const rich=await query('富文本输入框');
    if(rich.scope!=='editor'){
      const inspect=await python('import json;from supporter.windows import probe_caret;print(json.dumps(probe_caret('+JSON.stringify({hwnd,name:'__test-inspect__'})+'),ensure_ascii=False))');
      const validity=await python('from supporter.windows import u;print(u.IsWindow('+hwnd+'))');
      throw new Error('hwnd '+hwnd+' valid '+validity+' contenteditable classification: '+JSON.stringify(rich)+' tree: '+inspect);
    }
    assert.ok(rich.context.startsWith('富文本原文'));
    await win.webContents.executeJavaScript("const p=document.getElementById('readonly');p.focus();const r=document.createRange();r.selectNodeContents(p);getSelection().removeAllRanges();getSelection().addRange(r)");
    const readonly=await query('只读网页参考文字');assert.equal(readonly.scope,'reference','page selection is reference-only');assert.equal(readonly.context,'只读网页参考文字');
    const report={passed:true,richEditor:rich.scope,readonlySelection:readonly.scope};fs.writeFileSync(path.join(root,'.runtime','accessibility-test.json'),JSON.stringify(report,null,2));
  }catch(error){fs.writeFileSync(path.join(root,'.runtime','accessibility-test.json'),JSON.stringify({passed:false,error:error.stack}));}
  finally{win.destroy();app.quit();}
});
