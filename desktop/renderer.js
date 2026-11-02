const $=id=>document.getElementById(id);
const input=$('prompt');
const DEFAULT='默认模型（使用 CLI 配置）';
const labels={default:'默认',none:'关闭',minimal:'极轻',low:'低',medium:'中',high:'高',xhigh:'极高',max:'最大',ultra:'Ultra'};
const commands=[
  ['/settings','设置：外观、后端、模型与推理'],['/backend','选择本机自检测通过的后端插件'],
  ['/model','搜索并选择模型'],['/reasoning','设置当前模型的推理强度'],
  ['/env','对话环境；支持 /env:bash /env:powershell /env:markdown'],
  ['/tool','工具与检测；/tool:completion 查看命令补全'],
  ['/loc','定位原窗口的输入区域；/loc:window 全键盘选择'],
  ['/terminal','切换终端输入；单行填入，不执行'],['/refresh','重新检测 CLI、模型与能力'],
  ['/cancel','停止当前生成，保留对话和草稿（Ctrl+C）'],
  ['/clear','清空当前候选，开始新一轮'],['/help','查看全键盘操作'],
  ['/quit','退出 Supporter']
];
let inventory=[],settings={},backend='codex',model=DEFAULT,reasoning='default',terminal=false;
let menu=null,options=[],active=0,busy=false,history=[],steps=[],startedAt=0,targetScope='unavailable';
let choices=[],selected=-1,responseId=null,resultKind='text',motion=true;
let fitFrame=0,lastHeight=0;
let activeRequest=null,retryAfterPick=false;
let environment='auto',detectedEnvironment='auto',inlinePrefix='';
let activeClientId=null,requestSequence=0,stopped=false;
let completionState=null,completionInspector=false;
let personalCompletion={commands:{},usage:{},errors:[]};
let locationRequest=null,locations=[];
const send=data=>window.supporter.send(data);
const current=()=>inventory.find(b=>b.name===backend);
const key=()=>backend+'|'+model;
const reasoningOptions=()=>['default',...(current()?.reasoning?.[model]||[])];
const writable=()=>['editor','selection','terminal-line'].includes(targetScope);
const candidate=()=>choices[selected]?.text??'';
function text(id,value){if($(id).textContent!==value)$(id).textContent=value;}
function animate(element,frames,duration=160){
  if(motion&&!matchMedia('(prefers-reduced-motion: reduce)').matches)element.animate(frames,{duration,easing:'cubic-bezier(.2,.8,.2,1)'});
}
function scrollChoice(parent,row){
  if(!row)return;
  if(row.offsetTop<parent.scrollTop)parent.scrollTop=row.offsetTop;
  else if(row.offsetTop+row.offsetHeight>parent.scrollTop+parent.clientHeight)parent.scrollTop=row.offsetTop+row.offsetHeight-parent.clientHeight;
}
function enter(){for(const a of $('card').getAnimations())a.cancel();$('card').style.pointerEvents='';animate($('card'),[{opacity:0,transform:'translateY(5px) scale(.986)'},{opacity:1,transform:'none'}]);}
function fit(){
  if(fitFrame)return;
  fitFrame=requestAnimationFrame(()=>{
    fitFrame=0;
    const height=Math.ceil($('card').getBoundingClientRect().height+18);
    if(Math.abs(height-lastHeight)>=2){lastHeight=height;send({type:'resize',height});}
  });
}
function status(value=''){text('status',value);$('status').hidden=!value;fit();}
function step(value){
  if(steps.at(-1)===value)return;
  steps.push(value);$('process').hidden=false;$('steps').replaceChildren();
  for(const label of steps.slice(-3)){const li=document.createElement('li');li.textContent=label;$('steps').append(li);}fit();
}
function message(role,value){
  const box=$('conversation');box.hidden=false;
  const row=document.createElement('div');row.className='message '+role;
  const name=document.createElement('span');name.textContent=role==='user'?'你':'Supporter';
  const body=document.createElement('p');body.textContent=value;row.append(name,body);box.append(row);
  box.scrollTop=box.scrollHeight;animate(row,[{opacity:0,transform:'translateY(4px)'},{opacity:1,transform:'none'}]);fit();
}
setInterval(()=>{if(busy)text('processTitle','执行中 · '+Math.floor((Date.now()-startedAt)/1000)+'s');},1000);
function restoreEffort(){const fallback=backend==='codex'&&model.toLowerCase().includes('luna')&&reasoningOptions().includes('low')?'low':'default';const saved=settings.reasoning?.[key()]||fallback;reasoning=reasoningOptions().includes(saved)?saved:'default';}
function save(){settings.backend=backend;settings.environment=environment;settings.models={...settings.models,[backend]:model};settings.reasoning={...settings.reasoning,[key()]:reasoning};send({type:'settings',settings});}
function update(){
  text('backend',backend||'无可用 CLI');text('model',model===DEFAULT?'默认模型':model);
  text('effort','◉ '+(labels[reasoning]||reasoning));text('mode',terminal?'终端 · 仅填入':'随写助手');
  text('environment',environment==='auto'&&detectedEnvironment!=='auto'?'auto→'+detectedEnvironment:environment);
  $('busy').hidden=!busy;$('result').hidden=choices.length===0;
  text('candidate',selected>=0?candidate():'请先选择适用场景，Tab 只接受所选结果。');
  text('resultTitle',resultKind==='commands'?'命令候选':'待替换结果');
  text('choiceHint',choices.length>1?(selected<0?'↑↓ 或 Alt+数字选择分支':`${selected+1} / ${choices.length} · Tab 接受此项`):'Tab 接受此项');
  $('hint').innerHTML=choices.length?(selected<0?'<kbd>↑↓</kbd> 选择':'<kbd>Tab</kbd> '+(writable()?'接受':'复制')):'<kbd>/</kbd> 命令';
  input.placeholder=choices.length?'继续输入修改要求…':'想在这里写些什么？';fit();
}
function resetChoices(){choices=[];selected=-1;responseId=null;$('branches').replaceChildren();$('branches').hidden=true;}
function branch(index){
  if(index<0||index>=choices.length)return;
  selected=index;
  for(const [i,row] of [...$('branches').children].entries()){
    row.classList.toggle('active',i===selected);row.setAttribute('aria-selected',i===selected);
  }
  update();animate($('candidate'),[{opacity:.25,transform:'translateY(3px)'},{opacity:1,transform:'none'}],130);
  scrollChoice($('branches'),$('branches').children[selected]);
}
function renderBranches(){
  $('branches').replaceChildren();$('branches').hidden=choices.length<2;
  for(const [i,choice] of choices.entries()){
    const row=document.createElement('button');row.type='button';row.className='branch';row.setAttribute('role','option');
    const number=document.createElement('kbd');number.textContent=String(i+1);
    const content=document.createElement('div');const label=document.createElement('strong');label.textContent=choice.label;
    const detail=document.createElement('small');detail.textContent=choice.detail||'选择后预览具体内容';content.append(label,detail);
    row.append(number,content);row.onclick=()=>{branch(i);input.focus();};$('branches').append(row);
  }
  if(selected>=0)branch(selected);else update();
}
function pauseForPicker(){
  if(busy){send({type:'cancel-generation',client_request_id:activeClientId});activeClientId=null;stopped=true;busy=false;retryAfterPick=Boolean(activeRequest);step('已停止旧请求，选择后使用新配置继续');update();}
}
function open(kind){
  if(!['tool','loc'].includes(kind))pauseForPicker();
  if(['backend','model','reasoning'].includes(kind))send({type:'refresh',force:false});
  menu=kind;inlinePrefix='';active=0;input.value='';renderMenu();input.focus();
}
function markMenu(){
  [...$('options').children].forEach((row,i)=>{row.classList.toggle('active',i===active);row.setAttribute('aria-selected',i===active);});
  scrollChoice($('options'),$('options').children[active]);
}
function renderMenu(){
  const query=(inlinePrefix?input.value.slice(inlinePrefix.length):input.value).toLowerCase();let list=[],title='';
  if(menu==='commands'){list=commands.map(([value,description])=>({value,description}));title='命令 · ↑↓ 选择 · Tab 补全 · Enter 执行';}
  if(menu==='backend'){list=inventory.filter(b=>!b.error).map(b=>({value:b.name,description:(b.display_name||b.name)+' · '+b.version}));title='后端插件 · 自动检测本机可用 CLI';}
  if(menu==='model'){list=(current()?.models||[]).map(value=>({value,description:value===DEFAULT?'使用 CLI 当前配置':'模型目录 / 配置缓存'}));title='模型 · 输入筛选 · ↑↓ 选择 · Enter 确认';}
  if(menu==='reasoning'){list=reasoningOptions().map(value=>({value,description:value==='default'?'跟随 CLI 默认设置':(labels[value]||value)+' · 以模型实际支持为准'}));title=current()?.reasoning?.[model]?.length?'推理强度 · 按后端与模型保存':'当前模型未报告可选强度，保留 CLI 默认';}
  if(menu==='env'){list=window.commandData.environments.map(([value,description])=>({value,description}));title='对话环境 · Tab 补全 · Enter 应用';}
  if(menu==='tool'){list=[{value:'completion',description:'反引号内命令补全与公开目录检测；需显式设置 shell 环境'}];title='工具 · Tab 补全 · Enter 打开';}
  if(menu==='loc'){list=[{value:'window',description:'检测原窗口可输入区域，选择后聚焦并重新定位浮层'}];title='定位范围 · Tab 补全 · Enter 检测';}
  if(menu==='location'){list=locations.map((c,i)=>({value:c.id,label:(i+1)+'. '+c.name,description:(c.terminal?'终端输入':'文本输入')+(c.focused?' · 原焦点':'')+(c.class?' · '+c.class:'')}));title='原窗口输入区域 · 输入筛选 · ↑↓ / Enter 聚焦';}
  if(menu==='completion'){list=completionState?.options||[];title=environment+' 命令补全 · ↑↓ 选择 · Tab / Enter 补全';}
  options=menu==='completion'?list:list.filter(o=>((o.label||o.value)+' '+o.description).toLowerCase().includes(query));active=Math.max(0,Math.min(active,options.length-1));
  $('menu').hidden=!menu;text('menuTitle',title);$('options').replaceChildren();
  for(const [i,o] of options.entries()){
    const row=document.createElement('div');row.className='option';row.setAttribute('role','option');
    const name=document.createElement('span');name.textContent=o.label||o.value;const desc=document.createElement('small');desc.textContent=o.description;
    row.append(name,desc);if(o.source)row.title=o.source;row.onclick=()=>{active=i;choose();};$('options').append(row);
  }
  if(!options.length){const e=document.createElement('div');e.className='empty';e.textContent='没有匹配项';$('options').append(e);}
  markMenu();fit();
}
function closeMenu(){menu=null;inlinePrefix='';$('menu').hidden=true;input.value='';refreshCompletion();fit();}
function choose(){
  if(menu==='completion'){completeWord();return;}
  const value=options[active]?.value;if(!value)return;const kind=menu;closeMenu();
  if(kind==='commands'){execute(value);return;}
  if(kind==='tool'){showCompletion();return;}
  if(kind==='loc'){locateWindow();return;}
  if(kind==='location'){status('正在聚焦所选输入区域…');send({type:'locate-select',request_id:locationRequest,candidate_id:value});return;}
  if(kind==='backend'){backend=value;model=settings.models?.[backend]||DEFAULT;if(!current()?.models.includes(model))model=DEFAULT;restoreEffort();}
  if(kind==='model'){model=value;restoreEffort();}if(kind==='reasoning')reasoning=value;
  if(kind==='env')environment=value;
  save();status('已切换：'+(kind==='env'?environment:kind==='model'?model:kind==='reasoning'?(labels[reasoning]||reasoning):backend));update();refreshCompletion();input.focus();
  if(retryAfterPick&&activeRequest){retryAfterPick=false;startGeneration(activeRequest.request,activeRequest.history,false);}
}
function execute(cmd){
  if(cmd==='/cancel'){stopRunning();return;}
  if(cmd==='/settings'){send({type:'open-settings'});return;}
  if(['/backend','/model','/reasoning','/env','/tool','/loc'].includes(cmd)){open(cmd.slice(1));return;}
  if(cmd==='/terminal'){terminal=!terminal;send({type:'terminal-mode',enabled:terminal});status(terminal?'只填入所选的一条命令，不发送回车。':'已切换文本模式');}
  if(cmd==='/refresh'){status('正在检测 CLI、模型及推理能力…');send({type:'refresh'});}
  if(cmd==='/clear'){resetChoices();history=[];steps=[];$('conversation').replaceChildren();$('conversation').hidden=true;$('process').hidden=true;status();}
  if(cmd==='/help')status('Ctrl+C /cancel 停止生成 · /loc:window 定位输入区 · /env:bash + 反引号内 Tab 补全 · /tool:completion 检测 · Ctrl+M 模型 · Ctrl+R 推理 · Tab 接受 · Esc 关闭上下文');
  if(cmd==='/quit')send({type:'quit'});update();
}
function retarget(){status('候选已保留。请聚焦输入框，再按唤醒快捷键继续。');send({type:'retarget'});}
function accept(){
  if(!choices.length||busy)return;
  if(selected<0){status('有多个适用场景，请先按 ↑↓ 或 Alt+数字 选择，再按 Tab。');return;}
  send({type:'accept',response_id:responseId,candidate_index:selected});
}
function startGeneration(request,past=history,append=true){
  if(!current()||current().error){status(current()?.status==='checking'?'后端正在重新检测，要求已保留，请稍后发送。':'当前没有可用后端；安装 CLI 或添加后端插件后会自动更新。');send({type:'refresh',force:false});return;}
  activeClientId='r'+Date.now().toString(36)+'-'+(++requestSequence);stopped=false;
  activeRequest={request,history:structuredClone(past)};
  steps=[];startedAt=Date.now();step(backend+' · '+(model===DEFAULT?'默认模型':model)+' · 推理 '+(labels[reasoning]||reasoning));
  if(append)message('user',request);
  send({type:'generate',client_request_id:activeClientId,backend,model,reasoning,terminal,environment:environment==='auto'?detectedEnvironment:environment,completion_environment:environment,observe_completion:append,request,history:activeRequest.history});
  if(append)history.push({role:'user',content:request});
  input.value='';resetChoices();busy=true;status();update();
  refreshCompletion();
}
function stopRunning(){
  retryAfterPick=false;
  if(!busy){status('当前没有正在生成的请求。');return;}
  const id=activeClientId;activeClientId=null;stopped=true;busy=false;
  send({type:'cancel-generation',client_request_id:id});
  step('已停止当前生成');text('processTitle','执行过程');
  status('已停止生成，对话和草稿已保留。');update();
}
function showCompletion(){completionInspector=true;$('completionDetails').open=true;send({type:'completion-reload'});refreshCompletion();input.focus();}
function locateWindow(){
  locationRequest='loc-'+Date.now().toString(36)+'-'+(++requestSequence);locations=[];menu='location';inlinePrefix='';active=0;
  status('正在检测原窗口的可输入区域…');renderMenu();send({type:'locate-window',request_id:locationRequest});input.focus();
}
function refreshCompletion(){
  completionState=window.shellCompletion.inspect(input.value,input.selectionStart,environment,input.selectionEnd);
  $('completion').hidden=!completionInspector&&!completionState.inside;
  const custom=(personalCompletion.commands?.[environment]||[]).length,learned=(personalCompletion.usage?.[environment]||[]).length;
  text('completionCheck',completionState.message+(completionInspector?' · 自定义 '+custom+' / 已学习 '+learned+' · 学习'+(personalCompletion.learning===false?'关闭':'开启'):''));
  const specs=window.shellCompletion.catalog(environment);
  text('completionSource',(completionState.source||([...new Set(specs.map(s=>s.source))].join('\n')||'选择具体 shell 环境后显示对应文档来源。'))+
    (completionInspector?'\n个人目录：'+(personalCompletion.directory||'加载中')+'\n仅学习已发送/已接受的命令词与参数名；不保存参数值。':'')+
    (personalCompletion.errors?.length?'\n目录提示：'+personalCompletion.errors.join('；'):''));
  if(menu==='completion'&&(!completionState.inside||!completionState.options.length)){menu=null;$('menu').hidden=true;}
  if(completionState.inside&&completionState.options.length&&(!menu||menu==='completion')){
    menu='completion';inlinePrefix='';active=0;renderMenu();
  }
  fit();
}
function completeWord(){
  const option=options[active];if(!option)return;
  // Recompute at acceptance so moving the caret cannot replace an old range.
  const fresh=window.shellCompletion.inspect(input.value,input.selectionStart,environment,input.selectionEnd);
  const match=fresh.options.find(o=>o.value===option.value&&o.start===option.start&&o.end===option.end);
  if(!match){refreshCompletion();return;}
  const replacement=window.shellCompletion.apply(input.value,match);
  input.value=replacement.value;input.focus();input.setSelectionRange(replacement.caret,replacement.caret);
  menu=null;$('menu').hidden=true;refreshCompletion();
}
input.addEventListener('input',()=>{
  const colon=window.commandData.parseColon(input.value);
  if(colon){if(!['tool','loc'].includes(colon.kind))pauseForPicker();if(['backend','model','reasoning'].includes(colon.kind)&&menu!==colon.kind)send({type:'refresh',force:false});menu=colon.kind;inlinePrefix=colon.prefix;active=0;renderMenu();refreshCompletion();fit();return;}
  inlinePrefix='';
  if(!menu&&input.value.startsWith('/')){menu='commands';active=0;}
  if(menu==='commands'&&!input.value.startsWith('/')){menu=null;$('menu').hidden=true;}
  if(menu&&menu!=='completion'){active=0;renderMenu();}refreshCompletion();fit();
});
document.addEventListener('selectionchange',()=>{if(document.activeElement===input)refreshCompletion();});
document.addEventListener('keydown',event=>{
  if(event.isComposing||event.keyCode===229)return;const k=event.key.toLowerCase();
  if(event.ctrlKey&&!event.shiftKey&&!event.altKey&&k==='c'&&busy){event.preventDefault();stopRunning();return;}
  if(event.ctrlKey&&event.shiftKey&&k==='c'&&selected>=0){event.preventDefault();send({type:'copy',response_id:responseId,candidate_index:selected});return;}
  if(event.ctrlKey&&event.key===','){event.preventDefault();send({type:'open-settings'});return;}
  if(event.ctrlKey&&['b','m','r','t','q','l'].includes(k)){
    event.preventDefault();if(k==='b')open('backend');if(k==='m')open('model');if(k==='r')open('reasoning');if(k==='t')execute('/terminal');if(k==='q')send({type:'quit'});if(k==='l'&&choices.length)retarget();return;
  }
  if(event.key==='F5'){event.preventDefault();execute('/refresh');return;}
  if(event.key==='Escape'){event.preventDefault();activeClientId=null;locationRequest=null;locations=[];stopped=true;busy=false;resetChoices();history=[];activeRequest=null;retryAfterPick=false;completionInspector=false;closeMenu();send({type:'cancel'});return;}
  if(event.altKey&&/^[1-8]$/.test(event.key)&&!menu&&choices.length){event.preventDefault();branch(Number(event.key)-1);return;}
  if(['ArrowDown','ArrowUp'].includes(event.key)){
    if(menu){event.preventDefault();active=(active+(event.key==='ArrowDown'?1:-1)+Math.max(options.length,1))%Math.max(options.length,1);markMenu();return;}
    if(choices.length>1&&(!input.value||event.altKey)){event.preventDefault();branch(selected<0?(event.key==='ArrowDown'?0:choices.length-1):(selected+(event.key==='ArrowDown'?1:-1)+choices.length)%choices.length);return;}
  }
  if(event.key==='Tab'){event.preventDefault();if(menu==='completion'){completeWord();}else if(inlinePrefix&&options[active]){input.value=inlinePrefix+options[active].value;renderMenu();}else if(menu==='commands'){if(options[active]){input.value=options[active].value;renderMenu();}}else if(menu)choose();else if(completionState?.inside){status(completionState.message);}else accept();return;}
  if(event.key==='Enter'&&!event.shiftKey){
    event.preventDefault();if(menu){choose();return;}if(event.ctrlKey){accept();return;}if(busy)return;
    const request=input.value.trim();if(!request)return;
    if(request.startsWith('/')){status('未知命令。输入 / 查看命令。');return;}
    startGeneration(request);
  }
});
$('backend').onclick=()=>open('backend');$('model').onclick=()=>open('model');$('effort').onclick=()=>open('reasoning');
$('environment').onclick=()=>open('env');
function showTarget(target){
  targetScope=target.scope||'unavailable';terminal=Boolean(target.terminal);
  detectedEnvironment=target.shell==='posix'?'bash':target.shell||'auto';
  $('context').hidden=!target.context&&targetScope!=='terminal-line';text('original',target.context||(terminal?'（空命令行）':'（空输入框）'));
  text('scope',targetScope==='reference'?'只读选区 · 作为参考，不会改动网页':targetScope==='terminal-line'?'将替换当前命令（不会执行）':targetScope==='selection'?'将替换选中文本':'将替换当前输入框内容');
}
window.supporter.onEvent(event=>{
  if(event.type==='backend-scan-error'){status('后端检测失败，保留上次列表：'+event.message);return;}
  if(['locate-results','locate-error'].includes(event.type)){
    if(!locationRequest||event.request_id!==locationRequest)return;
    if(event.type==='locate-error'){status(event.message);menu=null;$('menu').hidden=true;fit();return;}
    locations=event.controls||[];menu='location';inlinePrefix='';active=0;
    status(locations.length?(event.title||'原窗口')+' · '+locations.length+' 个可输入区域'+(event.limited?'（列表已限量）':''):'未找到可定位的输入区域；请先键盘聚焦目标输入处，再唤醒。');
    renderMenu();return;
  }
  if(event.type==='completion-data'){personalCompletion=event.data;window.shellCompletion.configure(personalCompletion);refreshCompletion();return;}
  if(['progress','result','error','generation-stopped'].includes(event.type)&&event.client_request_id!=null&&event.client_request_id!==activeClientId){
    if(!(event.type==='generation-stopped'&&stopped&&!busy))return;
  }
  if(stopped&&event.client_request_id==null&&['progress','result'].includes(event.type))return;
  if(event.type==='generation-stopped'){
    if(busy)return;
    text('processTitle','执行过程');fit();return;
  }
  if(event.type==='restore-session'&&event.state){
    const state=event.state;({history,steps,startedAt,busy,choices,selected,responseId,resultKind,activeRequest,retryAfterPick}=state);
    activeClientId=state.activeClientId??null;requestSequence=state.requestSequence||0;stopped=Boolean(state.stopped);
    targetScope=state.targetScope;terminal=state.terminal;detectedEnvironment=state.detectedEnvironment;
    $('conversation').innerHTML=state.conversationHtml;$('conversation').hidden=!history.length;
    $('original').textContent=state.original;$('scope').textContent=state.scopeLabel;$('context').hidden=state.contextHidden;
    input.value=state.draft;menu=state.menu;inlinePrefix=state.inlinePrefix;active=state.active;
    completionInspector=Boolean(state.completionInspector);
    locations=state.locations||[];locationRequest=state.locationRequest||null;
    if(state.caret!=null)input.setSelectionRange(state.caret,state.selectionEnd??state.caret);
    renderBranches();if(menu)renderMenu();update();refreshCompletion();
  }
  if(event.type==='focus-input'){enter();input.focus();}
  if(event.type==='closing'){
    $('card').style.pointerEvents='none';
    if(motion)$('card').animate([{opacity:1,transform:'none'},{opacity:0,transform:'translateY(4px) scale(.99)'}],{duration:90,fill:'forwards'});
  }
  if(event.type==='context-updated'){showTarget(event.target);update();}
  if(event.type==='appearance'){
    const a=event.appearance||{};motion=a.motion!==false;
    document.documentElement.dataset.theme=a.theme==='system'?(event.systemDark?'dark':'light'):(a.theme||'dark');
    document.documentElement.dataset.glass=String(a.glass!==false);document.documentElement.style.setProperty('--surface-opacity',String(a.glass!==false?(event.glassNative?Math.max(.5,Math.min(.96,Number(a.glassOpacity)||.8)):Math.max(.9,Number(a.glassOpacity)||.8)):1));
    document.documentElement.style.setProperty('--accent',a.accent||'#b9b5ff');document.documentElement.style.setProperty('--editor-size',(a.fontSize||14)+'px');document.documentElement.style.setProperty('--radius',(a.radius||16)+'px');
    document.documentElement.classList.toggle('hide-process',a.showProcess===false);document.documentElement.classList.toggle('no-motion',!motion);fit();
  }
  if(event.type==='open-settings'){lastHeight=0;resetChoices();busy=false;closeMenu();$('context').hidden=true;enter();update();execute(event.command||'/settings');input.focus();}
  if(event.type==='wake'){
    lastHeight=0;showTarget(event.target);
    if(!event.resume){activeClientId=null;locationRequest=null;locations=[];stopped=false;busy=false;completionInspector=false;closeMenu();resetChoices();history=[];steps=[];activeRequest=null;$('conversation').replaceChildren();$('conversation').hidden=true;$('process').hidden=true;}
    status(!writable()?'当前位置不可编辑；Tab 复制所选候选，然后可 Ctrl+V 粘贴。':event.resume?'上下文已恢复。确认候选后按 Tab。':event.target.source==='window-fallback'?'未获取输入坐标，暂用窗口附近定位。':'');
    enter();update();input.focus();
  }
  if(event.type==='inventory'){
    inventory=event.backends;settings=event.settings||settings;backend=settings.backend||backend;
    environment=settings.environment||environment;
    if(!inventory.some(b=>b.name===backend&&(!b.error||b.status==='checking')))backend=inventory.find(b=>!b.error)?.name||'';
    model=settings.models?.[backend]||DEFAULT;if(!current()?.models.includes(model))model=current()?.models[0]||DEFAULT;restoreEffort();update();
    if(['backend','model','reasoning'].includes(menu))renderMenu();
    if(event.notice)status(event.notice);refreshCompletion();
  }
  if(event.type==='progress')step(event.message);
  if(event.type==='result'){
    busy=false;choices=event.candidates||[];selected=choices.length===1?0:-1;responseId=event.response_id;resultKind=event.kind||'text';
    message('assistant',event.reply);history.push({role:'assistant',content:event.reply,candidates:choices});renderBranches();
    step('已完成 · '+(startedAt?Math.floor((Date.now()-startedAt)/1000):0)+'s · '+(choices.length>1?'等待选择分支':choices.length?'等待 Tab 确认':'等待补充信息'));text('processTitle','执行过程');
    requestAnimationFrame(()=>$('content').scrollTop=$('content').scrollHeight);
    status(!writable()&&choices.length?'Tab 复制所选候选，可直接 Ctrl+V 粘贴；完整换行将保留。':'');update();input.focus();
  }
  if(event.type==='needs-target'){status(event.message);retarget();}
  if(event.type==='accepted'){resetChoices();update();}
  if(event.type==='clipboard-copied'){status('已复制，可 Ctrl+V 粘贴。');update();}
  if(event.type==='error'){busy=false;enter();step('失败 · '+event.message);text('processTitle','执行过程');status(event.message);update();}
});
new ResizeObserver(fit).observe($('card'));
window.supporterSession={snapshot:()=>({history,steps,startedAt,busy,choices,selected,responseId,resultKind,activeRequest,retryAfterPick,activeClientId,requestSequence,stopped,targetScope,terminal,detectedEnvironment,
  conversationHtml:$('conversation').innerHTML,original:$('original').textContent,scopeLabel:$('scope').textContent,contextHidden:$('context').hidden,draft:input.value,caret:input.selectionStart,selectionEnd:input.selectionEnd,completionInspector,locations,locationRequest,menu,inlinePrefix,active})};
update();
