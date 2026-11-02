/* Offline completion metadata from the public manuals linked in each entry.
 * No shell, subprocess, network request, or user command is evaluated here. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.shellCompletion=api;})(typeof window==='object'?window:globalThis,()=>{
  'use strict';
  const sources={
    core:'https://www.gnu.org/software/coreutils/manual/coreutils.html',
    bash:'https://www.gnu.org/software/bash/manual/bash.html',
    grep:'https://www.gnu.org/software/grep/manual/grep.html',
    find:'https://www.gnu.org/software/findutils/manual/html_mono/find.html',
    git:'https://git-scm.com/docs/git',
    nvidia:'https://docs.nvidia.com/deploy/nvidia-smi/index.html',
    watch:'https://gitlab.com/procps-ng/procps/-/blob/master/man/watch.1',
    cmd:'https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/',
    ps:'https://learn.microsoft.com/en-us/powershell/module/'
  };
  const pairs=rows=>rows.map(([value,description])=>({value,description}));
  const entry=(name,description,source,flags=[],extra={})=>({name,description,source,flags:pairs(flags),...extra});
  const git=entry('git','版本控制',sources.git, [['--version','查看版本'],['--help','查看帮助']],{subcommands:pairs([
    ['status','查看工作区状态'],['diff','比较修改'],['log','查看提交记录'],['branch','列出或管理分支'],['switch','切换分支'],['add','暂存文件'],['commit','创建提交'],['fetch','获取远程更新'],['pull','拉取并整合更新'],['push','推送提交'],['clone','克隆仓库']]),subFlags:{
    status:pairs([['--short','简短格式'],['--branch','显示分支信息']]),diff:pairs([['--stat','统计修改'],['--staged','查看已暂存修改'],['--name-only','只列文件名']]),
    log:pairs([['--oneline','每条提交一行'],['--graph','绘制提交关系'],['--all','所有引用']]),commit:pairs([['-m','指定提交说明']]),switch:pairs([['-c','创建并切换分支']])
  }});
  const nvidia=entry('nvidia-smi','查看 NVIDIA GPU 状态',sources.nvidia,[['--query-gpu=','指定 GPU 查询字段'],['--format=csv','CSV 格式'],['--loop=','按秒循环刷新'],['--list-gpus','列出 GPU'],['--id=','指定 GPU'],['-q','详细查询'],['--help','帮助']],{values:{
    '--query-gpu=':pairs([['name','GPU 名称'],['index','GPU 索引'],['memory.used','已用显存'],['memory.total','总显存'],['utilization.gpu','GPU 利用率'],['temperature.gpu','GPU 温度']]),
    '--format=':pairs([['csv','CSV 格式'],['csv,noheader','CSV 无表头'],['csv,noheader,nounits','CSV 无表头和单位']])
  }});
  const ps=(name,description,flags,module='microsoft.powershell.management',extra={})=>entry(name,description,sources.ps+module+'/'+name.toLowerCase()+'?view=powershell-5.1',flags,extra);
  const cmd=(name,description,flags)=>entry(name,description,sources.cmd+name,flags);
  const catalogs={
    bash:[
      entry('ls','列出目录内容',sources.core,[['-l','详细列表'],['-a','包括隐藏文件'],['-h','易读大小'],['--all','包括隐藏文件'],['--human-readable','易读大小']]),
      entry('cd','切换工作目录',sources.bash,[['-P','使用物理目录结构']]),
      entry('pwd','显示工作目录',sources.core,[['-P','显示物理路径']]),
      entry('cat','输出文件内容',sources.core,[['-n','显示行号'],['-b','非空行编号']]),
      entry('head','查看文件开头',sources.core,[['-n','指定行数'],['-c','指定字节数']]),
      entry('tail','查看文件结尾',sources.core,[['-n','指定行数'],['-f','跟随文件追加'],['-F','按名称跟随并重试']]),
      entry('df','查看文件系统空间',sources.core,[['-h','易读大小'],['-T','文件系统类型']]),
      entry('du','查看文件占用',sources.core,[['-h','易读大小'],['-s','只显示总计'],['--max-depth=','限制深度']]),
      entry('grep','搜索文本',sources.grep,[['-i','忽略大小写'],['-n','显示行号'],['-r','递归搜索'],['-E','扩展正则'],['-v','反向匹配'],['--color=auto','突出匹配内容']]),
      entry('find','查找文件',sources.find,[['-name','按文件名匹配'],['-iname','忽略大小写的名称匹配'],['-type','按类型筛选'],['-maxdepth','限制查找深度'],['-print','输出匹配路径']]),
      entry('watch','定期刷新命令输出',sources.watch,[['-n','指定秒数间隔'],['-d','突出变化'],['-t','隐藏标题']]),git,nvidia
    ],
    powershell:[
      ps('Get-ChildItem','列出目录项',[['-Path','路径'],['-LiteralPath','不展开通配符的路径'],['-Filter','文件名筛选'],['-Recurse','递归列出'],['-Force','包括隐藏项'],['-File','只列文件'],['-Directory','只列目录'],['-Name','只显示名称']],undefined,{aliases:['gci','ls','dir']}),
      ps('Get-Content','读取文件内容',[['-Path','文件路径'],['-Raw','以单个字符串读取'],['-Tail','最后若干行'],['-Wait','持续等待新内容'],['-Encoding','指定编码']],undefined,{aliases:['gc','cat','type']}),
      ps('Get-Process','查看进程',[['-Name','进程名称'],['-Id','进程编号']]),
      ps('Set-Location','切换工作目录',[['-Path','目标路径'],['-LiteralPath','不展开通配符的路径']],undefined,{aliases:['cd','sl']}),
      ps('Get-Location','显示工作目录',[],undefined,{aliases:['pwd','gl']}),
      ps('Select-String','搜索文本',[['-Pattern','匹配模式'],['-Path','文件路径'],['-SimpleMatch','按普通字符串匹配'],['-CaseSensitive','区分大小写']],'microsoft.powershell.utility'),
      ps('Select-Object','选择属性或记录',[['-Property','属性名'],['-First','前若干条'],['-Last','后若干条'],['-Unique','去重']],'microsoft.powershell.utility'),
      ps('Get-Help','查看命令帮助',[['-Name','命令名'],['-Examples','显示示例'],['-Full','完整帮助']],'microsoft.powershell.core'),git,nvidia
    ],
    cmd:[
      cmd('dir','列出目录内容',[['/a','包括隐藏和系统文件'],['/b','仅输出名称'],['/s','包括子目录'],['/p','逐屏显示'],['/w','宽列表'],['/o:n','按名称排序']]),
      cmd('cd','显示或切换目录',[['/d','同时切换驱动器']]),
      cmd('type','显示文本文件内容',[]),
      cmd('tasklist','列出进程',[['/fo','输出格式'],['/fi','筛选条件'],['/v','详细信息'],['/nh','不显示表头']]),
      cmd('ipconfig','显示网络配置',[['/all','完整网络配置'],['/displaydns','显示 DNS 缓存']]),
      cmd('ping','检测网络连通性',[['-n','请求次数'],['-t','持续请求'],['-4','使用 IPv4'],['-6','使用 IPv6']]),
      cmd('findstr','在文件中搜索文本',[['/i','忽略大小写'],['/n','显示行号'],['/s','搜索子目录'],['/l','使用普通字符串'],['/r','使用正则表达式']]),git,nvidia
    ]
  };
  const shellEnvs=Object.keys(catalogs);
  let personal={commands:{},usage:{}};
  let cachedCatalog=new Map();
  const foldFor=(env,value)=>env==='bash'?value:value.toLowerCase();
  function configure(data={}){personal={commands:data.commands||{},usage:data.usage||{}};cachedCatalog=new Map();}
  function catalog(env){
    if(!shellEnvs.includes(env))return [];
    if(cachedCatalog.has(env))return cachedCatalog.get(env);
    const merged=new Map((catalogs[env]||[]).map(c=>[foldFor(env,c.name),{...c,flags:[...c.flags],subcommands:[...(c.subcommands||[])]}]));
    for(const custom of personal.commands[env]||[]){
      const key=foldFor(env,custom.name),base=merged.get(key);
      merged.set(key,{...base,...custom,origin:'user',aliases:[...new Set([...(base?.aliases||[]),...(custom.aliases||[])])],values:{...(base?.values||{}),...(custom.values||{})},flags:[...(base?.flags||[]).map(o=>({...o,source:o.source||base.source})),...(custom.flags||[])],subcommands:[...(base?.subcommands||[]).map(o=>({...o,source:o.source||base.source})),...(custom.subcommands||[])]});
    }
    for(const habit of personal.usage[env]||[]){
      const key=foldFor(env,habit.name),base=merged.get(key)||{name:habit.name,description:'个人常用命令',source:'本地使用习惯',origin:'learned',flags:[],subcommands:[]};
      const withUsage=(list,records,flags=false)=>{
        const values=new Map(list.map(o=>[foldFor(env,o.value),{...o}]));
        for(const item of records||[]){
          let id=foldFor(env,item.value);
          if(flags&&!values.has(id))id=[...values.keys()].find(k=>k.split(/[=:]/)[0]===id)||id;
          const option=values.get(id)||{value:item.value,description:'个人常用项',origin:'learned',source:'本地使用习惯'};
          values.set(id,{...option,usage:item.count});
        }
        return [...values.values()];
      };
      merged.set(key,{...base,usage:habit.count,flags:withUsage(base.flags,habit.flags,true),subcommands:withUsage(base.subcommands,habit.subcommands)});
    }
    const rows=[...merged.values()].map(c=>({...c,flags:[...new Map(c.flags.map(o=>[foldFor(env,o.value),o])).values()],subcommands:[...new Map(c.subcommands.map(o=>[foldFor(env,o.value),o])).values()]}));
    cachedCatalog.set(env,rows);return rows;
  }
  const rank=list=>list.map((o,index)=>({...o,index})).sort((a,b)=>(b.usage||0)-(a.usage||0)||(b.origin==='user')-(a.origin==='user')||a.index-b.index);
  function valueFlags(name,sub){const map={
    'Get-ChildItem':['-Path','-LiteralPath','-Filter'],'Get-Content':['-Path','-Tail','-Encoding'],
    'Get-Process':['-Name','-Id'],'Set-Location':['-Path','-LiteralPath'],'Select-String':['-Pattern','-Path'],
    'Select-Object':['-Property','-First','-Last'],'Get-Help':['-Name'],find:['-name','-iname','-type','-maxdepth'],
    head:['-n','-c'],tail:['-n'],watch:['-n'],tasklist:['/fo','/fi'],ping:['-n'],git:sub==='commit'?['-m']:[]
  };return Object.hasOwn(map,name)?map[name]:[];}
  // Single backticks delimit the user's command. Fences/double-delimited Markdown
  // and escaped delimiters are excluded. An empty pair accepts the caret between it.
  function region(value,caret){
    let start=-1;
    for(let i=0;i<value.length;i++){
      if(value[i]!=='`')continue;
      let escapes=0;for(let j=i-1;j>=0&&value[j]==='\\';j--)escapes++;
      if(escapes%2)continue;
      let count=1;while(value[i+count]==='`')count++;
      if(count>1&&start<0){
        if(count===2&&caret===i+1)return {start:i+1,end:i+1};
        const close=value.indexOf('`'.repeat(count),i+count);
        if(close<0)return null;i=close+count-1;continue;
      }
      if(start<0){start=i+1;continue;}
      if(caret>=start&&caret<=i)return {start,end:i};
      start=-1;
    }
    return start>=0&&caret>=start?{start,end:value.length}:null;
  }
  // A conservative lexer: no completion in quoted arguments/comments. Operators
  // restart the command position; values and paths are never treated as flags.
  function tokens(value,offset,env){
    const result=[];let i=0;
    while(i<value.length){
      if(/\s/.test(value[i])){if(value[i]==='\n')result.push({operator:true,start:offset+i,end:offset+i+1});i++;continue;}
      if('|&;<>'.includes(value[i])){result.push({operator:true,redirect:'<>'.includes(value[i]),start:offset+i,end:offset+i+1});i++;continue;}
      if(env!=='cmd'&&value[i]==='#'){result.push({comment:true,start:offset+i,end:offset+value.length});break;}
      const begin=i;let quote=null,quoted=false;
      while(i<value.length){
        const ch=value[i];
        if((env==='bash'&&ch==='\\')||(env==='cmd'&&ch==='^')){i+=2;continue;}
        if(quote){if(ch===quote)quote=null;i++;continue;}
        if(ch==='"'||(env!=='cmd'&&ch==="'")){quote=ch;quoted=true;i++;continue;}
        if(/\s/.test(ch)||'|&;<>'.includes(ch))break;i++;
      }
      i=Math.min(i,value.length);result.push({value:value.slice(begin,i),start:offset+begin,end:offset+i,quoted});
    }
    return result;
  }
  function inspect(value,caret,env,selectionEnd=caret){
    const zone=region(value,caret),enabled=shellEnvs.includes(env);
    const state={inside:Boolean(zone),enabled,env,options:[],source:null,command:null,message:enabled?'已开启 · 在反引号内输入命令，Tab 补全':'请先设置 /env:bash、/env:powershell 或 /env:cmd'};
    if(!zone||selectionEnd!==caret)return state;
    if(!enabled)return {...state,message:state.message+'，再启用命令补全'};
    const all=tokens(value.slice(zone.start,zone.end),zone.start,env);
    if(all.some(t=>(t.quoted||t.comment)&&caret>=t.start&&caret<=t.end))return {...state,message:'字符串、路径和注释保留原文；此处不提供目录参数补全'};
    let segment=[],redirect=false;
    for(const token of all){
      if(token.operator){
        if(token.start>=caret)break;
        if(token.redirect)redirect=true;else{segment=[];redirect=false;}
      }else if(redirect){
        if(caret<=token.end)return {...state,message:'重定向目标是路径，此处不提供命令名补全'};
        redirect=false;
      }else segment.push(token);
    }
    if(redirect)return {...state,message:'请填写重定向目标路径'};
    let token=segment.find(t=>caret>=t.start&&caret<=t.end&&!t.operator);
    if(!token)token={value:'',start:caret,end:caret};
    const before=segment.filter(t=>t.end<token.start||t.end===token.start&&t!==token);
    const fragment=value.slice(token.start,caret),fold=s=>env==='bash'?s:s.toLowerCase();
    const matching=list=>list.filter(o=>fold(o.value).startsWith(fold(fragment))&&fold(o.value)!==fold(token.value));
    const entries=catalog(env);
    const wrap=list=>rank(list).map(o=>({...o,start:token.start,end:token.end,source:o.source||state.source,description:o.description+(o.usage?' · 常用 '+o.usage+' 次':o.origin==='user'?' · 自定义':'')}));
    if(!before.length){
      state.options=wrap(matching(entries.flatMap(c=>[c.name,...(c.aliases||[])].map(value=>({value,description:value===c.name?c.description:'别名 → '+c.name,source:c.source,usage:c.usage,origin:c.origin})))));
      state.message='命令名 · 可用目录 '+entries.length+' 项 · ↑↓ 选择 · Tab 补全';
      const exact=entries.find(c=>fold(c.name)===fold(token.value)||c.aliases?.some(a=>fold(a)===fold(token.value)));
      if(exact){state.command=exact.name;state.source=exact.source;state.message='已匹配 '+exact.name+'；空格后补全参数';}
      else if(!state.options.length&&fragment)state.message='公开目录未收录此命令，可继续输入；未执行可用性检测';
      return state;
    }
    const spec=entries.find(c=>fold(c.name)===fold(before[0].value)||c.aliases?.some(a=>fold(a)===fold(before[0].value)));
    if(!spec)return {...state,message:'公开目录未收录 '+before[0].value+'；保留原文，不判断远端是否安装'};
    state.command=spec.name;state.source=spec.source;const sub=before[1]?.value;
    const last=before.at(-1)?.value;
    if(valueFlags(spec.name,sub).some(flag=>fold(flag)===fold(last||''))){
      return {...state,message:spec.name+' · 请填写 '+last+' 的参数值；不会读取目标环境的文件或执行命令'};
    }
    let list=[];
    const valueKey=Object.keys(spec.values||{}).find(prefix=>fragment.startsWith(prefix));
    if(valueKey){
      if(valueKey==='--query-gpu='){
        const used=fragment.slice(valueKey.length).split(',');const tail=used.pop();const lead=valueKey+(used.length?used.join(',')+',':'');
        list=spec.values[valueKey].filter(o=>!used.includes(o.value)&&o.value.startsWith(tail)).map(o=>({...o,value:lead+o.value}));
      }else list=spec.values[valueKey].filter(o=>o.value.startsWith(fragment.slice(valueKey.length))).map(o=>({...o,value:valueKey+o.value}));
      list=list.filter(o=>o.value!==token.value);
    }else if(fragment.startsWith('-')||(env==='cmd'&&fragment.startsWith('/'))||!fragment){
      const subFlags=Object.hasOwn(spec.subFlags||{},sub)?spec.subFlags[sub]:[];
      list=[...spec.flags,...(Array.isArray(subFlags)?subFlags:[])];
      if(!fragment&&before.length===1)list=[...(spec.subcommands||[]),...list];
      const used=before.map(t=>fold(t.value.split('=')[0]));
      list=matching(list).filter(o=>!used.includes(fold(o.value.split('=')[0])));
    }else if(spec.subcommands&&before.length===1)list=matching(spec.subcommands);
    state.options=wrap(list);
    state.message=state.options.length?spec.name+' · 参数/子命令 · ↑↓ 选择 · Tab 补全':(fragment.startsWith('-')||env==='cmd'&&fragment.startsWith('/'))?'目录中无匹配参数；目录并非完整语法验证器':'已匹配 '+spec.name+'；参数值与路径由你填写';
    return state;
  }
  function apply(value,option){return {value:value.slice(0,option.start)+option.value+value.slice(option.end),caret:option.start+option.value.length};}
  function observations(value,env,raw=false){
    if(!shellEnvs.includes(env)||typeof value!=='string'||value.length>16000)return [];
    const bodies=[];
    if(raw)bodies.push(value);
    else for(let i=0;i<value.length;i++)if(value[i]==='`'){
      const zone=region(value,i+1);if(zone?.start===i+1){bodies.push(value.slice(zone.start,zone.end));i=zone.end;}
    }
    const found=[];
    for(const body of bodies){
      let group=[];
      const flush=()=>{
        const first=group[0];if(!first||first.quoted||!/^[a-zA-Z][a-zA-Z0-9_.+-]{0,63}$/.test(first.value))return;
        const spec=catalog(env).find(c=>foldFor(env,c.name)===foldFor(env,first.value)||c.aliases?.some(a=>foldFor(env,a)===foldFor(env,first.value)));
        const flags=[];let skipValue=false;
        for(const token of group.slice(1)){
          if(skipValue){skipValue=false;continue;}
          if(token.quoted)continue;
          if(token.value==='--')break;
          const flag=token.value.split(/[=:]/)[0],inlineValue=token.value!==flag;
          if(/(token|password|passwd|secret|credential|authorization|api.?key)/i.test(flag)||/^(?:-p|\/p)$/i.test(flag)&&spec?.name!=='dir'){
            skipValue=!inlineValue;continue;
          }
          const isFlag=/^--?[a-zA-Z][a-zA-Z0-9-]{0,31}$/.test(flag)||env==='cmd'&&/^\/[a-zA-Z][a-zA-Z0-9-]{0,31}$/.test(flag);
          if(!isFlag)continue;flags.push(flag);
          if(valueFlags(spec?.name||first.value,group[1]?.value).some(v=>foldFor(env,v)===foldFor(env,flag))||/^(?:--(?:output|file|path|config|name|id|header|data))$/i.test(flag))skipValue=!inlineValue;
        }
        const sub=spec?.subcommands?.find(o=>o.value===group[1]?.value);
        found.push({name:spec?.name||first.value,flags:[...new Set(flags)],subcommands:sub?[sub.value]:[]});
      };
      let redirect=false;
      for(const token of tokens(body,0,env)){
        if(token.comment)break;
        if(token.operator){if(token.redirect){redirect=true;continue;}flush();group=[];redirect=false;}
        else if(redirect)redirect=false;
        else group.push(token);
      }
      flush();
    }
    return found;
  }
  return {inspect,apply,catalogs,catalog,configure,observations,shellEnvs,sources,region};
});
