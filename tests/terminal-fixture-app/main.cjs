const {app,BrowserWindow,screen,clipboard}=require('electron');
const {execFile}=require('node:child_process');
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..');
const reportPath=path.join(root,'.runtime','terminal-fixture-test.json');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function python(code){return new Promise((resolve,reject)=>execFile('python.exe',['-c',code],{cwd:root,windowsHide:true,encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}},(e,out,err)=>e?reject(new Error(err||e.message)):resolve(out)));}
function softlines(hwnd,text){return new Promise((resolve,reject)=>{const child=execFile('python.exe',['-m','tests.rich_softline_writer',String(hwnd)],{cwd:root,windowsHide:true,encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}},(e,out,err)=>e?reject(new Error(err||e.message)):resolve(out));child.stdin.end(JSON.stringify({text}));});}
app.on('window-all-closed',()=>{});
app.whenReady().then(async()=>{
  let window;const report={passed:false,startedAt:new Date().toISOString(),physicalWriteback:'not attempted'};
  const deadline=setTimeout(()=>{report.error='fixture timeout';fs.writeFileSync(reportPath,JSON.stringify(report,null,2));app.exit(2);},15000);
  try{
    app.setAccessibilitySupportEnabled(true);
    window=new BrowserWindow({width:960,height:700,frame:false,show:false});
    await window.loadFile(path.join(__dirname,'editor.html'));window.showInactive();await sleep(400);
    const hwnd=Number(window.getNativeWindowHandle().readBigUInt64LE());
    async function query(name){return JSON.parse(await python('import json;from supporter.windows import probe_caret;print(json.dumps(probe_caret('+JSON.stringify({hwnd,name})+'),ensure_ascii=False))'));}
    const plain=await query('普通多行编辑框');assert.ok(plain&&plain.editable,'plain editor exposed');
    assert.equal(plain.text,'第一行\n第二行\n\n第四行');report.multilineReadPreserved=true;
    const cell=await query('Terminal input');assert.ok(cell&&cell.terminal,'xterm helper identified');
    assert.equal(cell.source,'xterm-input-cell');assert.ok(cell.width<=15&&cell.height>=20);
    const content=window.getContentBounds();
    const expected=screen.dipToScreenPoint({x:content.x+500,y:content.y+440});
    assert.ok(Math.abs(cell.x-expected.x)<=3&&Math.abs(cell.y-expected.y)<=3,'anchor matches helper cell rather than application origin');
    report.xtermCellAnchor={passed:true,source:cell.source,width:cell.width,height:cell.height};
    const rich=await query('富文本多行编辑框');assert.ok(rich&&rich.editable);report.richEditorRecognized=true;
    // The only physical input target is this explicitly identified local
    // fixture. If Windows won't foreground it, never send input elsewhere.
    window.show();window.focus();
    await python('from supporter.windows import restore;restore({"hwnd":'+hwnd+'})');
    await window.webContents.executeJavaScript('document.getElementById("plain").focus();document.getElementById("plain").select()');
    await sleep(150);
    const foreground=Number((await python('from supporter.windows import u;print(u.GetForegroundWindow())')).trim());
    if(foreground!==hwnd){report.physicalWriteback='skipped: test window could not acquire foreground';report.clipboardRestore='not attempted';}
    else{
      const replacement='# 标题\n\n第一段 Ω\n第二段\n';
      await window.webContents.executeJavaScript('window.pasteTrace=[];window.expectedPayload='+JSON.stringify(replacement)+';document.getElementById("plain").addEventListener("paste",event=>{const value=event.clipboardData.getData("text/plain");window.pasteTrace.push({type:"paste",length:value.length,matches:value===window.expectedPayload});});for(const name of ["keydown","keyup","beforeinput","input"]){document.addEventListener(name,event=>window.pasteTrace.push({type:name,key:["Control","Enter","v","V"].includes(event.key)?event.key:null,inputType:event.inputType||null,dataLength:typeof event.data==="string"?event.data.length:null}));}');
      await python('from supporter.windows import u,paste_text;import sys;sys.exit(3) if u.GetForegroundWindow()!='+hwnd+' else paste_text('+JSON.stringify(replacement)+',expected_hwnd='+hwnd+')');
      await sleep(180);
      const inserted=await window.webContents.executeJavaScript('document.getElementById("plain").value');
      report.pasteEvents=await window.webContents.executeJavaScript('window.pasteTrace');
      if(inserted!==replacement){report.plainDifference={prefixMatches:inserted.startsWith(replacement),extraLength:inserted.length-replacement.length,extraCodepoint:inserted.startsWith(replacement)&&inserted.length===replacement.length+1?inserted.charCodeAt(inserted.length-1):null};}
      assert.ok(inserted===replacement,'physical paste did not match multiline payload (actual length '+inserted.length+', expected '+replacement.length+')');
      report.physicalWriteback='passed: multiline LF, blank lines and unicode';
      const currentClipboard=(await clipboard.readText()).replace(/\r\n/g,'\n');
      assert.ok(currentClipboard===replacement,'accepted result remains on clipboard for Ctrl+V');
      report.clipboardResultRetained=true;
      const richPayload='## Markdown 标题\n\n第一段\n第二段';
      await window.webContents.executeJavaScript('const editor=document.getElementById("rich");editor.focus();const selection=getSelection();const range=document.createRange();range.selectNodeContents(editor);selection.removeAllRanges();selection.addRange(range);');
      if(process.argv.includes('--rich-softlines')){report.richStrategy='experiment: unicode segments + ShiftEnter';await softlines(hwnd,richPayload);}
      else await python('from supporter.windows import paste_text;paste_text('+JSON.stringify(richPayload)+',expected_hwnd='+hwnd+',plain=True)');
      await sleep(180);
      const richValue=await window.webContents.executeJavaScript('document.getElementById("rich").innerText');
      if(richValue!==richPayload)report.richFixtureActual=JSON.stringify(richValue);
      assert.ok(richValue===richPayload,'rich editor keeps Markdown paragraphs and line breaks (length '+richValue.length+', expected '+richPayload.length+')');
      report.richPhysicalMultilineWriteback=true;
    }
    report.passed=true;
  }catch(e){report.error=e.stack;}
  finally{clearTimeout(deadline);report.finishedAt=new Date().toISOString();fs.writeFileSync(reportPath,JSON.stringify(report,null,2));if(window&&!window.isDestroyed())window.destroy();app.quit();}
});
