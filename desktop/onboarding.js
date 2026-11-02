const $=id=>document.getElementById(id);let settings={},backends=[],loaded=false;
const send=data=>window.supporter.send(data);
function options(id,values,chosen){const el=$(id);el.replaceChildren();for(const value of values){const option=document.createElement('option');option.value=value;option.textContent=value;el.append(option);}if(values.includes(chosen))el.value=chosen;el.disabled=values.length===0;}
function reasoning(){const b=backends.find(b=>b.name===$('welcomeBackend').value),m=$('welcomeModel').value,levels=b?.reasoning?.[m]||[];const fallback=(b?.adapter==='codex'||b?.name==='codex')&&m.toLowerCase().includes('luna')&&levels.includes('low')?'low':'default';options('welcomeReasoning',['default',...levels],settings.reasoning?.[b?.name+'|'+m]||fallback);$('welcomeReasoning').options[0].textContent='默认（跟随后端配置）';}
function models(keep){const b=backends.find(b=>b.name===$('welcomeBackend').value);const preferred=settings.models?.[b?.name]||(b?.name==='codex'?b.models.find(m=>m==='gpt-6-luna'):null);options('welcomeModel',b?.models||[],keep||preferred);reasoning();}
function update(event){
 const a=(event.settings||settings).appearance||{};document.documentElement.dataset.glass=String(a.glass!==false);document.documentElement.style.setProperty('--surface-opacity',String(event.glassNative?Number(a.glassOpacity)||.8:.92));
 const prior={b:$('welcomeBackend').value,m:$('welcomeModel').value,r:$('welcomeReasoning').value};settings=event.settings||settings;backends=event.backends||[];
 const available=backends.filter(b=>!b.error);options('welcomeBackend',available.map(b=>b.name),loaded&&available.some(b=>b.name===prior.b)?prior.b:settings.backend);
 models(loaded&&$('welcomeBackend').value===prior.b?prior.m:undefined);if(loaded&&$('welcomeBackend').value===prior.b&&[...$('welcomeReasoning').options].some(o=>o.value===prior.r))$('welcomeReasoning').value=prior.r;
 if(!loaded)$('welcomeHotkey').value=settings.general?.hotkey||'Control+Space';loaded=true;
 $('welcomeDetection').textContent=event.scanning?'正在检测本机环境…':available.length?'已找到 '+available.length+' 个可用后端，选择后即可开始。':'尚未检测到可用后端。可先完成安装，接入后会自动出现。';
 $('welcomeTools').textContent=backends.filter(b=>b.status!=='missing').map(b=>(b.display_name||b.name)+' · '+(b.error||b.version)).join('\n');
 $('welcomeFinish').disabled=available.length===0;if(event.error)$('welcomeFeedback').textContent=event.error;
}
function finish(later=false){
 const b=$('welcomeBackend').value,m=$('welcomeModel').value;if(!later&&!b)return;
 const next={...settings,backend:b||settings.backend||'',models:b?{...settings.models,[b]:m}:settings.models||{},reasoning:b?{...settings.reasoning,[b+'|'+m]:$('welcomeReasoning').value}:settings.reasoning||{},general:{...settings.general,hotkey:$('welcomeHotkey').value.trim()||'Control+Space'},onboarding:{completed:true}};
 $('welcomeFinish').disabled=true;$('welcomeLater').disabled=true;$('welcomeFeedback').textContent='正在保存…';send({type:'onboarding-save',settings:next});
}
$('welcomeBackend').onchange=()=>models();$('welcomeModel').onchange=reasoning;
$('welcomeForm').onsubmit=e=>{e.preventDefault();finish();};$('welcomeFinish').onclick=()=>finish();$('welcomeLater').onclick=()=>finish(true);
$('welcomeRefresh').onclick=()=>{$('welcomeDetection').textContent='正在重新检测…';send({type:'refresh'});};
$('welcomeGuide').onclick=()=>send({type:'open-install-guide'});$('welcomeClose').onclick=()=>send({type:'onboarding-dismiss'});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();send({type:'onboarding-dismiss'});}if(e.key==='F5'){e.preventDefault();$('welcomeRefresh').click();}if(e.ctrlKey&&e.key.toLowerCase()==='s'){e.preventDefault();finish(!$('welcomeBackend').value);}});
window.supporter.onEvent(e=>{if(e.type==='onboarding-data')update(e);if(e.type==='settings-saved')send({type:'onboarding-dismiss'});if(e.type==='settings-error'){$('welcomeFeedback').textContent=e.message;$('welcomeFinish').disabled=!$('welcomeBackend').value;$('welcomeLater').disabled=false;}});
requestAnimationFrame(()=>$('welcomeBackend').focus());
