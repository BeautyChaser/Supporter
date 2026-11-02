const {app,BrowserWindow,clipboard}=require('electron');
const {execFile}=require('node:child_process');const path=require('node:path');const fs=require('node:fs');const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..');const file=path.join(root,'.runtime','rich-production-test.json');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function python(args,input=null){return new Promise((resolve,reject)=>{const child=execFile('python.exe',args,{cwd:root,windowsHide:true,encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}},(e,out,err)=>e?reject(new Error(err||e.message)):resolve(out));if(input!==null)child.stdin.end(JSON.stringify(input));});}
app.on('window-all-closed',()=>{});
app.whenReady().then(async()=>{
  let window;const report={passed:false,startedAt:new Date().toISOString(),productionPath:true};
  const deadline=setTimeout(()=>{report.error='fixture deadline';fs.writeFileSync(file,JSON.stringify(report,null,2));app.exit(2);},15000);
  try{
    app.setAccessibilitySupportEnabled(true);window=new BrowserWindow({width:960,height:700,frame:false,show:false});
    await window.loadFile(path.join(__dirname,'../terminal-fixture-app/editor.html'));
    window.show();window.focus();const hwnd=Number(window.getNativeWindowHandle().readBigUInt64LE());
    await python(['-c','from supporter.windows import restore;restore({"hwnd":'+hwnd+'})']);
    await window.webContents.executeJavaScript('document.getElementById("rich").focus();getSelection().removeAllRanges();getSelection().collapse(document.getElementById("rich"),0)');
    await sleep(150);
    const foreground=Number((await python(['-c','from supporter.windows import u;print(u.GetForegroundWindow())'])).trim());
    if(foreground!==hwnd){report.skipped='fixture not foreground; no physical input sent';}
    else{
      const target=JSON.parse(await python(['-c','import json;from supporter.windows import capture;print(json.dumps(capture(),ensure_ascii=False))']));
      if(target.hwnd!==hwnd)throw new Error('capture changed foreground; physical write skipped');
      assert.equal(await window.webContents.executeJavaScript('document.activeElement.id'),'rich','DOM focus verified');
      report.captured={scope:target.scope,pasteMode:target.paste_mode,source:target.source,contextMatches:target.context==='富文本原文'};
      assert.equal(target.scope,'editor');assert.equal(target.paste_mode,'soft-lines');assert.equal(target.context,'富文本原文');
      const text='## Markdown 标题\n\n第一段\n第二段';
      await python(['-m','tests.rich_production_writer'],{target,text});await sleep(180);
      const actual=await window.webContents.executeJavaScript('document.getElementById("rich").innerText');
      report.actualLength=actual.length;report.expectedLength=text.length;
      assert.ok(actual===text,'production rich replacement must keep exact LF content');
      assert.ok((await clipboard.readText()).replace(/\r\n/g,'\n')===text,'full result remains on clipboard');
      report.richExact=true;report.clipboardRetained=true;
      await window.webContents.executeJavaScript('const plain=document.getElementById("plain");plain.focus();plain.setSelectionRange(0,0)');
      const beforePlain=Number((await python(['-c','from supporter.windows import u;print(u.GetForegroundWindow())'])).trim());
      if(beforePlain!==hwnd)report.plainSkipped='fixture lost foreground; no additional physical input';
      else{
        const plainTarget=JSON.parse(await python(['-c','import json;from supporter.windows import capture;print(json.dumps(capture(),ensure_ascii=False))']));
        assert.equal(plainTarget.hwnd,hwnd);assert.equal(plainTarget.scope,'editor');
        const plainText='# 标题\n\n第一段 Ω\n第二段\n';
        await python(['-m','tests.rich_production_writer'],{target:plainTarget,text:plainText});await sleep(180);
        const plainActual=await window.webContents.executeJavaScript('document.getElementById("plain").value');
        report.plain={pasteMode:plainTarget.paste_mode,actualLength:plainActual.length,expectedLength:plainText.length,exact:plainActual===plainText};
        assert.ok(report.plain.exact,'production textarea multiline replacement must keep exact LF content');
      }
      report.passed=true;
    }
  }catch(error){report.error=error.stack;if(/foreground|焦点/.test(error.message))report.inconclusive='focus changed; no retry or input to another window';}
  finally{clearTimeout(deadline);report.finishedAt=new Date().toISOString();fs.writeFileSync(file,JSON.stringify(report,null,2));if(window&&!window.isDestroyed())window.destroy();app.quit();}
});
