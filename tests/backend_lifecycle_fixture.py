"""Isolated backend inventory service fixture: no installed CLI is executed."""
import copy
import json
import os
from pathlib import Path
import sys
import threading
import time

os.environ['SUPPORTER_BACKEND_POLL_SECONDS']=sys.argv[2] if len(sys.argv)>2 else '0.1'
from supporter import service
from supporter.backends import Backend,DEFAULT
from supporter import codex_runtime

service.ROOT=Path(sys.argv[1]);state_file=service.ROOT/'backend-state.json'
guard=threading.Lock();scan_count=0;scan_active=0;verified={}

def state():return json.loads(state_file.read_text(encoding='utf-8'))

def key(row):return (row['name'],row.get('revision','rev1'),row.get('version','fixture1'))

def backend(row):
    return Backend(row['name'],path='isolated-fixture/'+row['name'],version=row.get('version','fixture1'),
        models=[DEFAULT,*row.get('models',['model-'+row['name']])],error=row.get('error',''),
        adapter='generic',plugin_revision=row.get('revision','rev1'),display_name=row['name'],
        status='unavailable' if row.get('error') else 'available')

def presence():
    snapshot=state();out=[]
    with guard:
        for row in snapshot['backends']:
            cached=verified.get(key(row))
            if cached:out.append(copy.deepcopy(cached))
            else:
                pending=backend(row);pending.status='checking';pending.error='fixture checking';out.append(pending)
    return out

def discover(*,force=False):
    global scan_count,scan_active
    snapshot=state()
    with guard:
        scan_count+=1;number=scan_count;scan_active+=1;active=scan_active
    service.emit('test-scan-started',number=number,active=active,force=force)
    try:
        if snapshot.get('holdScan'):
            release=service.ROOT/('scan-'+str(number)+'.release');deadline=time.monotonic()+5
            while not release.exists() and time.monotonic()<deadline:time.sleep(.005)
        if snapshot.get('scanError'):raise RuntimeError('deliberate inventory fixture error')
        out=[backend(row) for row in snapshot['backends']]
        with guard:
            for row,item in zip(snapshot['backends'],out):verified[key(row)]=copy.deepcopy(item)
        service.emit('test-scan-finished',number=number)
        return out
    finally:
        with guard:scan_active-=1

def invalidate():service.emit('test-invalidated')

class FixtureProcess:
    def __init__(self,label):self.label=label;self.stopped=False
    def poll(self):return 0 if self.stopped else None

def generate(b,model,prompt,cancel,process_callback=lambda p:None,*args,**kwargs):
    process=FixtureProcess(model);process_callback(process)
    service.emit('test-generation-started',model=model,backend=b.name,historyPresent='fixture-history-seed' in prompt)
    if model.startswith('held-'):
        release=service.ROOT/(model+'.release');deadline=time.monotonic()+5
        while not release.exists() and not cancel.is_set() and time.monotonic()<deadline:time.sleep(.005)
    service.emit('test-generation-finished',model=model,cancelled=cancel.is_set())
    process.stopped=True
    if cancel.is_set():raise RuntimeError('fixture generation cancelled')
    return json.dumps({'reply':'fixture reply','kind':'text','result':'fixture result '+model})

def stop(process):
    service.emit('test-process-stopped',hasProcess=process is not None,label=getattr(process,'label',None))
    if process is not None:process.stopped=True

service.discover=discover;service.presence=presence;service.invalidate_discovery=invalidate
service.generate=generate;service.stop=stop
service.stop_detection=lambda:service.emit('test-detection-stopped')
service.windows.capture=lambda:{'hwnd':920001,'scope':'reference','context':'fixture original','terminal':False,'title':'Isolated lifecycle fixture'}
service.windows.restore=lambda target:None
service.windows.insert=lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('lifecycle tests must not type'))
codex_runtime.close_all=lambda:service.emit('test-runtimes-closed')
service.main()
