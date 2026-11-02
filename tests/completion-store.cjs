// Local-only regression tests. Every mutable path is created beneath .runtime.
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const {CompletionStore}=require('../desktop/completion-store.cjs');
const completion=require('../desktop/completion.js');
const runtime=path.resolve(__dirname,'../.runtime');fs.mkdirSync(runtime,{recursive:true});
const tests=[];const test=(name,run)=>tests.push({name,run});
const write=(directory,name,data)=>fs.writeFileSync(path.join(directory,name),JSON.stringify(data,null,2)+'\n','utf8');
function sandbox(run){
  const directory=fs.mkdtempSync(path.join(runtime,'completion-store-test-'));
  try{return run(directory,new CompletionStore(directory));}
  finally{
    completion.configure({commands:{},usage:{}});
    const resolved=fs.realpathSync(directory),relative=path.relative(runtime,resolved);
    assert.ok(relative&&!relative.startsWith('..')&&!path.isAbsolute(relative),'cleanup stays under the test runtime');
    fs.rmSync(resolved,{recursive:true,force:true});
  }
}
const allNames=env=>completion.catalog(env).map(c=>c.name);
function inspect(value,env){return completion.inspect(value,value.length-1,env).options;}
const usage=(store,env,name)=>store.snapshot().usage[env].find(c=>c.name===name);

test('initializes only the three user catalogs and separate learning/config files',()=>sandbox((directory,store)=>{
  assert.deepEqual(fs.readdirSync(directory).sort(),['bash.json','cmd.json','config.json','habits.json','powershell.json']);
  assert.equal(store.snapshot().learning,true);assert.deepEqual(store.snapshot().errors,[]);
}));

test('custom catalogs are isolated by environment and survive reload/restart',()=>sandbox((directory,store)=>{
  const custom={bash:{name:'acme-bash',description:'Bash 自定义',aliases:['ab'],flags:[['--scan','扫描']],values:{'--mode=':['fast','careful']}},
    powershell:{name:'Get-AcmeReport',flags:[['-Scan','扫描']]},cmd:{name:'acmecmd',flags:[['/scan','扫描']]}};
  for(const [env,row] of Object.entries(custom))write(directory,env+'.json',{version:1,commands:[row]});
  store.reload();completion.configure(store.snapshot());
  for(const [env,row] of Object.entries(custom)){
    assert.ok(allNames(env).includes(row.name));
    for(const other of completion.shellEnvs.filter(e=>e!==env))assert.ok(!allNames(other).includes(row.name));
  }
  assert.ok(inspect('`acme-bash --s`','bash').some(o=>o.value==='--scan'));
  assert.ok(inspect('`ab --s`','bash').some(o=>o.value==='--scan'));
  const restarted=new CompletionStore(directory);completion.configure(restarted.snapshot());
  assert.ok(allNames('bash').includes('acme-bash'));
  assert.deepEqual(completion.catalog('bash').find(c=>c.name==='acme-bash').values['--mode='].map(v=>v.value),['fast','careful']);
}));

test('extending a PowerShell command retains built-in aliases and adds custom aliases',()=>sandbox((directory,store)=>{
  write(directory,'powershell.json',{version:1,commands:[{name:'Get-ChildItem',aliases:['items'],flags:[['-ExtraView','自定义显示选项']]}]});
  store.reload();completion.configure(store.snapshot());
  const row=completion.catalog('powershell').find(c=>c.name==='Get-ChildItem');
  for(const alias of ['gci','ls','dir','items'])assert.ok(row.aliases.includes(alias),alias+' alias must survive extension');
  assert.ok(inspect('`ls -Extra`','powershell').some(o=>o.value==='-ExtraView'));
  assert.ok(inspect('`items -Fo`','powershell').some(o=>o.value==='-Force'));
}));

test('extending NVIDIA flags retains public query values and merges new value prefixes',()=>sandbox((directory,store)=>{
  write(directory,'bash.json',{version:1,commands:[{name:'nvidia-smi',flags:['--local-view'],values:{'--local-mode=':['fast']}}]});
  store.reload();completion.configure(store.snapshot());
  const row=completion.catalog('bash').find(c=>c.name==='nvidia-smi');
  assert.ok(row.flags.some(o=>o.value==='--local-view'));
  assert.ok(row.values['--query-gpu='].some(o=>o.value==='memory.used'));
  assert.ok(row.values['--format='].some(o=>o.value==='csv,noheader'));
  assert.deepEqual(row.values['--local-mode='].map(o=>o.value),['fast']);
  assert.ok(inspect('`nvidia-smi --query-gpu=mem`','bash').some(o=>o.value==='--query-gpu=memory.used'));
  assert.ok(inspect('`nvidia-smi --local-mode=f`','bash').some(o=>o.value==='--local-mode=fast'));
}));

test('aliases are command-name completion candidates instead of recognition-only shortcuts',()=>sandbox((directory,store)=>{
  write(directory,'powershell.json',{version:1,commands:[{name:'Get-ChildItem',aliases:['myitems']} ]});
  store.reload();completion.configure(store.snapshot());
  const builtin=inspect('`gc`','powershell').find(o=>o.value==='gci');
  assert.ok(builtin);assert.match(builtin.description,/别名.*Get-ChildItem/);
  const custom=inspect('`myi`','powershell').find(o=>o.value==='myitems');assert.ok(custom);
  assert.match(custom.description,/别名.*Get-ChildItem/);
  const value='`myi`';const applied=completion.apply(value,custom);assert.equal(applied.value,'`myitems`');
}));

test('usage ranks known/custom commands and options and persists counts',()=>sandbox((directory,store)=>{
  write(directory,'bash.json',{version:1,commands:[{name:'acme-low'},{name:'acme-high',flags:['--alpha','--zebra']}]});
  assert.ok(store.observe('`acme-low`','bash'));
  for(let i=0;i<3;i++)assert.ok(store.observe('acme-high --zebra','bash',true));
  assert.ok(store.observe('acme-high --alpha','bash',true));
  const restarted=new CompletionStore(directory);completion.configure(restarted.snapshot());
  assert.equal(usage(restarted,'bash','acme-high').count,4);
  assert.equal(inspect('`acme-`','bash')[0].value,'acme-high');
  assert.equal(inspect('`acme-high --`','bash')[0].value,'--zebra');
}));

test('only submitted single-backtick commands or explicit confirmed raw commands are learned',()=>sandbox((directory,store)=>{
  for(const prose of ['please run acme --scan','```bash\nacme --scan\n```','``acme --scan``','\\`acme --scan`'])assert.equal(store.observe(prose,'bash'),false);
  assert.ok(store.observe('请运行 `git status --short`，再运行 `my-acme --fresh`','bash'));
  assert.ok(usage(store,'bash','git'));assert.ok(usage(store,'bash','my-acme'));
  assert.ok(store.observe('confirmed-tool --selected','powershell',true));
  assert.ok(usage(store,'powershell','confirmed-tool'));
  assert.equal(store.observe('no-tool --flag','markdown',true),false);
}));

test('unknown command names and flags can be learned without retaining argument values',()=>sandbox((directory,store)=>{
  assert.ok(store.observe('new-acme --brand-new=PRIVATE_VALUE --output /home/operator/private plain-argument','bash',true));
  const row=usage(store,'bash','new-acme');assert.deepEqual(row.flags.map(f=>f.value),['--brand-new','--output']);
  const persisted=fs.readFileSync(path.join(directory,'habits.json'),'utf8');
  for(const value of ['PRIVATE_VALUE','/home/operator/private','plain-argument'])assert.ok(!persisted.includes(value),value+' must not be stored');
}));

test('positional paths are not mistaken for slash flags in Bash or PowerShell',()=>sandbox((directory,store)=>{
  store.observe('cat /private','bash',true);store.observe('Get-Content /reports','powershell',true);
  assert.deepEqual(usage(store,'bash','cat').flags,[]);assert.deepEqual(usage(store,'powershell','Get-Content').flags,[]);
  store.observe('dir /b','cmd',true);assert.deepEqual(usage(store,'cmd','dir').flags.map(f=>f.value),['/b']);
}));

test('sensitive flags, quoted values and flag-looking argument values are never persisted',()=>sandbox((directory,store)=>{
  store.observe('mytool --password -aB123Value --token=TOKEN_VALUE --api-key API_KEY_VALUE --quoted "-QuotedValue" --verbose','bash',true);
  store.observe('find -name -PrivateName','bash',true);
  store.observe('acme --output -OutputValue --name -NameValue -- --AfterEnd','bash',true);
  const persisted=fs.readFileSync(path.join(directory,'habits.json'),'utf8');
  for(const value of ['aB123Value','TOKEN_VALUE','API_KEY_VALUE','QuotedValue','PrivateName','OutputValue','NameValue','AfterEnd'])assert.ok(!persisted.includes(value),value+' must not be stored');
  assert.ok(usage(store,'bash','mytool').flags.some(f=>f.value==='--verbose'));
}));

test('learning=false prevents habit writes and edited configuration can re-enable it',()=>sandbox((directory,store)=>{
  write(directory,'config.json',{version:1,learning:false});const before=fs.readFileSync(path.join(directory,'habits.json'),'utf8');
  assert.equal(store.observe('ls -l','bash',true),false);assert.equal(store.snapshot().learning,false);
  assert.equal(fs.readFileSync(path.join(directory,'habits.json'),'utf8'),before);
  write(directory,'config.json',{version:1,learning:true});assert.ok(store.observe('ls -l','bash',true));
  assert.equal(usage(store,'bash','ls').count,1);
}));

test('habit learning never rewrites user-owned catalogs or configuration',()=>sandbox((directory,store)=>{
  for(const env of completion.shellEnvs)fs.writeFileSync(path.join(directory,env+'.json'),' {"version": 1, "commands": [{"name":"acme-'+env+'"}]}  \n');
  fs.writeFileSync(path.join(directory,'config.json'),'{"version":1,"learning":true, "customUserKey":"retain"}\n');
  const names=['bash.json','powershell.json','cmd.json','config.json'];const before=Object.fromEntries(names.map(name=>[name,fs.readFileSync(path.join(directory,name),'utf8')]));
  for(const env of completion.shellEnvs)assert.ok(store.observe('acme-'+env+' --new-flag',env,true));
  for(const name of names)assert.equal(fs.readFileSync(path.join(directory,name),'utf8'),before[name]);
}));

test('invalid catalog JSON/schema preserves last good values and reports the file',()=>sandbox((directory,store)=>{
  write(directory,'bash.json',{version:1,commands:[{name:'kept-command'}]});store.reload();const before=structuredClone(store.snapshot().commands.bash);
  for(const broken of ['{broken','{"version":2,"commands":[]}','{"version":1,"commands":{}}']){
    fs.writeFileSync(path.join(directory,'bash.json'),broken);const snapshot=store.reload();assert.deepEqual(snapshot.commands.bash,before);assert.ok(snapshot.errors.some(e=>e.startsWith('bash.json:')));
    assert.equal(fs.readFileSync(path.join(directory,'bash.json'),'utf8'),broken);
  }
}));

test('invalid habit/config JSON blocks learning, preserves habits, and reports failure',()=>sandbox((directory,store)=>{
  store.observe('ls -l','bash',true);const before=structuredClone(store.snapshot().usage);
  fs.writeFileSync(path.join(directory,'habits.json'),'{broken');store.reload();assert.deepEqual(store.snapshot().usage,before);
  assert.equal(store.observe('cat -n','bash',true),false);assert.equal(fs.readFileSync(path.join(directory,'habits.json'),'utf8'),'{broken');
  assert.ok(store.snapshot().errors.some(e=>e.startsWith('habits.json:')));
  write(directory,'habits.json',{version:1,environments:before});fs.writeFileSync(path.join(directory,'config.json'),'{broken');
  assert.equal(store.observe('cat -n','bash',true),false);assert.equal(store.snapshot().learning,false);assert.ok(store.snapshot().errors.some(e=>e.startsWith('config.json:')));
}));

test('semantically malformed learning configuration fails closed instead of enabling learning',()=>sandbox((directory,store)=>{
  for(const invalid of [{version:1,learning:'false'},{version:2,learning:true},[],null]){
    write(directory,'config.json',invalid);assert.equal(store.observe('acme --new','bash',true),false);
    assert.equal(store.snapshot().learning,false);assert.ok(store.snapshot().errors.some(e=>e.startsWith('config.json:')));
  }
}));

test('an environments array is not accepted as a valid habit map',()=>sandbox((directory,store)=>{
  store.observe('ls -l','bash',true);const before=structuredClone(store.snapshot().usage);
  write(directory,'habits.json',{version:1,environments:[]});store.reload();
  assert.deepEqual(store.snapshot().usage,before);assert.ok(store.snapshot().errors.some(e=>e.startsWith('habits.json:')));
  assert.equal(store.observe('cat -n','bash',true),false);
}));

test('write failure restores the previous habit snapshot and reports the error',()=>sandbox((directory,store)=>{
  store.observe('ls -l','bash',true);const before=structuredClone(store.snapshot().usage.bash);const fileBefore=fs.readFileSync(path.join(directory,'habits.json'),'utf8');
  const original=store.atomic.bind(store);store.atomic=(file,data)=>{if(path.basename(file)==='habits.json')throw new Error('fixture disk failure');return original(file,data);};
  assert.equal(store.observe('ls -a','bash',true),false);assert.deepEqual(store.snapshot().usage.bash,before);assert.equal(fs.readFileSync(path.join(directory,'habits.json'),'utf8'),fileBefore);assert.ok(store.snapshot().errors.some(e=>e.includes('fixture disk failure')));
}));

test('catalog and option counts are bounded and oversized files preserve last good catalog',()=>sandbox((directory,store)=>{
  const commands=Array.from({length:330},(_,i)=>({name:'tool'+i}));
  Object.assign(commands[0],{aliases:Array.from({length:25},(_,j)=>'alias'+j),flags:Array.from({length:100},(_,j)=>'--flag'+j),values:{'--mode=':Array.from({length:100},(_,j)=>'mode'+j)}});
  write(directory,'bash.json',{version:1,commands});store.reload();
  assert.equal(store.snapshot().commands.bash.length,300);assert.equal(store.snapshot().commands.bash[0].flags.length,64);assert.equal(store.snapshot().commands.bash[0].aliases.length,16);assert.equal(store.snapshot().commands.bash[0].values['--mode='].length,64);
  const before=structuredClone(store.snapshot().commands.bash);fs.writeFileSync(path.join(directory,'bash.json'),' '.repeat(1024*1024+1));store.reload();assert.deepEqual(store.snapshot().commands.bash,before);assert.ok(store.snapshot().errors.some(e=>e.includes('超过 1 MB')));
}));

test('learning cannot write a habits file that its next read would reject',()=>sandbox((directory,store)=>{
  const flags=Array.from({length:64},(_,i)=>({value:'--f'+String(i).padStart(2,'0')+'a'.repeat(27),count:1}));
  const rows=[];const document={version:1,environments:{bash:rows}};let previous=[];
  while(rows.length<299){
    rows.push({name:'tool'+rows.length,count:1,lastUsed:'2026-01-01T00:00:00.000Z',flags,subcommands:[]});
    if(Buffer.byteLength(JSON.stringify(document,null,2)+'\n')>1024*1024){rows.pop();break;}
    previous=structuredClone(rows);
  }
  document.environments.bash=previous;write(directory,'habits.json',document);store.reload();
  const command='one-more-tool '+flags.map(f=>f.value).join(' ');store.observe(command,'bash',true);
  assert.ok(fs.statSync(path.join(directory,'habits.json')).size<=1024*1024,'habit writer must honor its own read-size boundary');
}));

test('prototype keys and malicious strings are data and cannot execute or pollute objects',()=>sandbox((directory,store)=>{
  const marker=path.join(directory,'must-not-exist');
  const payload=JSON.parse('{"version":1,"commands":[{"name":"constructor","flags":["__proto__","--normal"],"values":{"__proto__":["polluted"],"constructor":["prototype"]}},{"name":"__proto__"},{"name":"toString"}]}');
  payload.commands[0].description='require("node:fs").writeFileSync('+JSON.stringify(marker)+',"executed")';
  payload.commands.push({name:'$(touch-marker)',flags:['`touch-marker`']});write(directory,'bash.json',payload);store.reload();completion.configure(store.snapshot());
  assert.equal({}.polluted,undefined);assert.equal(Object.prototype.polluted,undefined);assert.equal(fs.existsSync(marker),false);
  const custom=completion.catalog('bash').find(c=>c.name==='constructor');assert.ok(custom);assert.ok(Object.prototype.hasOwnProperty.call(custom.values,'__proto__'));
  for(const value of ['`constructor -`','`toString -`','`git constructor --`'])assert.doesNotThrow(()=>inspect(value,'bash'),'prototype-named commands or subcommands must remain ordinary data');
  assert.equal(Object.getPrototypeOf(custom.values),Object.prototype);assert.ok(!allNames('bash').includes('__proto__'));assert.ok(!allNames('bash').includes('$(touch-marker)'));
  assert.equal(store.observe('anything','../../escape',true),false);assert.equal(fs.existsSync(path.join(directory,'escape.json')),false);
}));

let failures=0;const results=[];
for(const {name,run} of tests){try{run();results.push({name,passed:true});console.log('PASS '+name);}catch(error){failures++;results.push({name,passed:false,error:error.stack});console.error('FAIL '+name+'\n'+error.stack);}}
fs.writeFileSync(path.join(runtime,'completion-store-test.json'),JSON.stringify({passed:failures===0,tests:results.length,failures,results},null,2));
console.log(`${results.length-failures}/${results.length} completion persistence tests passed`);if(failures)process.exitCode=1;
