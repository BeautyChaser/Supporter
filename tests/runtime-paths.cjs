'use strict';
// No Electron instance, installed backend, or network is started by this test.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {isDeepStrictEqual}=require('node:util');
const {initializePaths}=require('../desktop/runtime-paths.cjs');
const {CompletionStore}=require('../desktop/completion-store.cjs');
const repo=path.resolve(__dirname,'..');
const temporary=fs.mkdtempSync(path.join(repo,'.runtime','distribution-paths-'));
let passed=0;
function write(file,value){fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,typeof value==='string'?value:JSON.stringify(value));}
function snapshot(directory){
  const result={};
  if(fs.existsSync(directory))for(const entry of fs.readdirSync(directory,{withFileTypes:true})){
    const item=path.join(directory,entry.name);
    if(entry.isDirectory())for(const [name,value] of Object.entries(snapshot(item)))result[entry.name+'/'+name]=value;
    else result[entry.name]=fs.readFileSync(item).toString('base64');
  }
  return result;
}
function fixture(name){
  const root=path.join(temporary,name),resourcesPath=path.join(root,'Program Files with spaces','resources');
  const resourceRoot=path.join(resourcesPath,'supporter'),dataRoot=path.join(root,'User profile 中文','Supporter');
  const sourceRoot=path.join(root,'source private state');
  const defaults={backend:'codex',models:{},reasoning:{},codexConnection:{mode:'inherit',proxyUrl:''},onboarding:{completed:false}};
  write(path.join(resourceRoot,'defaults','settings.json'),defaults);
  write(path.join(resourceRoot,'backend-plugins','codex.json'),{schemaVersion:1,id:'codex'});
  write(path.join(resourceRoot,'backend-plugins','README.md'),'public plugin instructions');
  write(path.join(sourceRoot,'settings.json'),{privateFixture:'must-not-migrate',codexConnection:{mode:'proxy',proxyUrl:'http://private.invalid:9090'}});
  write(path.join(sourceRoot,'completions','user','habits.json'),{privateFixture:'must-not-migrate'});
  const setPaths=[];
  const app={isPackaged:true,getPath(name){assert.equal(name,'userData');return dataRoot;},setPath(name,value){setPaths.push([name,value]);}};
  return {root,sourceRoot,resourcesPath,resourceRoot,dataRoot,defaults,setPaths,app};
}
function readonlyResources(directory,callback){
  const methods=['mkdirSync','writeFileSync','appendFileSync','copyFileSync','renameSync','rmSync'];
  const originals=Object.fromEntries(methods.map(name=>[name,fs[name]]));
  const inside=value=>{const relative=path.relative(directory,path.resolve(String(value)));return relative===''||(!relative.startsWith('..'+path.sep)&&relative!=='..'&&!path.isAbsolute(relative));};
  for(const name of methods)fs[name]=function(...args){
    const destination=name==='copyFileSync'||name==='renameSync'?args[1]:args[0];
    assert.equal(inside(destination),false,'attempted to write installation resources: '+name);
    return originals[name](...args);
  };
  try{return callback();}finally{Object.assign(fs,originals);}
}
function test(name,run){run();passed++;process.stdout.write('PASS '+name+'\n');}
try{
  test('packaged paths use clean resources and per-user data, never old source state',()=>{
    const f=fixture('fresh'),before=snapshot(f.resourceRoot),sourceBefore=snapshot(f.sourceRoot);
    const result=readonlyResources(f.resourceRoot,()=>initializePaths({...f,env:{}}));
    assert.equal(result.packaged,true);assert.equal(result.fresh,true);
    assert.equal(result.resourceRoot,f.resourceRoot);assert.equal(result.dataRoot,f.dataRoot);
    assert.equal(result.python,path.join(f.resourceRoot,'python','python.exe'));
    assert.equal(result.settingsPath,path.join(f.dataRoot,'settings.json'));
    assert.deepEqual(JSON.parse(fs.readFileSync(result.settingsPath)),f.defaults);
    assert.deepEqual(JSON.parse(fs.readFileSync(path.join(result.pluginRoot,'codex.json'))),{schemaVersion:1,id:'codex'});
    assert.deepEqual(snapshot(f.resourceRoot),before);assert.deepEqual(snapshot(f.sourceRoot),sourceBefore);
    assert.equal(result.environment.SUPPORTER_RESOURCE_ROOT,f.resourceRoot);
    assert.equal(result.environment.SUPPORTER_DATA_DIR,f.dataRoot);
    assert.equal(result.environment.SUPPORTER_BACKEND_DIR,result.pluginRoot);
    assert.equal(result.environment.PYTHONDONTWRITEBYTECODE,'1');assert.equal(result.environment.PYTHONIOENCODING,'utf-8');
    assert.deepEqual(f.setPaths,[]);
  });
  test('personal completion initialization creates no migrated habits or resource writes',()=>{
    const f=fixture('completions'),before=snapshot(f.resourceRoot);
    const result=initializePaths({...f,env:{}});
    readonlyResources(f.resourceRoot,()=>new CompletionStore(result.completionRoot));
    const habits=JSON.parse(fs.readFileSync(path.join(result.completionRoot,'habits.json')));
    assert.deepEqual(habits,{version:1,environments:{}});
    assert.equal(JSON.stringify(snapshot(f.dataRoot)).includes('must-not-migrate'),false);
    assert.deepEqual(snapshot(f.resourceRoot),before);
  });
  test('restart and update preserve existing settings and user plugins byte for byte',()=>{
    const f=fixture('restart'),first=initializePaths({...f,env:{}});
    const settings='{"user":"fixture","codexConnection":{"mode":"direct"}}\n';
    const plugin='{"schemaVersion":1,"id":"codex","enabled":false}\n';
    write(first.settingsPath,settings);write(path.join(first.pluginRoot,'codex.json'),plugin);
    write(path.join(f.resourceRoot,'defaults','settings.json'),{newDefault:'must-not-replace-user'});
    const second=readonlyResources(f.resourceRoot,()=>initializePaths({...f,env:{}}));
    assert.equal(second.fresh,false);assert.equal(fs.readFileSync(second.settingsPath,'utf8'),settings);
    assert.equal(fs.readFileSync(path.join(second.pluginRoot,'codex.json'),'utf8'),plugin);
  });
  test('explicit portable paths affect only returned child environment and selected userData',()=>{
    const f=fixture('portable'),dataRoot=path.join(f.root,'portable data 中文');
    const env={SUPPORTER_RESOURCE_ROOT:f.resourceRoot,SUPPORTER_DATA_DIR:dataRoot,
      SUPPORTER_BACKEND_DIR:path.join(dataRoot,'my plugins'),SUPPORTER_COMPLETION_ROOT:path.join(dataRoot,'my completions'),
      SUPPORTER_PYTHON:path.join(f.root,'custom interpreter','python.exe'),HTTP_PROXY:'http://fixture.invalid:8080'};
    const original={...env},processBefore={...process.env};
    const result=readonlyResources(f.resourceRoot,()=>initializePaths({...f,env}));
    assert.equal(result.dataRoot,dataRoot);assert.equal(result.python,env.SUPPORTER_PYTHON);
    assert.equal(result.pluginRoot,env.SUPPORTER_BACKEND_DIR);assert.equal(result.completionRoot,env.SUPPORTER_COMPLETION_ROOT);
    assert.deepEqual(f.setPaths,[['userData',path.join(dataRoot,'chromium')]]);
    assert.equal(isDeepStrictEqual(env,original),true,'caller environment changed');
    assert.equal(isDeepStrictEqual({...process.env},processBefore),true,'parent environment changed');
    assert.equal(result.environment.HTTP_PROXY,env.HTTP_PROXY);
    assert.equal(fs.existsSync(path.join(f.dataRoot,'settings.json')),false);
  });
  test('relative plugin and completion overrides become absolute before child cwd changes',()=>{
    const f=fixture('relative');
    const pluginRoot=path.relative(process.cwd(),path.join(f.root,'custom plugins'));
    const completionRoot=path.relative(process.cwd(),path.join(f.root,'custom completions'));
    const result=initializePaths({...f,env:{SUPPORTER_BACKEND_DIR:pluginRoot,SUPPORTER_COMPLETION_ROOT:completionRoot}});
    assert.equal(result.pluginRoot,path.resolve(pluginRoot));assert.equal(result.completionRoot,path.resolve(completionRoot));
    assert.equal(result.environment.SUPPORTER_BACKEND_DIR,result.pluginRoot);
  });
  test('development default keeps source layout and still does not overwrite settings',()=>{
    const f=fixture('development');f.app.isPackaged=false;
    const before=snapshot(f.sourceRoot);const result=initializePaths({...f,env:{}});
    assert.equal(result.resourceRoot,f.sourceRoot);assert.equal(result.dataRoot,f.sourceRoot);
    assert.equal(result.python,'python.exe');assert.equal(result.fresh,false);
    assert.equal(fs.readFileSync(result.settingsPath,'utf8'),Buffer.from(before['settings.json'],'base64').toString());
  });
  process.stdout.write(JSON.stringify({passed:true,cases:passed,networkRequests:0})+'\n');
}finally{fs.rmSync(temporary,{recursive:true,force:true});}
