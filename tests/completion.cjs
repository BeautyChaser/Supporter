// Pure string/metadata regression tests. No shell, GUI, model or user input.
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');
const completion=require('../desktop/completion.js');
const tests=[];const test=(name,run)=>tests.push({name,run});
function at(marked,env='bash',selectionEnd){
  const caret=marked.indexOf('¦');assert.ok(caret>=0,'fixture needs a caret marker');
  const value=marked.slice(0,caret)+marked.slice(caret+1);
  return {value,caret,state:completion.inspect(value,caret,env,selectionEnd)};
}
const values=state=>state.options.map(o=>o.value);
function has(marked,env,option){assert.ok(values(at(marked,env).state).includes(option),option+' missing');}
function none(marked,env='bash'){assert.equal(at(marked,env).state.options.length,0);}

test('requires an explicit supported shell environment',()=>{
  for(const env of ['auto','markdown','text','code','posix','']){
    const {state}=at('`ls -¦`',env);assert.equal(state.inside,true);assert.equal(state.enabled,false);assert.deepEqual(state.options,[]);assert.match(state.message,/env:bash/);
  }
});
test('does not complete ordinary prose outside backticks',()=>none('请运行 ls -¦'));
test('closed single pair enables completion',()=>has('`gi¦`','bash','git'));
test('unclosed single delimiter enables drafting completion',()=>has('`gi¦','bash','git'));
test('empty pair enables command-name completion',()=>has('`¦`','bash','ls'));
test('caret after a closing delimiter is outside',()=>none('`ls`¦'));
test('double delimiters are Markdown code, not an active single pair',()=>none('``ls¦``'));
test('fenced block is not an inline shell region',()=>none('```bash\nls -¦\n```'));
test('unclosed fenced block is excluded',()=>none('```bash\nls -¦'));
test('escaped delimiter is literal',()=>none('\\`gi¦'));
test('even escape count permits a real delimiter',()=>has('\\\\`gi¦`','bash','git'));
test('finds the pair enclosing the caret among multiple pairs',()=>has('`ls` 然后 `gi¦`','bash','git'));
test('noncollapsed selection does not overwrite selected text',()=>{
  const x=at('`gi¦t`');const state=completion.inspect(x.value,x.caret,'bash',x.caret+1);assert.equal(state.options.length,0);
});

test('Bash names remain case-sensitive',()=>none('`LS¦`','bash'));
test('PowerShell command names are case-insensitive',()=>has('`get-ch¦`','powershell','Get-ChildItem'));
test('PowerShell ls alias uses cmdlet parameters',()=>has('`ls -rec¦`','powershell','-Recurse'));
test('Bash ls has GNU flags instead of PowerShell parameters',()=>{
  const state=at('`ls -¦`','bash').state;assert.ok(values(state).includes('-l'));assert.ok(!values(state).includes('-Recurse'));
});
test('cmd dir uses slash flags',()=>has('`dir /¦`','cmd','/b'));
test('PowerShell dir alias uses cmdlet parameters',()=>has('`dir -Fo¦`','powershell','-Force'));
test('Bash unknown dir does not pretend catalog coverage',()=>{
  const state=at('`dir -¦`','bash').state;assert.equal(state.options.length,0);assert.match(state.message,/未收录/);
});
test('double-quoted arguments are untouched',()=>none('`grep "pattern -¦"`'));
test('single-quoted Bash arguments are untouched',()=>none("`grep 'pattern -¦'`"));
test('comments do not receive flag completions',()=>none('`git status # --sh¦`'));
test('quoted hash is data and later flags remain completable',()=>has('`grep "# literal" -¦`','bash','-i'));
test('cmd caret-escaped separators stay in their token',()=>none('`dir foo^&ca¦`','cmd'));
test('pipe starts a new Bash command position',()=>has('`ls -l | gr¦`','bash','grep'));
test('pipe starts a new PowerShell cmdlet position',()=>has('`Get-ChildItem | select-st¦`','powershell','Select-String'));
test('quoted pipe is not a pipeline',()=>none('`grep "a|gr¦"`'));
test('redirection target is a path, not a new command',()=>none('`ls > ca¦`'));

test('Git subcommands are offered after the command name',()=>has('`git st¦`','bash','status'));
test('Git subcommand-specific flags are offered',()=>has('`git status --sh¦`','bash','--short'));
test('already used flags are not offered twice',()=>{
  const state=at('`git status --short --¦`','bash').state;assert.ok(!values(state).includes('--short'));assert.ok(values(state).includes('--branch'));
});
test('ordinary flag argument values are not treated as flags',()=>none('`watch -n tw¦`'));
test('NVIDIA query fields are offered independently',()=>{
  const state=at('`nvidia-smi --query-gpu=name,mem¦`').state;
  assert.ok(values(state).includes('--query-gpu=name,memory.used'));assert.ok(values(state).includes('--query-gpu=name,memory.total'));
});
test('NVIDIA query fields do not duplicate a previous field',()=>{
  const state=at('`nvidia-smi --query-gpu=name,¦`').state;assert.ok(!values(state).includes('--query-gpu=name,name'));
});
test('NVIDIA format combinations complete after a comma',()=>has('`nvidia-smi --format=csv,noh¦`','bash','--format=csv,noheader'));
test('an exact value is not offered as a no-op completion',()=>{
  const state=at('`nvidia-smi --format=csv¦`').state;assert.ok(!values(state).includes('--format=csv'));
});
test('middle-of-token command replacement preserves every other character',()=>{
  const x=at('前文 `g¦ti status` 后文');const option=x.state.options.find(o=>o.value==='git');assert.ok(option);
  const applied=completion.apply(x.value,option);assert.equal(applied.value,'前文 `git status` 后文');assert.equal(applied.caret,'前文 `git'.length);
});
test('middle-of-token flag replacement preserves following arguments',()=>{
  const x=at('前文 `git status --sh¦ortish file.txt` 后文');const option=x.state.options.find(o=>o.value==='--short');assert.ok(option);
  assert.equal(completion.apply(x.value,option).value,'前文 `git status --short file.txt` 后文');
});
test('query-field replacement preserves suffix text and the enclosing delimiters',()=>{
  const x=at('A `nvidia-smi --query-gpu=name,mem¦ory.x --format=csv` B');const option=x.state.options.find(o=>o.value==='--query-gpu=name,memory.used');assert.ok(option);
  assert.equal(completion.apply(x.value,option).value,'A `nvidia-smi --query-gpu=name,memory.used --format=csv` B');
});
test('completion ranges stay inside the active pair',()=>{
  const x=at('保持 `git status --¦` 外部');const zone=completion.region(x.value,x.caret);
  for(const option of x.state.options){assert.ok(option.start>=zone.start);assert.ok(option.end<=zone.end);}
});
test('hostile command text is never evaluated or passed to an execution API',()=>{
  const module={exports:{}};const blocked=()=>{throw new Error('execution API must not be used');};
  const sandbox={module,globalThis:{},require:blocked,fetch:blocked,eval:blocked,Function:blocked};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../desktop/completion.js'),'utf8'),sandbox);
  const input='`$(globalThis.__owned = true); ls -`';const state=module.exports.inspect(input,input.length-1,'bash');
  assert.ok(state.options.length>0);assert.equal(sandbox.globalThis.__owned,undefined);
});
test('unknown command reports catalog coverage rather than installation state',()=>{
  const state=at('`__not_in_public_catalog_7391 --¦`').state;
  assert.equal(state.options.length,0);assert.match(state.message,/未收录/);assert.match(state.message,/不判断远端是否安装/);
});
test('a catalog match does not assert local or remote installation',()=>{
  const state=at('`nvidia-smi¦`').state;assert.equal(state.command,'nvidia-smi');assert.ok(!('installed' in state));assert.ok(!('available' in state));assert.doesNotMatch(state.message,/已安装|检测.*可用/);
  assert.match(state.source,/^https:\/\/docs\.nvidia\.com\//);
});

const results=[];
for(const {name,run} of tests){try{run();results.push({name,passed:true});console.log('ok - '+name);}catch(error){results.push({name,passed:false,error:error.message});console.error('FAIL - '+name+'\n'+error.message);}}
const report={passed:results.every(r=>r.passed),count:results.length,failures:results.filter(r=>!r.passed),pureNode:true,noExternalExecution:true};
fs.mkdirSync(path.join(__dirname,'../.runtime'),{recursive:true});fs.writeFileSync(path.join(__dirname,'../.runtime/completion-test.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify({passed:report.passed,count:report.count,failed:report.failures.length}));
if(!report.passed)process.exitCode=1;
