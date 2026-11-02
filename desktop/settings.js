const $=id=>document.getElementById(id);let settings={},backends=[],accent='#b9b5ff',systemDark=matchMedia('(prefers-color-scheme:dark)').matches,initialized=false,dirty=false;
const send=data=>window.supporter.send(data);
const colors=['#b9b5ff','#91bfff','#90d9be','#f0bc84','#efa8c6','#b8c2d6'];
function page(name){for(const e of document.querySelectorAll('[data-panel]'))e.hidden=e.dataset.panel!==name;for(const b of document.querySelectorAll('[data-page]'))b.classList.toggle('active',b.dataset.page===name);}
for(const b of document.querySelectorAll('[data-page]'))b.onclick=()=>page(b.dataset.page);
function appearance(){return {theme:$('theme').value,accent,fontSize:Number($('fontSize').value),width:Number($('width').value),opacity:Number($('opacity').value)/100,radius:Number($('radius').value),showProcess:$('showProcess').checked,motion:$('motion').checked,glass:$('glass').checked,glassOpacity:Number($('glassOpacity').value)/100};}
function preview(){const a=appearance();document.documentElement.dataset.theme=a.theme==='system'?(systemDark?'dark':'light'):a.theme;document.documentElement.style.setProperty('--accent',accent);document.documentElement.style.setProperty('--sample-size',a.fontSize+'px');$('sample').style.borderRadius=a.radius+'px';$('sample').style.opacity=a.opacity;$('opacityValue').textContent=Math.round(a.opacity*100)+'%';send({type:'preview-appearance',appearance:a});}
for(const color of colors){const b=document.createElement('button');b.type='button';b.style.background=color;b.setAttribute('aria-label',color);b.onclick=()=>{dirty=true;accent=color;paint();preview();};$('colors').append(b);}
function paint(){[...$('colors').children].forEach((b,i)=>b.classList.toggle('selected',colors[i]===accent));}
function options(select,values,chosen){select.replaceChildren();for(const value of values){const o=document.createElement('option');o.value=value;o.textContent=value;select.append(o);}if(values.includes(chosen))select.value=chosen;select.disabled=values.length===0;}
function numericPreference(id,value){const select=$(id),chosen=String(value);if(![...select.options].some(o=>o.value===chosen)){const option=document.createElement('option');option.value=chosen;option.textContent=chosen+' · 自定义';select.append(option);}select.value=chosen;}
function models(chosen,effort){const b=backends.find(b=>b.name===$('backend').value);options($('model'),b?.models||[],chosen??settings.models?.[b?.name]);$('modelSource').textContent=b?.source||'没有可用 CLI；安装或添加后端插件后自动更新。';reasoning(effort);}
function reasoning(chosen){const b=backends.find(b=>b.name===$('backend').value);const m=$('model').value;const levels=b?.reasoning?.[m]||[];const fallback=b?.name==='codex'&&m.toLowerCase().includes('luna')&&levels.includes('low')?'low':'default';options($('reasoning'),['default',...levels],chosen??settings.reasoning?.[b?.name+'|'+m]??fallback);$('reasoning').options[0].textContent='默认（跟随 CLI）';$('reasoning').disabled=!b;}
$('backend').onchange=()=>models();$('model').onchange=()=>reasoning();
for(const type of ['input','change'])$('form').addEventListener(type,()=>{dirty=true;});
$('codexConnection').onchange=()=>{$('codexProxyRow').hidden=$('codexConnection').value!=='proxy';};
for(const id of ['theme','fontSize','width','opacity','radius','showProcess','motion','glass','glassOpacity'])$(id).addEventListener('input',preview);
const closeSettings=()=>send({type:'settings-close'});
$('cancel').onclick=closeSettings;
$('windowClose').onclick=closeSettings;
$('refresh').onclick=()=>{send({type:'refresh'});$('feedback').textContent='正在重新检测…';};
$('save').onclick=()=>{const b=$('backend').value,m=$('model').value;const next={...settings,appearance:appearance(),general:{hotkey:$('hotkey').value.trim()||'Control+Space',autoStart:$('autoStart').checked},backend:b,models:b?{...settings.models,[b]:m}:{...settings.models},reasoning:b&&m?{...settings.reasoning,[b+'|'+m]:$('reasoning').value}:{...settings.reasoning},codexConnection:{mode:$('codexConnection').value,proxyUrl:$('codexConnection').value==='proxy'?$('codexProxy').value.trim():''}};$('save').disabled=true;$('feedback').textContent='正在保存…';send({type:'settings-save',settings:next});};
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeSettings();if(e.ctrlKey&&e.key.toLowerCase()==='s'){e.preventDefault();$('save').click();}});
function loadData(e){
 const keep=initialized&&dirty,prior={backend:$('backend').value,model:$('model').value,effort:$('reasoning').value};
 settings=e.settings||settings;backends=e.backends||[];
 if(!keep){
  const a=settings.appearance||{};$('theme').value=a.theme||'dark';accent=a.accent||colors[0];numericPreference('fontSize',a.fontSize||14);numericPreference('width',a.width||520);$('opacity').value=Math.round((a.opacity||1)*100);numericPreference('radius',a.radius||16);$('showProcess').checked=a.showProcess!==false;$('motion').checked=a.motion!==false;$('glass').checked=a.glass!==false;$('glassOpacity').value=Math.round((a.glassOpacity||.8)*100);$('hotkey').value=settings.general?.hotkey||'Control+Space';$('autoStart').checked=Boolean(settings.general?.autoStart);$('codexConnection').value=settings.codexConnection?.mode||'inherit';$('codexProxy').value=settings.codexConnection?.proxyUrl||'';$('codexConnection').onchange();paint();preview();
 }
 const preferred=keep?prior.backend:settings.backend||'codex';
 const available=backends.filter(b=>!b.error||b.name===preferred&&b.status==='checking');
 const names=available.map(b=>b.name);options($('backend'),names,names.includes(preferred)?preferred:settings.backend);
 for(const option of $('backend').options){const b=available.find(b=>b.name===option.value);option.textContent=(b.display_name||b.name)+(b.status==='checking'?'（检测中）':'');option.disabled=Boolean(b.error);}
 const preserve=keep&&$('backend').value===prior.backend;models(preserve?prior.model:undefined,preserve?prior.effort:undefined);
 $('cliStatus').textContent=backends.filter(b=>b.status!=='missing').map(b=>b.name+': '+(b.error?'不可用 — '+b.error.slice(0,100):b.version)).join('\n')||'没有检测到可用后端插件。';
 if(keep)$('feedback').textContent='后端目录已更新，未保存的更改已保留。';initialized=true;
}
window.supporter.onEvent(e=>{
 if(e.type==='appearance'){const a=e.appearance||{};document.documentElement.dataset.glass=String(a.glass!==false);document.documentElement.style.setProperty('--surface-opacity',String(a.glass!==false?(e.glassNative?Number(a.glassOpacity)||.8:Math.max(.9,Number(a.glassOpacity)||.8)):1));$('glassOpacityValue').textContent=Math.round((Number(a.glassOpacity)||.8)*100)+'%';}
 if(e.type==='settings-data')loadData(e);
 if(e.type==='settings-saved'){closeSettings();}
 if(e.type==='settings-error'){$('feedback').textContent=e.message;$('save').disabled=false;}
});
