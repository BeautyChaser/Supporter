const {BrowserWindow,dialog}=require('electron');
const path=require('node:path');

function createSettingsWindow({window:existing,directory,getData,onError=()=>{}}){
  const window=existing||new BrowserWindow({width:850,height:650,minWidth:760,minHeight:560,
    title:'Supporter 设置',show:false,backgroundColor:'#202229',autoHideMenuBar:true,
    webPreferences:{preload:path.join(directory,'preload.cjs'),contextIsolation:true,
      nodeIntegration:false,sandbox:true,backgroundThrottling:false}});
  if(existing){
    window.setMinimumSize(760,560);window.setResizable(true);window.setAlwaysOnTop(false);
    window.setSkipTaskbar(false);window.setOpacity(1);window.setBackgroundColor('#202229');
    window.setSize(850,650);window.center();window.setTitle('Supporter 设置');
  }
  const contents=window.webContents;
  contents.setWindowOpenHandler(()=>({action:'deny'}));
  contents.on('render-process-gone',(_,details)=>onError(new Error('设置页渲染进程退出：'+details.reason)));
  // Install listeners before navigation. Do not expose a blank native window
  // while its separate renderer is still starting.
  window.supporterReady=(async()=>{
    await window.loadFile(path.join(directory,'settings.html'));
    const valid=await contents.executeJavaScript('Boolean(document.querySelector("#form") && document.querySelectorAll("nav button").length===4 && window.supporter)');
    if(!valid)throw new Error('设置页面未完成初始化');
    contents.send('event',{type:'settings-data',...getData()});
    // Hidden Chromium renderers may suspend requestAnimationFrame. Showing the
    // ready DOM must precede waiting for a first painted frame.
    if(!window.isDestroyed()){
      window.show();window.focus();contents.invalidate();
      await contents.executeJavaScript('document.fonts.ready.then(()=>true)');
      await new Promise(resolve=>setTimeout(resolve,120));
    }
    return window;
  })();
  window.supporterReady.catch(error=>{
    onError(error);
    if(!window.isDestroyed()){
      dialog.showErrorBox('Supporter 设置加载失败',error.message+'\n请关闭后从托盘重新打开设置。');window.destroy();
    }
  });
  return window;
}
module.exports={createSettingsWindow};
