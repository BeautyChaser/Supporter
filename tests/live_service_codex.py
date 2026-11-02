"""Optional authenticated smoke test of the production service, with no UI input.

Uses a temporary copy of the project's saved settings and a fixed local source.
Never accepts candidates, writes into an app, or changes global Codex settings.
"""
import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parent.parent

def worker(directory):
    from supporter import service
    from supporter.backends import discover_one
    service.ROOT=Path(directory)
    service.discover=lambda:[discover_one('codex')]
    service.windows.capture=lambda:{'scope':'reference','context':'询问 ChatGPT','terminal':False,'source':'isolated-fixture','title':'Supporter fixed test source'}
    service.windows.restore=lambda target:None
    def no_insert(*args,**kwargs):raise AssertionError('Live service test must never insert text')
    service.windows.insert=no_insert
    service.main()

def run(report_path):
    settings=json.loads((ROOT/'settings.json').read_text(encoding='utf-8'))
    model='gpt-6-luna';effort=settings.get('reasoning',{}).get('codex|'+model,'default')
    report={'model':model,'reasoning':effort,'connection':settings.get('codexConnection',{}).get('mode','inherit'),'productionService':True,'noExternalInput':True,'passed':False,'progress':[]}
    with tempfile.TemporaryDirectory(prefix='live-service-',dir=ROOT/'.runtime') as temporary:
        (Path(temporary)/'settings.json').write_text(json.dumps(settings,ensure_ascii=False),encoding='utf-8')
        child=subprocess.Popen([sys.executable,'-u','-m','tests.live_service_codex','--worker',temporary],cwd=ROOT,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',
            env={**os.environ,'PYTHONIOENCODING':'utf-8'},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        inbox=queue.Queue()
        def reader():
            for line in child.stdout:
                try:inbox.put(json.loads(line))
                except ValueError:pass
        threading.Thread(target=reader,daemon=True).start()
        def send(**data):child.stdin.write(json.dumps(data,ensure_ascii=False)+'\n');child.stdin.flush()
        started=None;first=None;deadline=time.monotonic()+50
        try:
            while time.monotonic()<deadline:
                event=inbox.get(timeout=max(.1,deadline-time.monotonic()))
                if event['type']=='inventory':send(type='capture',force=True,request_id='live-capture')
                elif event['type']=='wake':
                    started=time.monotonic();send(type='generate',client_request_id='live-gpu',backend='codex',model=model,reasoning=effort,request='写一段查看gpu的命令',terminal=False,environment='bash',history=[])
                elif event['type']=='progress':
                    elapsed=time.monotonic()-started if started else 0
                    report['progress'].append({'seconds':round(elapsed,3),'message':event['message']});print(event['message'],flush=True)
                    if first is None and event['message']=='Codex 开始返回文本':first=elapsed
                elif event['type']=='result':
                    report.update(totalSeconds=time.monotonic()-started,firstTextSeconds=first,candidateCount=len(event['candidates']),kind=event['kind'])
                    report['passed']=event.get('client_request_id')=='live-gpu' and event['kind']=='commands' and bool(event['candidates']) and any('本次推理：低' in p['message'] for p in report['progress']) and any('代理 127.0.0.1:7890' in p['message'] for p in report['progress'])
                    break
                elif event['type']=='error':raise RuntimeError(event['message'])
            else:raise TimeoutError('Production service smoke test exceeded 50 seconds')
        except Exception as error:report['error']=str(error)
        finally:
            if child.poll() is None:
                try:send(type='quit');child.wait(timeout=6)
                except (OSError,subprocess.TimeoutExpired):child.kill();child.wait(timeout=3)
            for stream in (child.stdin,child.stdout,child.stderr):stream.close()
    Path(report_path).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return 0 if report['passed'] else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker');parser.add_argument('--report',default=str(ROOT/'.runtime/luna-live-service.json'))
    args=parser.parse_args()
    if args.worker:worker(args.worker)
    else:raise SystemExit(run(args.report))
