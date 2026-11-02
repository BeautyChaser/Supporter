const {app,BrowserWindow}=require('electron');
const {execFile}=require('node:child_process');
const path=require('node:path');
const fs=require('node:fs');
const root=path.resolve(__dirname,'..');
function python(code){return new Promise((resolve,reject)=>execFile('python.exe',['-c',code],{cwd:root,windowsHide:true,encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}},(error,out,err)=>error?reject(new Error(err||error.message)):resolve(out)));}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
app.whenReady().then(async()=>{
  app.setAccessibilitySupportEnabled(true);
  const win=new BrowserWindow({width:900,height:650,show:true,alwaysOnTop:true});
  try{
    await win.loadFile(path.join(__dirname,'selftest.html'));win.focus();
    const ownHandle=Number(win.getNativeWindowHandle().readBigUInt64LE());
    await python('from supporter.windows import restore;restore({"hwnd":'+ownHandle+'})');
    await sleep(200);
    win.show();win.focus();
    await win.webContents.executeJavaScript("document.querySelector('textarea').focus()");
    await win.webContents.executeJavaScript("window.testKeys=[];document.addEventListener('keydown',e=>window.testKeys.push([e.key,e.ctrlKey,e.shiftKey]));");
    await sleep(600);
    let target=JSON.parse(await python("import json;from supporter.windows import capture;print(json.dumps(capture(),ensure_ascii=False))"));
    for(let attempt=0;target.hwnd!==ownHandle&&attempt<2;attempt++){
      win.focus();await python('from supporter.windows import restore;restore({"hwnd":'+ownHandle+'})');await sleep(200);
      target=JSON.parse(await python("import json;from supporter.windows import capture;print(json.dumps(capture(),ensure_ascii=False))"));
    }
    if(target.hwnd!==ownHandle)throw new Error('Test editor not foreground; input test skipped');
    if(target.context!=='原始文字'||target.scope!=='editor')throw new Error('Input capture failed: '+JSON.stringify(target));
    if(!target.caret)throw new Error('Caret/editor anchor missing');
    await python('from supporter.windows import insert;import json;insert(json.loads('+JSON.stringify(JSON.stringify(target))+'),"替换后的文字",replace=True)');
    await sleep(300);
    const value=await win.webContents.executeJavaScript("document.querySelector('textarea').value");
    if(value!=='替换后的文字')throw new Error('Replacement failed: '+value+' details: '+await win.webContents.executeJavaScript("JSON.stringify({keys:window.testKeys,active:document.activeElement.id,selection:[editor.selectionStart,editor.selectionEnd]})"));
    await win.webContents.executeJavaScript("editor.focus();editor.setSelectionRange(0,2)");
    const selected=JSON.parse(await python("import json;from supporter.windows import capture;print(json.dumps(capture(),ensure_ascii=False))"));
    if(selected.hwnd!==ownHandle||selected.scope!=='selection'||selected.context!=='替换')throw new Error('Selection capture failed');
    await python('from supporter.windows import insert;import json;insert(json.loads('+JSON.stringify(JSON.stringify(selected))+'),"修订",replace=True)');
    await sleep(200);
    if(await win.webContents.executeJavaScript('editor.value')!=='修订后的文字')throw new Error('Selection replacement failed');
    await win.webContents.executeJavaScript("editor.value='';editor.focus()");
    const empty=JSON.parse(await python("import json;from supporter.windows import capture;print(json.dumps(capture(),ensure_ascii=False))"));
    if(empty.hwnd!==ownHandle||empty.context!==''||empty.scope!=='editor'||!empty.caret)throw new Error('Empty editor capture failed');
    await win.webContents.executeJavaScript("window.getSelection().removeAllRanges();document.getElementById('rich').focus()");
    const rich=JSON.parse(await python("import json;from supporter.windows import capture;print(json.dumps(capture(),ensure_ascii=False))"));
    if(rich.hwnd!==ownHandle||rich.scope!=='editor'||!rich.context.startsWith('富文本原文'))throw new Error('Rich editor misclassified: '+JSON.stringify(rich));
    await python('from supporter.windows import insert;import json;insert(json.loads('+JSON.stringify(JSON.stringify(rich))+'),"新的富文本",replace=True)');
    await sleep(200);
    if(await win.webContents.executeJavaScript("document.getElementById('rich').innerText")!=='新的富文本')throw new Error('Rich editor replacement failed');
    await win.webContents.executeJavaScript("const p=document.getElementById('readonly');p.focus();const range=document.createRange();range.selectNodeContents(p);getSelection().removeAllRanges();getSelection().addRange(range)");
    const reference=JSON.parse(await python("import json;from supporter.windows import capture;print(json.dumps(capture(),ensure_ascii=False))"));
    if(reference.hwnd!==ownHandle||reference.scope!=='reference'||reference.context!=='只读网页参考文字')throw new Error('Readonly page selection misclassified: '+JSON.stringify(reference));
    const report={passed:true,source:target.source,scope:target.scope,x:target.x,y:target.y,value,selectedReplacement:true,emptyEditorAnchor:true,richEditorReplacement:true,readonlyReference:true};
    fs.writeFileSync(path.join(root,'.runtime','integration-test.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report));
  }catch(error){console.error(error);fs.writeFileSync(path.join(root,'.runtime','integration-test.json'),JSON.stringify({passed:false,error:error.message}));process.exitCode=1;}
  finally{win.destroy();app.quit();}
});
