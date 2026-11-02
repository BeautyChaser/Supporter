const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('supporter',{
  send:data=>ipcRenderer.send('action',data),
  onEvent:callback=>ipcRenderer.on('event',(_,data)=>callback(data))
});
