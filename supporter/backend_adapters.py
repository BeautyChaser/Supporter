"""Independent adapter implementations behind the backend plugin contract."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import tomllib

@dataclass
class Invocation:
    args:list
    input_text:str|None=None
    env:dict|None=None
    output_file:Path|None=None
    output_format:str='text'
    output_field:str='text'
    event_type:str=''
    strip_sessions:bool=False

def field(value,key):
    for part in key.split('.') if key else []:
        if not isinstance(value,dict):return None
        value=value.get(part)
    return value

def execute(ctx,b,invocation,cancel,process_callback,progress):
    p,data=ctx.launch(b.path,invocation.args,input_text=invocation.input_text,env=invocation.env)
    process_callback(p)
    if progress:progress('CLI 已启动，等待模型响应')
    result=[];errors=[]
    def communicate():
        try:
            if not progress:result.append(p.communicate(data));return
            out=[];err=[]
            def read_err():
                for line in p.stderr:err.append(line)
            stderr=threading.Thread(target=read_err,daemon=True);stderr.start()
            if data:p.stdin.write(data)
            p.stdin.close()
            for line in p.stdout:
                out.append(line)
                try:
                    kind=json.loads(line).get('type','')
                    if kind in ('thread.started','turn.started','step_start'):progress('模型已开始处理')
                    elif kind in ('text','message.updated','item.completed','item.started'):progress('正在生成回复和待替换结果')
                    elif kind in ('turn.completed','step_finish'):progress('模型已返回，正在校验结果')
                except (ValueError,AttributeError):pass
            p.wait();stderr.join(2);result.append((''.join(out),''.join(err)))
        except Exception as error:errors.append(error)
    worker=threading.Thread(target=communicate,daemon=True);worker.start();deadline=time.monotonic()+180
    while worker.is_alive():
        if cancel.wait(.1) or time.monotonic()>deadline:
            ctx.stop(p);worker.join(3);raise RuntimeError('已取消或请求超时')
    if errors:raise RuntimeError('读取 CLI 回复失败：'+str(errors[0]))
    out,err=result[0]
    if p.returncode:raise RuntimeError((err or out or 'CLI 调用失败')[-1600:])
    if invocation.output_file:
        out=invocation.output_file.read_text(encoding='utf-8') if invocation.output_file.exists() else ''
    if invocation.output_format in ('json','jsonl'):
        rows=[out] if invocation.output_format=='json' else out.splitlines();parts=[]
        for row in rows:
            try:record=json.loads(row)
            except ValueError:
                if invocation.output_format=='json':raise RuntimeError('CLI 返回的 JSON 无效')
                continue
            if isinstance(record,dict) and record.get('type')=='error':raise RuntimeError(str(record.get('error',record))[:1600])
            if invocation.event_type and (not isinstance(record,dict) or record.get('type')!=invocation.event_type):continue
            value=field(record,invocation.output_field)
            if isinstance(value,str):parts.append(value)
        text=''.join(parts)
    else:text=out
    if invocation.strip_sessions:text=re.sub(r'(?m)^.*session_id[:=].*$','',text).strip()
    if not text.strip():raise RuntimeError('CLI 未返回候选文本，请检查登录和模型配置')
    return text.strip()

class Adapter:
    def watch_paths(self):return []
    def enrich(self,b,ctx,plugin):pass
    def generate(self,b,ctx,plugin,model,prompt,cancel,process_callback=lambda p:None,reasoning='default',on_progress=None,*,connection=None):
        if reasoning!='default' and reasoning not in b.reasoning.get(model,[]):raise RuntimeError('当前模型未声明支持此推理强度，请重新选择')
        runtime=ctx.ROOT/'.runtime';runtime.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='request-',dir=runtime) as directory:
            return execute(ctx,b,self.plan(b,ctx,plugin,model,prompt,Path(directory),reasoning,on_progress,connection),cancel,process_callback,on_progress)

class CodexAdapter(Adapter):
    def watch_paths(self):
        home=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))
        return [home/'models_cache.json',home/'config.toml']
    def enrich(self,b,ctx,plugin):
        home=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))
        cache=ctx.read_json(home/'models_cache.json')
        for item in cache.get('models',[]):b.reasoning[item.get('slug','')]=[x['effort'] for x in item.get('supported_reasoning_levels',[]) if x.get('effort')]
        models=[m['slug'] for m in cache.get('models',[]) if m.get('slug') and m.get('visibility','list')=='list']
        config=home/'config.toml'
        if config.exists():
            chosen=tomllib.loads(config.read_text(encoding='utf-8')).get('model')
            if chosen:models.insert(0,chosen)
        b.models+=list(dict.fromkeys(m for m in models if isinstance(m,str) and m))
        b.reasoning[ctx.DEFAULT]=b.reasoning.get(models[0] if models else '',[])
        b.source='Codex 配置 / 模型缓存（可能过期；权限以实际调用为准）'
    def generate(self,b,ctx,plugin,model,prompt,cancel,process_callback=lambda p:None,reasoning='default',on_progress=None,*,connection=None):
        if Path(b.path).suffix.lower()=='.exe':
            if reasoning!='default' and reasoning not in b.reasoning.get(model,[]):raise RuntimeError('当前模型未声明支持此推理强度，请重新选择')
            from .codex_runtime import generate
            return generate(b.path,None if model==ctx.DEFAULT else model,prompt,cancel,reasoning,on_progress,process_callback=process_callback,connection=connection)
        return super().generate(b,ctx,plugin,model,prompt,cancel,process_callback,reasoning,on_progress,connection=connection)
    def plan(self,b,ctx,plugin,model,prompt,tmp,reasoning,progress,connection):
        from .connections import connection_environment
        output=tmp/'response.txt';args=['exec','--skip-git-repo-check','--ephemeral','--sandbox','read-only','--color','never','-o',str(output),'-']
        if progress:args.insert(1,'--json')
        if model!=ctx.DEFAULT:args+=['--model',model]
        if reasoning!='default':args+=['-c','model_reasoning_effort='+json.dumps(reasoning)]
        return Invocation(args,prompt,connection_environment(connection),output)

class OpenCodeAdapter(Adapter):
    def watch_paths(self):
        paths=[Path.home()/'.config/opencode/opencode.json',Path.home()/'.config/opencode/opencode.jsonc']
        if os.environ.get('OPENCODE_CONFIG'):paths.insert(0,Path(os.environ['OPENCODE_CONFIG']))
        return paths
    def enrich(self,b,ctx,plugin):
        help_text=ctx.call(b.path,['run','--help'],timeout=6)
        b.reasoning_style='model-suffix' if 'provider/model#variant' in help_text else 'variant'
        models=[line.strip() for line in ctx.call(b.path,['models'],timeout=15).splitlines() if re.fullmatch(r'[\w.-]+/[\w./:@-]+',line.strip())]
        b.models+=list(dict.fromkeys(models));b.source='opencode models 目录（权限以实际调用为准）'
        for config_path in self.watch_paths():
            for provider,config in ctx.read_json(config_path).get('provider',{}).items():
                for model_id,meta in config.get('models',{}).items():b.reasoning[provider+'/'+model_id]=[k for k,v in meta.get('variants',{}).items() if not isinstance(v,dict) or not v.get('disabled')]
    def plan(self,b,ctx,plugin,model,prompt,tmp,reasoning,progress,connection):
        args=['run','--format','json',prompt]
        if model!=ctx.DEFAULT:args+=['--model',model+('#'+reasoning if reasoning!='default' and b.reasoning_style=='model-suffix' else '')]
        if reasoning!='default' and b.reasoning_style!='model-suffix':args+=['--variant',reasoning]
        return Invocation(args,env={**os.environ,'OPENCODE_PERMISSION':json.dumps({'*':'deny'})},output_format='jsonl',output_field='part.text',event_type='text')

class HermesAdapter(Adapter):
    def watch_paths(self):
        home=Path(os.environ.get('HERMES_HOME',str(Path.home()/'.hermes')))
        return [home/'config.yaml',home/'provider_models_cache.json']
    def enrich(self,b,ctx,plugin):
        home=Path(os.environ.get('HERMES_HOME',str(Path.home()/'.hermes')));py=Path(b.path).parent/'python.exe';models=[]
        if py.exists() and (home/'config.yaml').exists():
            code="import yaml,json,sys; c=yaml.safe_load(open(sys.argv[1],encoding='utf-8')) or {}; m=c.get('model',{}); print(json.dumps([m] if isinstance(m,str) else [m.get('default','')]))"
            models+=json.loads(ctx.call(str(py),['-c',code,str(home/'config.yaml')],timeout=5))
        cache=ctx.read_json(home/'provider_models_cache.json')
        if py.exists() and (home/'config.yaml').exists():
            code="import yaml,json,sys; c=yaml.safe_load(open(sys.argv[1],encoding='utf-8')) or {}; m=c.get('model',{}); print(json.dumps(m.get('provider','') if isinstance(m,dict) else ''))"
            provider=json.loads(ctx.call(str(py),['-c',code,str(home/'config.yaml')],timeout=5));models+=cache.get(provider,{}).get('models',[])
        for provider,entry in cache.items():
            if isinstance(entry,dict):models+=[provider+' :: '+m for m in entry.get('models',[]) if isinstance(m,str)]
        b.models+=list(dict.fromkeys(m for m in models if isinstance(m,str) and m));b.source='Hermes 配置 / 供应商缓存；provider :: model 绑定供应商（缓存可能过期）'
        for model in b.models:b.reasoning[model]=['none','minimal','low','medium','high','xhigh','max','ultra']
    def plan(self,b,ctx,plugin,model,prompt,tmp,reasoning,progress,connection):
        query=tmp/'prompt.txt';query.write_text(prompt,encoding='utf-8')
        args=['--ignore-rules','chat','--query-file',str(query),'--oneshot','-Q','-t','none','--max-turns','1']
        if ' :: ' in model:provider,model=model.split(' :: ',1);args+=['--provider',provider]
        if model!=ctx.DEFAULT:args+=['--model',model]
        if reasoning!='default':args+=['--reasoning',reasoning]
        return Invocation(args,strip_sessions=True)

def substitute(args,values):
    result=[]
    for argument in args:
        names=re.findall(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}',argument)
        if any(name not in values for name in names):raise ValueError('插件使用了未知参数模板')
        result.append(re.sub(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}',lambda match:values[match[1]],argument))
    return result

class GenericAdapter(Adapter):
    def generate(self,b,ctx,plugin,*args,**kwargs):
        if Path(b.path).suffix.lower() in ('.cmd','.bat','.ps1'):raise RuntimeError('通用插件需要原生可执行文件或解释器入口，不支持 batch/PowerShell 启动器')
        return super().generate(b,ctx,plugin,*args,**kwargs)
    def enrich(self,b,ctx,plugin):
        spec=plugin.data.get('models',{});models=list(spec.get('values',[]))
        if spec.get('args'):
            output=ctx.call(b.path,spec['args'],timeout=10)
            parsed=field(json.loads(output),spec.get('field','')) if spec.get('format')=='json' else output.splitlines()
            if not isinstance(parsed,list):raise ValueError('模型目录需为名称数组')
            models+=parsed
        b.models+=list(dict.fromkeys(m.strip() for m in models if isinstance(m,str) and m.strip() and len(m)<=200 and not any(ord(c)<32 for c in m)))[:500]
        for model in b.models:b.reasoning[model]=plugin.data.get('reasoning',{}).get(model,plugin.data.get('reasoning',{}).get('*',[]))
        b.source='插件声明 / CLI 模型目录（未验证账号调用权限）'
    def plan(self,b,ctx,plugin,model,prompt,tmp,reasoning,progress,connection):
        spec=plugin.data['generate'];query=tmp/'prompt.txt';query.write_text(prompt,encoding='utf-8');output=tmp/'response.txt'
        values={'prompt':prompt,'model':model,'reasoning':reasoning,'query_file':str(query),'output_file':str(output)}
        args=list(spec.get('args',[]))
        if model!=ctx.DEFAULT:args+=spec.get('modelArgs',[])
        if reasoning!='default':
            if not spec.get('reasoningArgs'):raise ValueError('插件没有声明推理档位参数')
            args+=spec['reasoningArgs']
        out=spec.get('output',{})
        return Invocation(substitute(args,values),prompt if spec.get('stdin','prompt')=='prompt' else None,
            {**os.environ,**spec.get('env',{})},output if out.get('fromFile') else None,out.get('format','text'),out.get('field','text'),out.get('eventType',''))

ADAPTERS={'codex':CodexAdapter(),'opencode':OpenCodeAdapter(),'hermes':HermesAdapter(),'generic':GenericAdapter()}
