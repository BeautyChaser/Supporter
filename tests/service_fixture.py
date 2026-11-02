"""Isolated local CLI/window substitutes for the service integration test."""
import json
import sys
import time
from pathlib import Path
from supporter import service
from supporter.backends import Backend

service.ROOT=Path(sys.argv[1])
service.discover=lambda:[Backend('codex','fixture')]
def fake_generate(backend,model,prompt,cancel,*args,**kwargs):
    if model.startswith('test-'):
        service.emit('test-generation-started',model=model)
        if model.startswith('test-held-'):
            release=service.ROOT/(model+'.release')
            deadline=time.monotonic()+3
            while not release.exists() and time.monotonic()<deadline:time.sleep(.005)
        service.emit('test-generation-finished',model=model,cancelled=cancel.is_set())
        if model.endswith('-error'):raise RuntimeError('deliberate fixture error')
        return json.dumps({'reply':'fixture reply','kind':'commands','candidates':[
            {'label':model,'detail':'isolated fixture','text':'printf '+model}]})
    return json.dumps({'reply':'不同硬件适用不同命令。','kind':'commands','candidates':[
        {'label':'NVIDIA','detail':'已安装驱动','text':'nvidia-smi'},
        {'label':'AMD','detail':'ROCm 环境','text':'rocm-smi'}]})
service.generate=fake_generate
captures=iter([{'hwnd':910001,'title':'Isolated locate fixture','scope':'reference','context':'只读参考','terminal':False},
               {'hwnd':910001,'title':'Isolated locate fixture','scope':'editor','context':'','terminal':False}])
service.windows.capture=lambda:next(captures)
service.windows.restore=lambda target:None
service.windows.insert=lambda target,text,replace:service.emit('test-insert',text=text,scope=target['scope'],replace=replace)

def location_mode():
    try:return (service.ROOT/'locate-mode.txt').read_text(encoding='utf-8')
    except FileNotFoundError:return ''

def list_inputs(target):
    service.emit('test-list-inputs',hwnd=target['hwnd'])
    mode=location_mode()
    if mode=='error':raise RuntimeError('deliberate fixture locate error')
    return {'controls':[] if mode=='empty' else [
        {'id':'fixture-first','name':'Fixture first editor','class':'fixture-edit','bounds':[20,40,200,30],'focused':False,'terminal':False},
        {'id':'fixture-second','name':'Fixture second editor','class':'fixture-edit','bounds':[20,90,200,60],'focused':False,'terminal':False}],
        'limited':mode=='limited'}

def focus_input(target,identifier):
    service.emit('test-focus-input',hwnd=target['hwnd'],identifier=identifier)
    if location_mode()=='focus-error':raise RuntimeError('deliberate fixture focus error')
    return {**target,'scope':'editor','context':'fixture newly focused','editor_id':identifier}

service.windows.list_inputs=list_inputs
service.windows.focus_input=focus_input
service.main()
