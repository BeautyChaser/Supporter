"""Private NDJSON child-process bridge for the Electron desktop shell."""
import json
import os
import queue
import sys
import threading
from dataclasses import asdict
from .backends import ROOT, DEFAULT, discover, presence, invalidate_discovery, generate, conversation_prompt, parse_response, stop, stop_detection
from . import windows
from .results import accepted_text
from .defaults import default_model,default_reasoning
from .connections import normalize_connection

lock=threading.Lock()
def emit(event_type, **data):
    with lock:
        print(json.dumps({'type':event_type,**data},ensure_ascii=False),flush=True)

def main():
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    events=queue.Queue(); ready=queue.Queue()
    target=None; backends=[]; current_cancel=threading.Event(); job=0; process=None; visible=False
    latest_result=None; transfer_pending=False
    running_client_id=None; running_job=None
    locations={};location_request=None
    settings_path=ROOT/'settings.json'
    try: settings=json.loads(settings_path.read_text(encoding='utf-8'))
    except (OSError,ValueError): settings={}
    scan_requested=threading.Event();scan_stopped=threading.Event();scan_lock=threading.Lock();scan_forced=False
    try:poll_seconds=max(0,float(os.environ.get('SUPPORTER_BACKEND_POLL_SECONDS','10')))
    except ValueError:poll_seconds=10
    def request_scan(force=False):
        nonlocal scan_forced
        with scan_lock:scan_forced=scan_forced or force;scan_requested.set()
    def scan_worker():
        nonlocal scan_forced
        initial=True
        while not scan_stopped.is_set():
            scan_requested.wait(poll_seconds if poll_seconds else None)
            if scan_stopped.is_set():break
            with scan_lock:
                force=scan_forced;scan_forced=False;scan_requested.clear()
            try:
                if force:invalidate_discovery()
                if not initial:events.put(('backend-inventory',{'backends':presence(),'phase':'presence'}))
                if scan_stopped.is_set():break
                events.put(('backend-inventory',{'backends':discover(),'phase':'complete'}));initial=False
            except Exception as error:events.put(('backend-scan-error',str(error)))
    warmed=set();last_inventory=None
    def apply_inventory(found,phase):
        nonlocal backends,settings,last_inventory
        backends=found
        available=[b for b in backends if not b.error]
        checking=any(b.status=='checking' for b in backends)
        old_backend=settings.get('backend','')
        pending_selected=any(b.name==old_backend and b.status=='checking' for b in backends)
        changed=False;notice=''
        if available and not pending_selected:
            chosen=next((b for b in available if b.name==old_backend),None) or next((b for b in available if b.name=='codex'),available[0])
            if chosen.name!=old_backend:
                settings={**settings,'backend':chosen.name};changed=True
                if old_backend:notice=old_backend+' 已不可用，已切换到 '+chosen.name+'；对话与候选已保留。'
            model=settings.get('models',{}).get(chosen.name)
            if model and model not in chosen.models and chosen.models_stale:chosen.models=[*chosen.models,model]
            if not model or model not in chosen.models:
                selected=default_model(chosen);settings={**settings,'models':{**settings.get('models',{}),chosen.name:selected}};changed=True
            else:selected=model
            preference=chosen.name+'|'+selected
            effort=settings.get('reasoning',{}).get(preference)
            if effort is None or not chosen.models_stale and effort not in ['default',*chosen.reasoning.get(selected,[])]:
                settings={**settings,'reasoning':{**settings.get('reasoning',{}),preference:default_reasoning(chosen,selected)}};changed=True
        elif not checking and phase=='complete' and old_backend:
            settings={**settings,'backend':''};changed=True;notice='当前没有可用后端。安装或启用后端插件后会自动更新；对话与候选已保留。'
        codex=next((b for b in backends if b.name=='codex' and not b.error),None)
        if codex and settings.get('backend')=='codex':
            warm_key=(codex.path,json.dumps(settings.get('codexConnection'),sort_keys=True))
            if warm_key not in warmed:
                warmed.add(warm_key)
                def warm():
                    try:
                        from .codex_runtime import get_runtime
                        get_runtime(codex.path,settings.get('codexConnection')).warm()
                    except Exception:pass
                threading.Thread(target=warm,daemon=True).start()
        if changed:
            try:
                temporary=settings_path.with_suffix('.json.tmp');temporary.write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(settings_path)
            except OSError as error:notice=(notice+' 偏好保存失败：'+str(error)).strip()
        value={'backends':[asdict(b) for b in backends],'settings':settings,'reason':'scan'}
        signature=json.dumps(value,sort_keys=True,ensure_ascii=False)
        if signature!=last_inventory or notice:
            last_inventory=signature;emit('inventory',**value,notice=notice)
    request_scan();threading.Thread(target=scan_worker,daemon=True).start()
    def read():
        for line in sys.stdin:
            try: events.put(('command',json.loads(line)))
            except ValueError: pass
        events.put(('command',{'type':'quit'}))
    threading.Thread(target=read,daemon=True).start()
    emit('ready',error=None)
    while True:
        kind,value=events.get()
        if kind=='backend-inventory':apply_inventory(value['backends'],value['phase']);continue
        if kind=='backend-scan-error':emit('backend-scan-error',message=value);continue
        if kind=='model-result':
            if value['id']==job:
                running_job=None;running_client_id=None
                parsed=value['payload'];latest_result=value
                emit('result',text=parsed['result'],reply=parsed['reply'],kind=parsed['kind'],candidates=parsed['candidates'],response_id=job,client_request_id=value.get('client_request_id'))
            continue
        if kind=='model-error':
            if value['id']==job:
                running_job=None;running_client_id=None
                emit('error',message=value['message'],client_request_id=value.get('client_request_id'))
            continue
        if kind=='wake' or (kind=='command' and value.get('type')=='capture'):
            if visible and not value.get('force'): continue
            locations={};location_request=None
            if not transfer_pending:current_cancel.set();job+=1;running_job=None;running_client_id=None
            try:target=windows.capture() if kind=='command' else value
            except Exception as e:
                visible=False;emit('error',message=str(e),capture_request_id=value.get('request_id'));continue
            visible=True
            if not transfer_pending: latest_result=None
            emit('wake',target=target,resume=transfer_pending,request_id=value.get('request_id'))
            transfer_pending=False
            continue
        cmd=value; action=cmd.get('type')
        if action=='locate-window':
            location_request=cmd.get('request_id');locations={}
            try:
                if not target:raise RuntimeError('请先在目标窗口按唤醒快捷键')
                listing=windows.list_inputs(target);locations={c['id']:c for c in listing['controls']}
                emit('locate-results',request_id=location_request,controls=list(locations.values()),limited=listing.get('limited',False),title=target.get('title','原窗口'))
            except Exception as e:emit('locate-error',request_id=location_request,message=str(e))
            continue
        if action=='locate-select':
            try:
                if not target or cmd.get('request_id')!=location_request or cmd.get('candidate_id') not in locations:raise RuntimeError('输入位置列表已过期，请重新执行 /loc:window')
                target=windows.focus_input(target,cmd['candidate_id']);visible=True;transfer_pending=False
                locations={};location_request=None
                emit('wake',target=target,resume=True,request_id=cmd.get('request_id'))
            except Exception as e:emit('locate-error',request_id=cmd.get('request_id'),message=str(e))
            continue
        if action=='terminal-mode' and target:
            enabled=bool(cmd.get('enabled'))
            target['terminal']=enabled
            target['scope']=('terminal-line' if target.get('command') is not None else 'terminal-unknown') if enabled else target.get('editor_scope','insert')
            target['context']=(target.get('command') or '') if enabled else target.get('editor_context','')
            emit('context-updated',target=target)
            continue
        if action=='refresh':request_scan(cmd.get('force',True))
        elif action=='cancel-generation':
            cancelled_id=cmd.get('client_request_id') or running_client_id
            if running_job is None:
                emit('generation-stopped',client_request_id=cancelled_id);continue
            if cancelled_id and running_client_id and cancelled_id!=running_client_id:
                emit('generation-stopped',client_request_id=cancelled_id);continue
            current_cancel.set();job+=1;latest_result=None
            running_client_id=None;running_job=None
            emit('generation-stopped',client_request_id=cancelled_id)
        elif action=='suspend':
            visible=False;transfer_pending=True
        elif action=='settings':
            try:
                next_settings=cmd['settings']
                if 'codexConnection' in next_settings:next_settings={**next_settings,'codexConnection':normalize_connection(next_settings['codexConnection'])}
                temporary=settings_path.with_suffix('.json.tmp')
                temporary.write_text(json.dumps(next_settings,ensure_ascii=False,indent=2),encoding='utf-8')
                temporary.replace(settings_path)
                settings=next_settings
                if cmd.get('request_id'): emit('settings-persisted',request_id=cmd['request_id'])
            except Exception as e: emit('settings-persist-error',request_id=cmd.get('request_id'),message=str(e))
        elif action=='retarget':
            transfer_pending=True;visible=False
            if target:
                try: windows.restore(target)
                except RuntimeError: pass
        elif action in ('cancel','quit'):
            visible=False
            current_cancel.set(); job+=1
            running_job=None;running_client_id=None
            locations={};location_request=None
            latest_result=None;transfer_pending=False
            if action=='quit':
                scan_stopped.set();scan_requested.set();stop_detection()
                stop(process)
                from .codex_runtime import close_all
                close_all()
                break
            if target and cmd.get('restore',True):
                try: windows.restore(target)
                except RuntimeError: pass
        elif action in ('accept','copy') and target:
            try:
                if not latest_result or cmd.get('response_id')!=latest_result['id']:
                    raise ValueError('候选已过期，请重新生成')
                payload=latest_result['payload']
                text=accepted_text(payload,cmd.get('candidate_index'),False)
                multiline='\n' in text or '\r' in text
                physical_terminal=target.get('physical_terminal',target.get('terminal',False))
                copy_only=(action=='copy' or target.get('scope') not in ('selection','editor','terminal-line') or
                    (physical_terminal and payload['kind']!='commands') or (multiline and target.get('supports_multiline') is False))
                if copy_only:
                    visible=False;transfer_pending=True
                    emit('copy-ready',text=text,response_id=latest_result['id'])
                    continue
                text=accepted_text(payload,cmd.get('candidate_index'),physical_terminal)
                if latest_result.get('environment')=='code':target={**target,'paste_mode':'standard'}
                visible=False
                windows.insert(target,text,replace=True)
                latest_result=None;transfer_pending=True
                emit('accepted')
            except Exception as e:
                visible=True
                emit('error',message=str(e))
        elif action=='clipboard-written' and target:
            try:windows.restore(target)
            except RuntimeError:pass
        elif action=='restore-target' and target:
            try:windows.restore(target)
            except RuntimeError:pass
        elif action=='generate':
            current_cancel.set(); job+=1
            latest_result=None
            current_cancel=threading.Event()
            running_client_id=cmd.get('client_request_id');running_job=job
            b=next((b for b in backends if b.name==cmd['backend'] and not b.error),None)
            if b is None:
                emit('error',message='请选择已检测通过的 CLI',client_request_id=running_client_id)
                running_job=None;running_client_id=None
                request_scan()
                continue
            def track(p):
                nonlocal process
                process=p
            def work(b=b,cmd=cmd,cancel=current_cancel,job_id=job,snapshot=target,connection=settings.get('codexConnection')):
                try:
                    def progress(message):
                        if job_id==job: emit('progress',message=message,client_request_id=cmd.get('client_request_id'))
                    progress('已读取原文，正在启动 '+b.name)
                    result=generate(b,cmd.get('model',DEFAULT),conversation_prompt(snapshot.get('context','') if snapshot else '',cmd.get('history',[]),cmd['request'],cmd.get('terminal',False),cmd.get('environment','auto')),cancel,track,cmd.get('reasoning','default'),progress,connection=connection)
                    parsed=parse_response(result,terminal=cmd.get('terminal',False),request=cmd['request'],history=cmd.get('history',[]),environment=cmd.get('environment','auto'))
                    events.put(('model-result',{'id':job_id,'payload':parsed,'environment':cmd.get('environment','auto'),'client_request_id':cmd.get('client_request_id')}))
                except Exception as e:
                    events.put(('model-error',{'id':job_id,'message':str(e),'client_request_id':cmd.get('client_request_id')}))
            threading.Thread(target=work,daemon=True).start()

if __name__=='__main__': main()
