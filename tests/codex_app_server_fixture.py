"""Minimal stdio protocol fixture. Never executes requested commands."""
import json
import sys
import threading
import time

sys.stdin.reconfigure(encoding='utf-8');sys.stdout.reconfigure(encoding='utf-8')
options=json.loads(sys.argv[1]) if len(sys.argv)>1 else {}
thread=0;turn=0;pending=None;active={};output_lock=threading.Lock()
def send(value):
    with output_lock:print(json.dumps(value),flush=True)
def answer(request,value):send({'id':request['id'],'result':value})
def complete(thread_id,turn_id,text,*,final_only=False,final_delay=0):
    cancelled=active[turn_id]['cancelled']
    if cancelled.is_set():return
    if not final_only:
        send({'method':'item/agentMessage/delta','params':{'threadId':thread_id,'turnId':turn_id,'itemId':'answer','delta':'stale delta'}})
    if cancelled.wait(final_delay):return
    send({'method':'item/completed','params':{'threadId':thread_id,'turnId':turn_id,'item':{'type':'agentMessage','id':'answer','text':text}}})
    send({'method':'turn/completed','params':{'threadId':thread_id,'turn':{'id':turn_id,'status':'completed','items':[]}}})

def delayed_complete(thread_id,turn_id,text,delay,final_delay,final_only=False):
    if not active[turn_id]['cancelled'].wait(delay):
        complete(thread_id,turn_id,text,final_delay=final_delay,final_only=final_only)

for raw in sys.stdin:
    request=json.loads(raw);method=request.get('method');params=request.get('params',{})
    if method=='initialize':
        time.sleep(options.get('initializeDelay',0));answer(request,{'userAgent':'fixture'})
    elif method=='initialized':pass
    elif method=='thread/start':
        time.sleep(options.get('threadDelay',0));thread+=1
        result={'thread':{'id':f'thread-{thread}'}}
        effort=params.get('config',{}).get('model_reasoning_effort',options.get('inheritedEffort','xhigh'))
        shape=options.get('reportedEffortShape','top-level')
        if shape=='top-level':result['reasoningEffort']=effort
        elif shape=='nested':result['thread']['reasoningEffort']=effort
        answer(request,result)
    elif method=='turn/start':
        turn+=1;tid=params['threadId'];turn_id=f'turn-{turn}';text=params['input'][0]['text']
        active[turn_id]={'threadId':tid,'cancelled':threading.Event()}
        time.sleep(options.get('turnDelay',0))
        answer(request,{'turn':{'id':turn_id,'status':'inProgress','items':[]}})
        send({'method':'item/completed','params':{'threadId':tid,'turnId':turn_id,'item':{'type':'userMessage','id':'input','content':[]}}})
        if text=='crash':sys.exit(7)
        if text=='wait':pending=(tid,turn_id);continue
        if text=='tool-request':
            pending=(tid,turn_id)
            send({'id':'server-approval','method':'item/commandExecution/requestApproval','params':{'threadId':tid,'turnId':turn_id,'command':'must never execute'}})
            continue
        if text=='tool-event':
            send({'method':'item/started','params':{'threadId':tid,'turnId':turn_id,'item':{'type':'commandExecution','id':'forbidden'}}});continue
        result=json.dumps({'reply':'done','kind':'text','candidates':[{'label':'result','detail':'','text':'line one\nline two'}]})
        if text=='fatal-error':
            send({'method':'error','params':{'threadId':tid,'turnId':turn_id,'willRetry':False,'error':{'message':'fixture request rejected'}}});continue
        if text=='retry':
            for _ in range(2):
                send({'method':'error','params':{'threadId':tid,'turnId':turn_id,'willRetry':True,'error':{'message':'fixture transient connection'}}})
        if text=='delayed':
            threading.Thread(target=delayed_complete,args=(tid,turn_id,result,.15,.05),daemon=True).start();continue
        if text=='empty-delta':
            send({'method':'item/agentMessage/delta','params':{'threadId':tid,'turnId':turn_id,'itemId':'answer','delta':''}})
            threading.Thread(target=delayed_complete,args=(tid,turn_id,result,.15,0,True),daemon=True).start();continue
        if text=='turn-final-only':
            send({'method':'turn/completed','params':{'threadId':tid,'turn':{'id':turn_id,'status':'completed','items':[{'type':'agentMessage','id':'answer','text':result}]}}});continue
        complete(tid,turn_id,result,final_only=text=='final-only')
    elif method=='turn/interrupt':
        answer(request,{})
        state=active.get(params['turnId'])
        if state:state['cancelled'].set()
        if pending:
            tid,turn_id=pending;send({'method':'turn/completed','params':{'threadId':tid,'turn':{'id':turn_id,'status':'interrupted'}}});pending=None
    elif method=='thread/unsubscribe':
        for state in active.values():
            if state['threadId']==params['threadId']:state['cancelled'].set()
        answer(request,{'status':'unsubscribed'})
    elif request.get('id')=='server-approval':
        tid,turn_id=pending;complete(tid,turn_id,request.get('result',{}).get('decision','unexpected approval'));pending=None
    elif 'id' in request:send({'id':request['id'],'error':{'code':-32601,'message':'unknown method'}})
