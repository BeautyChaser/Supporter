const fs=require('node:fs');
const path=require('node:path');

function initializePaths({app,sourceRoot=path.resolve(__dirname,'..'),env=process.env,resourcesPath=process.resourcesPath}){
  const packaged=Boolean(app.isPackaged);
  const resourceRoot=path.resolve(env.SUPPORTER_RESOURCE_ROOT||(packaged?path.join(resourcesPath,'supporter'):sourceRoot));
  const dataRoot=path.resolve(env.SUPPORTER_DATA_DIR||(packaged?app.getPath('userData'):sourceRoot));
  const runtimeRoot=path.join(dataRoot,'.runtime');
  fs.mkdirSync(runtimeRoot,{recursive:true});
  if(env.SUPPORTER_DATA_DIR)app.setPath('userData',path.join(dataRoot,'chromium'));
  const settingsPath=path.join(dataRoot,'settings.json');
  const fresh=!fs.existsSync(settingsPath);
  if(fresh){
    const defaults=path.join(resourceRoot,'defaults','settings.json');
    if(fs.existsSync(defaults))fs.copyFileSync(defaults,settingsPath);
  }
  const pluginRoot=path.resolve(env.SUPPORTER_BACKEND_DIR||path.join(dataRoot,'backend-plugins'));
  if(!fs.existsSync(pluginRoot)){
    fs.mkdirSync(pluginRoot,{recursive:true});
    const bundled=path.join(resourceRoot,'backend-plugins');
    if(fs.existsSync(bundled))for(const name of fs.readdirSync(bundled))if(/\.(json|md|example)$/.test(name))fs.copyFileSync(path.join(bundled,name),path.join(pluginRoot,name));
  }
  const python=env.SUPPORTER_PYTHON||(packaged?path.join(resourceRoot,'python','python.exe'):'python.exe');
  return {packaged,resourceRoot,dataRoot,runtimeRoot,settingsPath,pluginRoot,python,fresh,
    completionRoot:path.resolve(env.SUPPORTER_COMPLETION_ROOT||path.join(dataRoot,'completions','user')),
    environment:{...env,SUPPORTER_RESOURCE_ROOT:resourceRoot,SUPPORTER_DATA_DIR:dataRoot,SUPPORTER_BACKEND_DIR:pluginRoot,PYTHONIOENCODING:'utf-8',PYTHONDONTWRITEBYTECODE:'1'}};
}
module.exports={initializePaths};
