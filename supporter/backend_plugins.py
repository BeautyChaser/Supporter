"""Reloadable, declarative backend plugins and machine-local CLI detection."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass,replace
from copy import deepcopy
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import threading
import time

from .paths import DATA_ROOT
ROOT=DATA_ROOT
_cache={}
_lock=threading.Lock()
MODEL_TTL=180

@dataclass(frozen=True)
class Plugin:
    id:str
    label:str
    adapter:str
    revision:str
    data:dict
    source:Path

def search_path():
    """Include installer changes without changing the parent's environment."""
    parts=[os.environ.get('PATH','')]
    if os.name=='nt':
        import winreg
        for hive,key in [(winreg.HKEY_CURRENT_USER,r'Environment'),(winreg.HKEY_LOCAL_MACHINE,r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment')]:
            try:
                with winreg.OpenKey(hive,key) as handle:parts.append(winreg.QueryValueEx(handle,'Path')[0])
            except OSError:pass
    return os.pathsep.join(dict.fromkeys(os.path.expandvars(p.strip('"')) for value in parts for p in value.split(os.pathsep) if p))

def _strings(value,name,*,empty=True):
    if not isinstance(value,list) or len(value)>64 or not all(isinstance(v,str) and len(v)<=4096 and '\x00' not in v for v in value) or (not empty and not value):
        raise ValueError(name+' 需要有效的字符串数组')
    return value

def load_plugins(directory=None):
    directory=Path(directory or os.environ.get('SUPPORTER_BACKEND_DIR') or ROOT/'backend-plugins')
    plugins=[];errors=[];ids=set()
    for file in sorted(directory.glob('*.json'))[:64]:
        try:
            if file.stat().st_size>65536:raise ValueError('插件描述超过 64 KB')
            raw=file.read_bytes();data=json.loads(raw)
            if not isinstance(data,dict) or type(data.get('schemaVersion')) is not int or data['schemaVersion']!=1:raise ValueError('需要 schemaVersion: 1')
            identifier=data.get('id','')
            if not isinstance(identifier,str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,47}',identifier):raise ValueError('无效插件 id')
            if identifier in ids:raise ValueError('插件 id 重复：'+identifier)
            if 'enabled' in data and not isinstance(data['enabled'],bool):raise ValueError('enabled 必须是布尔值')
            if data.get('enabled',True) is False:continue
            if data.get('adapter') not in ('codex','opencode','hermes','generic'):raise ValueError('未知 adapter')
            detect=data.get('detect',{})
            if not isinstance(detect,dict):raise ValueError('detect 需要对象')
            _strings(detect.get('commands',[]),'detect.commands')
            _strings(detect.get('pathGlobs',[]),'detect.pathGlobs')
            if not detect.get('commands') and not detect.get('pathGlobs'):raise ValueError('请声明可检测的命令或路径')
            _strings(detect.get('versionArgs',['--version']),'versionArgs',empty=False)
            if any('{' in arg or '}' in arg for arg in detect.get('versionArgs',[])):raise ValueError('检测参数不接受动态模板')
            if detect.get('selection','first') not in ('first','newest'):raise ValueError('无效 selection')
            if type(data.get('priority',100)) is not int:raise ValueError('priority 需要整数')
            if data['adapter']=='generic':
                generate=data.get('generate')
                if not isinstance(generate,dict):raise ValueError('generic 插件需要 generate')
                for field in ('args','modelArgs','reasoningArgs'):_strings(generate.get(field,[]),'generate.'+field)
                for arg in [*generate.get('args',[]),*generate.get('modelArgs',[]),*generate.get('reasoningArgs',[])]:
                    if any(name not in ('prompt','model','reasoning','query_file','output_file') for name in re.findall(r'\{([A-Za-z_][A-Za-z0-9_]*)\}',arg)):raise ValueError('未知的生成参数模板')
                if generate.get('stdin','prompt') not in ('prompt','none'):raise ValueError('无效 stdin 模式')
                output=generate.get('output',{})
                if not isinstance(output,dict) or output.get('format','text') not in ('text','json','jsonl'):raise ValueError('无效输出格式')
                if 'fromFile' in output and not isinstance(output['fromFile'],bool):raise ValueError('output.fromFile 必须是布尔值')
                for key in ('field','eventType'):
                    if key in output and not isinstance(output[key],str):raise ValueError('output.'+key+' 需要字符串')
                models=data.get('models',{})
                if not isinstance(models,dict):raise ValueError('models 需要对象')
                _strings(models.get('args',[]),'models.args')
                _strings(models.get('values',[]),'models.values')
                if models.get('format','lines') not in ('lines','json'):raise ValueError('无效模型目录格式')
                if not isinstance(models.get('field',''),str):raise ValueError('models.field 需要字符串')
                reasoning=data.get('reasoning',{})
                if not isinstance(reasoning,dict):raise ValueError('reasoning 需要对象')
                for levels in reasoning.values():_strings(levels,'reasoning levels')
                env=generate.get('env',{})
                if not isinstance(env,dict) or not all(isinstance(k,str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',k) and isinstance(v,str) and '\x00' not in v for k,v in env.items()):raise ValueError('无效子进程环境')
            ids.add(identifier)
            plugins.append(Plugin(identifier,str(data.get('label',identifier))[:80],data['adapter'],hashlib.sha256(raw).hexdigest(),data,file))
        except (OSError,ValueError,TypeError) as error:errors.append((file.stem,str(error)))
    return sorted(plugins,key=lambda p:(p.data.get('priority',100),p.id)),errors

def candidates(plugin):
    result=[];detect=plugin.data['detect'];paths=search_path()
    for value in detect.get('commands',[]):
        expanded=os.path.expandvars(os.path.expanduser(value))
        if '/' in expanded or '\\' in expanded:
            path=Path(expanded)
            if not path.is_absolute():path=ROOT/path
            if path.is_file():result.append(str(path.resolve()))
        else:
            found=shutil.which(expanded,path=paths)
            if found:result.append(str(Path(found).resolve()))
    for value in detect.get('pathGlobs',[]):
        expanded=os.path.expandvars(os.path.expanduser(value))
        if not Path(expanded).is_absolute():expanded=str(ROOT/expanded)
        result.extend(str(Path(p).resolve()) for p in sorted(glob.glob(expanded))[:24] if Path(p).is_file())
    return list(dict.fromkeys(result))[:24]

def _signature(plugin,paths,adapter):
    files=[*paths,*adapter.watch_paths()]
    records=[]
    for value in files:
        try:s=Path(value).stat();records.append((str(value),s.st_size,s.st_mtime_ns))
        except OSError:records.append((str(value),None,None))
    return plugin.revision,tuple(records)

def _probe(plugin,ctx,*,force=False,presence=False):
    from .backend_adapters import ADAPTERS
    adapter=ADAPTERS[plugin.adapter];paths=candidates(plugin);key=(str(plugin.source.resolve()),plugin.id)
    signature=_signature(plugin,paths,adapter)
    with _lock:cached=_cache.get(key)
    if not paths:return ctx.Backend(plugin.id,error='未安装 / 不在本机搜索路径中',adapter=plugin.adapter,plugin_revision=plugin.revision,display_name=plugin.label,status='missing')
    if cached and cached[0]==signature and (presence or not force and time.monotonic()-cached[1]<(30 if cached[2].error or cached[2].models_stale else MODEL_TTL)):
        return deepcopy(cached[2])
    if presence:
        if cached and cached[2].path in paths and Path(cached[2].path).is_file():
            return replace(deepcopy(cached[2]),status='checking',error='后端有变化，正在重新检测',plugin_revision=plugin.revision)
        return ctx.Backend(plugin.id,path=paths[0],error='正在检测 CLI',adapter=plugin.adapter,plugin_revision=plugin.revision,display_name=plugin.label,status='checking')
    b=ctx.Backend(plugin.id,adapter=plugin.adapter,plugin_revision=plugin.revision,display_name=plugin.label,status='unavailable')
    versions=[]
    for path in paths:
        if plugin.adapter=='generic' and Path(path).suffix.lower() in ('.cmd','.bat','.ps1'):
            b.error='通用插件请声明原生可执行文件或 Python/Node 解释器入口';continue
        try:
            lines=ctx.call(path,plugin.data['detect'].get('versionArgs',['--version']),timeout=4).splitlines()
            if not lines:raise RuntimeError('CLI 未返回版本信息')
            versions.append((path,lines[0][:200]))
            if plugin.data['detect'].get('selection','first')=='first':break
        except Exception as error:b.error=str(error)[:250]
    if versions:
        def version_key(row):
            match=re.search(r'(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?',row[1])
            if not match:return (0,0,0,False,())
            major,minor,patch,suffix=match.groups()
            prerelease=tuple((0,int(part)) if part.isdigit() else (1,part.lower()) for part in re.findall(r'[0-9]+|[A-Za-z]+',suffix or ''))
            return (int(major),int(minor),int(patch),not bool(suffix),prerelease)
        b.path,b.version=max(versions,key=version_key) if plugin.data['detect'].get('selection')=='newest' else versions[0]
        b.error='';b.status='available'
        try:adapter.enrich(b,ctx,plugin)
        except Exception as error:
            b.models_stale=True;b.source='模型检测失败，仍可使用默认模型：'+str(error)[:180]
            if cached and cached[2].path==b.path and cached[2].plugin_revision==plugin.revision:
                b.models=list(cached[2].models);b.reasoning=dict(cached[2].reasoning)
                b.source='模型更新失败，暂保留上次目录（待复核）：'+str(error)[:160]
    with _lock:_cache[key]=(signature,time.monotonic(),b)
    return deepcopy(b)

def discover(ctx,*,force=False,presence=False):
    plugins,errors=load_plugins()
    def probe(plugin):return _probe(plugin,ctx,force=force,presence=presence)
    with ThreadPoolExecutor(max_workers=4) as pool:backends=list(pool.map(probe,plugins))
    return backends+[ctx.Backend(name,error='插件描述无效：'+error,status='plugin-error') for name,error in errors]

def discover_one(name,ctx):
    plugins,_=load_plugins();plugin=next((p for p in plugins if p.id==name),None)
    return _probe(plugin,ctx,force=True) if plugin else ctx.Backend(name,error='后端插件不存在或已停用',status='missing')

def generate(backend,ctx,*args,**kwargs):
    from .backend_adapters import ADAPTERS
    plugins,_=load_plugins();plugin=next((p for p in plugins if p.id==backend.name),None)
    if plugin is None:raise RuntimeError('后端插件已移除或停用，请重新选择后端')
    if backend.plugin_revision and backend.plugin_revision!=plugin.revision:raise RuntimeError('后端插件配置已变化，正在重新检测，请稍后重试')
    if backend.error or not backend.path:raise RuntimeError(backend.error or 'CLI 路径不可用，请等待重新检测')
    return ADAPTERS[plugin.adapter].generate(backend,ctx,plugin,*args,**kwargs)

def invalidate():
    with _lock:
        # A new machine can have a monotonic clock below MODEL_TTL.
        for key,(signature,_,backend) in list(_cache.items()):_cache[key]=(signature,float('-inf'),backend)
