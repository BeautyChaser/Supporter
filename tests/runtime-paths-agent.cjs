/* Pure path tests: every resource/profile path belongs to this test fixture. */
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {initializePaths}=require('../desktop/runtime-paths.cjs');
const root=path.resolve(__dirname,'..');
const directory=fs.mkdtempSync(path.join(root,'.runtime','runtime-paths-agent-'));
const report={runId:new Date().toISOString(),passed:false,tests:[]};
function test(name,run){try{run();report.tests.push({name,passed:true});}catch(error){report.tests.push({name,passed:false,error:String(error.stack||error)});}}
function fixture(name){
  const base=path.join(directory,name),resourcesPath=path.join(base,'resources'),sourceRoot=path.join(base,'source'),profile=path.join(base,'profile'),calls=[];
  fs.mkdirSync(sourceRoot,{recursive:true});fs.mkdirSync(resourcesPath,{recursive:true});
  const app={isPackaged:true,getPath:key=>{assert.equal(key,'userData');return profile;},setPath:(key,value)=>calls.push({key,value})};
  return {base,resourcesPath,sourceRoot,profile,app,calls};
}
function writeJson(file,value){fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(value));}
test('packaged defaults and plugins copy to the profile while Python stays in resources',()=>{
  const f=fixture('packaged'),resourceRoot=path.join(f.resourcesPath,'supporter');
  writeJson(path.join(resourceRoot,'defaults','settings.json'),{backend:'codex',onboarding:{completed:false}});
  writeJson(path.join(resourceRoot,'backend-plugins','fixture.json'),{name:'fixture'});
  fs.writeFileSync(path.join(resourceRoot,'backend-plugins','ignored.exe'),'fixture only');
  const result=initializePaths({...f,env:{}});
  assert.equal(result.dataRoot,f.profile);assert.equal(result.resourceRoot,resourceRoot);assert.equal(result.python,path.join(resourceRoot,'python','python.exe'));
  assert.equal(result.runtimeRoot,path.join(f.profile,'.runtime'));assert.equal(result.settingsPath,path.join(f.profile,'settings.json'));assert.equal(result.completionRoot,path.join(f.profile,'completions','user'));
  assert.deepEqual(JSON.parse(fs.readFileSync(result.settingsPath,'utf8')),{backend:'codex',onboarding:{completed:false}});assert.ok(fs.existsSync(path.join(result.pluginRoot,'fixture.json')));assert.ok(!fs.existsSync(path.join(result.pluginRoot,'ignored.exe')));assert.equal(result.fresh,true);
});
test('explicit data and resource overrides stay separate and reach the Python environment',()=>{
  const f=fixture('override'),dataRoot=path.join(f.base,'isolated-data'),resourceRoot=path.join(f.base,'immutable-resources');fs.mkdirSync(resourceRoot,{recursive:true});
  const result=initializePaths({...f,env:{SUPPORTER_DATA_DIR:dataRoot,SUPPORTER_RESOURCE_ROOT:resourceRoot,PATH:'fixture-only'}});
  assert.equal(result.dataRoot,dataRoot);assert.equal(result.resourceRoot,resourceRoot);assert.deepEqual(f.calls,[{key:'userData',value:path.join(dataRoot,'chromium')}]);
  assert.equal(result.environment.SUPPORTER_DATA_DIR,dataRoot);assert.equal(result.environment.SUPPORTER_RESOURCE_ROOT,resourceRoot);assert.equal(result.environment.SUPPORTER_BACKEND_DIR,path.join(dataRoot,'backend-plugins'));assert.equal(result.environment.PYTHONDONTWRITEBYTECODE,'1');assert.equal(result.environment.PATH,'fixture-only');
  assert.deepEqual(fs.readdirSync(resourceRoot),[],'immutable resources must not receive settings, logs or generated files');
});
test('existing user settings and plugin edits survive reinitialization',()=>{
  const f=fixture('existing'),resourceRoot=path.join(f.resourcesPath,'supporter');writeJson(path.join(resourceRoot,'defaults','settings.json'),{backend:'bundled-default'});writeJson(path.join(resourceRoot,'backend-plugins','fixture.json'),{name:'bundled'});
  writeJson(path.join(f.profile,'settings.json'),{backend:'user-choice',onboarding:{completed:true}});writeJson(path.join(f.profile,'backend-plugins','fixture.json'),{name:'edited'});
  const result=initializePaths({...f,env:{}});assert.equal(result.fresh,false);assert.equal(JSON.parse(fs.readFileSync(result.settingsPath,'utf8')).backend,'user-choice');assert.equal(JSON.parse(fs.readFileSync(path.join(result.pluginRoot,'fixture.json'),'utf8')).name,'edited');
});
test('development overrides never import a project settings file',()=>{
  const f=fixture('development');f.app.isPackaged=false;writeJson(path.join(f.sourceRoot,'settings.json'),{fixtureValue:'must-not-import'});writeJson(path.join(f.sourceRoot,'defaults','settings.json'),{backend:'safe-default',onboarding:{completed:false}});
  const result=initializePaths({...f,env:{SUPPORTER_DATA_DIR:path.join(f.base,'isolated-data')}});assert.equal(result.resourceRoot,f.sourceRoot);assert.equal(result.python,'python.exe');assert.deepEqual(JSON.parse(fs.readFileSync(result.settingsPath,'utf8')),{backend:'safe-default',onboarding:{completed:false}});
});
test('explicit Python, plugin and completion directories are honored without personal paths',()=>{
  const f=fixture('custom'),pluginRoot=path.join(f.base,'custom-plugins'),completionRoot=path.join(f.base,'custom-completions');
  const result=initializePaths({...f,env:{SUPPORTER_PYTHON:path.join(f.base,'custom-python.exe'),SUPPORTER_BACKEND_DIR:pluginRoot,SUPPORTER_COMPLETION_ROOT:completionRoot}});assert.equal(result.python,path.join(f.base,'custom-python.exe'));assert.equal(result.pluginRoot,pluginRoot);assert.equal(result.completionRoot,completionRoot);assert.ok(fs.existsSync(pluginRoot));
});
report.passed=report.tests.every(item=>item.passed);fs.writeFileSync(path.join(root,'.runtime','runtime-paths-agent-report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));if(!report.passed)process.exitCode=1;
