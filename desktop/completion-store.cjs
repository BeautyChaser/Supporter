/* Local user-owned metadata. No command arguments or conversation are persisted. */
const fs=require('node:fs');
const path=require('node:path');
const completion=require('./completion.js');
const envs=completion.shellEnvs;
const namePattern=/^[A-Za-z][A-Za-z0-9_.+-]{0,63}$/;
const tokenPattern=/^[^\s`"'\\\x00-\x1f\x7f]{1,128}$/;
const count=value=>Math.max(0,Math.min(1000000,Number.isFinite(value)?Math.floor(value):0));
function option(value){
  const row=typeof value==='string'?{value}:Array.isArray(value)?{value:value[0],description:value[1]}:value;
  if(!row||typeof row.value!=='string'||!tokenPattern.test(row.value))return null;
  return {value:row.value,description:String(row.description||'用户自定义').slice(0,160),origin:'user'};
}
class CompletionStore{
  constructor(directory){
    this.directory=directory;this.commands={};this.usage={};this.errors=[];this.learning=true;
    try{
      fs.mkdirSync(directory,{recursive:true});
      for(const env of envs){const file=path.join(directory,env+'.json');if(!fs.existsSync(file))this.atomic(file,{version:1,commands:[]});}
      const config=path.join(directory,'config.json');if(!fs.existsSync(config))this.atomic(config,{version:1,learning:true});
      const habits=path.join(directory,'habits.json');if(!fs.existsSync(habits))this.atomic(habits,{version:1,environments:{}});
    }catch(error){this.initError=error.message;}
    this.reload();
  }
  atomic(file,data){
    const content=JSON.stringify(data,null,2)+'\n';
    if(Buffer.byteLength(content,'utf8')>1024*1024)throw new Error('补全文件达到 1 MB 上限，请清理低频习惯后重试');
    const temporary=file+'.tmp';fs.writeFileSync(temporary,content,'utf8');fs.renameSync(temporary,file);
  }
  read(name){
    const file=path.join(this.directory,name);
    if(fs.statSync(file).size>1024*1024)throw new Error(name+' 超过 1 MB');
    return JSON.parse(fs.readFileSync(file,'utf8'));
  }
  reload(){
    this.errors=[this.initError,this.writeError].filter(Boolean);
    try{
      const config=this.read('config.json');if(!config||Array.isArray(config)||config.version!==1||typeof config.learning!=='boolean')throw new Error('需要 version: 1 与布尔值 learning');
      this.learning=config.learning;
    }catch(e){this.learning=false;this.errors.push('config.json: '+e.message);}
    for(const env of envs){
      try{
        const data=this.read(env+'.json');if(data.version!==1||!Array.isArray(data.commands))throw new Error('需要 version: 1 与 commands 数组');
        const specs=[];
        for(const raw of data.commands.slice(0,300)){
          if(!raw||!namePattern.test(raw.name||'')){this.errors.push(env+'.json: 无效命令名');continue;}
          const source='用户目录 · '+env+'.json';
          const options=rows=>(Array.isArray(rows)?rows:[]).map(option).filter(Boolean).slice(0,64).map(o=>({...o,source}));
          const values={};for(const [prefix,rows] of Object.entries(raw.values||{}))if(tokenPattern.test(prefix))Object.defineProperty(values,prefix,{value:options(rows),enumerable:true});
          specs.push({name:raw.name,description:String(raw.description||'用户自定义命令').slice(0,160),source,origin:'user',
            aliases:(Array.isArray(raw.aliases)?raw.aliases:[]).filter(a=>typeof a==='string'&&namePattern.test(a)).slice(0,16),
            flags:options(raw.flags),subcommands:options(raw.subcommands),values});
        }
        this.commands[env]=specs;
      }catch(e){this.errors.push(env+'.json: '+e.message);this.commands[env]??=[];}
    }
    try{
      const data=this.read('habits.json');if(data.version!==1||!data.environments||Array.isArray(data.environments)||typeof data.environments!=='object')throw new Error('需要 version: 1 与 environments 对象');
      for(const env of envs)this.usage[env]=(Array.isArray(data.environments[env])?data.environments[env]:[]).filter(r=>r&&namePattern.test(r.name||'')).slice(0,300).map(r=>({
        name:r.name,count:count(r.count),lastUsed:typeof r.lastUsed==='string'?r.lastUsed.slice(0,30):'',
        flags:this.validUsage(r.flags),subcommands:this.validUsage(r.subcommands)
      }));
    }catch(e){this.errors.push('habits.json: '+e.message);}
    return this.snapshot();
  }
  validUsage(rows){return (Array.isArray(rows)?rows:[]).filter(r=>r&&typeof r.value==='string'&&tokenPattern.test(r.value)).slice(0,64).map(r=>({value:r.value,count:count(r.count)}));}
  snapshot(){return {commands:this.commands,usage:this.usage,directory:this.directory,learning:this.learning,errors:this.errors};}
  observe(value,env,raw=false){
    if(!envs.includes(env))return false;
    // Reload user edits before learning, then update only the separate habit file.
    this.reload();if(!this.learning||this.errors.some(e=>e.startsWith('habits.json:')))return false;
    completion.configure(this.snapshot());const observations=completion.observations(value,env,raw);if(!observations.length)return false;
    const fold=value=>env==='bash'?value:value.toLowerCase();
    const rows=structuredClone(this.usage[env]||[]);
    for(const observation of observations){
      let row=rows.find(r=>fold(r.name)===fold(observation.name));
      if(!row){row={name:observation.name,count:0,lastUsed:'',flags:[],subcommands:[]};rows.push(row);}
      row.count=count(row.count+1);row.lastUsed=new Date().toISOString();
      for(const field of ['flags','subcommands'])for(const value of observation[field]){
        const item=row[field].find(o=>fold(o.value)===fold(value));if(item)item.count=count(item.count+1);else row[field].push({value,count:1});
        row[field].sort((a,b)=>b.count-a.count);row[field]=row[field].slice(0,64);
      }
    }
    const previous=this.usage[env];this.usage[env]=rows.sort((a,b)=>b.count-a.count||b.lastUsed.localeCompare(a.lastUsed)).slice(0,300);
    try{this.atomic(path.join(this.directory,'habits.json'),{version:1,environments:this.usage});this.writeError=null;return true;}
    catch(error){this.usage[env]=previous;this.writeError='习惯保存失败：'+error.message;this.errors.push(this.writeError);return false;}
  }
}
module.exports={CompletionStore};
