"""Black-box embedded-runtime smoke with empty PATH and disposable userdata.

No installed CLI, user settings or account cache is used. The native helper's
self-test checks its loader without clipboard access.
An optional self-created native fixture permits scoped UIA enumeration only.
"""
import argparse
import hashlib
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
NO_CONSOLE=getattr(subprocess,'CREATE_NO_WINDOW',0)
CHECK=r'''
import json,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
resource=Path(os.environ['SUPPORTER_RESOURCE_ROOT']).resolve()
data=Path(os.environ['SUPPORTER_DATA_DIR']).resolve()
def within(path,root):
    try:Path(path).resolve().relative_to(root);return True
    except (ValueError,TypeError):return False
attempts=[];outside=[]
def forbid(event,path):
    if isinstance(path,int):return  # Existing pipe/stdio descriptors, not filesystem paths.
    if within(path,data):return
    (attempts if within(path,resource) else outside).append(event)
    raise PermissionError('distribution probe may only write isolated userdata')
def audit(event,args):
    if event=='open':
        path,mode,flags=args
        if flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):forbid(event,path)
    elif event in ('os.mkdir','os.remove','os.rmdir','os.chmod','os.truncate'):forbid(event,args[0])
    elif event in ('os.rename','os.replace'):
        forbid(event,args[0]);forbid(event,args[1])
sys.addaudithook(audit)
from supporter import paths,uia_native
import comtypes,comtypes.client
result={'executable':sys.executable,'version':sys.version.split()[0],
 'source':str(paths.SOURCE_ROOT),'resource':str(paths.RESOURCE_ROOT),'data':str(paths.DATA_ROOT),
 'runtime':str(paths.RUNTIME_ROOT),'helper':str(paths.helper_path('paste-bridge')),
 'comtypes':comtypes.__version__,'comtypesFile':comtypes.__file__,
 'uiaFile':uia_native.__file__,'genDirectory':comtypes.client.gen_dir,
 'wrapperFile':uia_native.U.__file__,'resourceWriteAttempts':attempts,'outsideUserdataWriteAttempts':outside,'path':sys.path}
if len(sys.argv)>1 and sys.argv[1]!='0':
    from supporter import windows
    owner=windows.W.DWORD()
    windows.u.GetWindowThreadProcessId(int(sys.argv[1]),windows.C.byref(owner))
    if owner.value!=int(sys.argv[2]):raise RuntimeError('native fixture HWND belongs to a different process')
    listing=uia_native.snapshot({'hwnd':int(sys.argv[1]),'locate_inputs':True})
    result['fixtureInputNames']=sorted(control['name'] for control in listing['controls'])
    bridged=windows.probe_caret({'hwnd':int(sys.argv[1]),'locate_inputs':True})
    if not isinstance(bridged,dict):raise RuntimeError('packaged windows.probe_caret did not return native metadata')
    result['bridgedInputNames']=sorted(control['name'] for control in bridged['controls'])
    result['probeExecutable']=str(Path(windows._probe.args[0]).resolve())
    result['probeImplementation']=windows._probe_path
    windows._probe.stdin.close();windows._probe.wait(timeout=3);windows._probe.stdout.close()
print(json.dumps(result,ensure_ascii=False))
'''

def check(condition,message):
    if not condition:raise AssertionError(message)

def snapshot(directory):
    return {str(path.relative_to(directory)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob('*') if path.is_file()}

def receive(inbox,events,kind,timeout=6):
    deadline=time.monotonic()+timeout
    while True:
        try:event=inbox.get(timeout=max(.01,deadline-time.monotonic()))
        except queue.Empty:raise AssertionError('missing service event '+kind)
        events.append(event)
        if event['type']==kind:return event
        if time.monotonic()>deadline:raise AssertionError('missing service event '+kind)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--python',required=True,type=Path)
    parser.add_argument('--resources',required=True,type=Path);parser.add_argument('--native-fixture',type=Path)
    parser.add_argument('--report',type=Path,default=ROOT/'.runtime/packaged-smoke-report.json');args=parser.parse_args()
    interpreter=args.python.resolve();resources=args.resources.resolve()
    report={'passed':False,'emptyPath':True,'isolatedUserdata':True,'noKeyboardMouseOrTextInput':True}
    check(interpreter.is_file(),'embedded interpreter does not exist');check(resources.is_dir(),'resource directory does not exist')
    check(resources!=ROOT,'use staged distribution resources, never the development workspace')
    before=snapshot(resources);fixture=None;worker=None
    with tempfile.TemporaryDirectory(prefix='packaged-smoke-空间-',dir=ROOT/'.runtime') as directory:
        data=Path(directory);plugins=data/'empty-plugins';plugins.mkdir()
        env={key:value for key,value in os.environ.items() if not key.startswith('SUPPORTER_') and key not in ('PYTHONHOME','PYTHONPATH','VIRTUAL_ENV')}
        env.update(PATH='',SUPPORTER_RESOURCE_ROOT=str(resources),SUPPORTER_DATA_DIR=str(data),
            SUPPORTER_BACKEND_DIR=str(plugins),SUPPORTER_BACKEND_POLL_SECONDS='0',PYTHONIOENCODING='utf-8',
            PYTHONDONTWRITEBYTECODE='1',HOME=str(data/'home'),USERPROFILE=str(data/'home'),
            APPDATA=str(data/'roaming'),LOCALAPPDATA=str(data/'local'),TEMP=str(data/'temp'),TMP=str(data/'temp'))
        for name in ('home','roaming','local','temp'):(data/name).mkdir()
        try:
            hwnd=0
            if args.native_fixture:
                fixture=subprocess.Popen([str(args.native_fixture.resolve())],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                    text=True,encoding='utf-8',creationflags=NO_CONSOLE)
                ready=queue.Queue();threading.Thread(target=lambda:ready.put(fixture.stdout.readline()),daemon=True).start()
                identity=json.loads(ready.get(timeout=5));check(identity['pid']==fixture.pid,'native fixture process identity')
                hwnd=identity['hwnd']
            probe=subprocess.run([str(interpreter),'-I','-B','-c',CHECK,str(hwnd),str(fixture.pid if fixture else 0)],cwd=data,env=env,capture_output=True,
                text=True,encoding='utf-8',timeout=15,creationflags=NO_CONSOLE)
            check(probe.returncode==0,'embedded UIA import failed: '+probe.stderr[-1500:])
            runtime=json.loads(probe.stdout);report['runtime']=runtime
            check(Path(runtime['executable']).resolve()==interpreter,'the embedded interpreter must be used directly')
            check(runtime['version']=='3.14.8','expected bundled Python 3.14.8')
            check(runtime['comtypes']=='1.4.17','expected bundled comtypes 1.4.17')
            check(Path(runtime['uiaFile']).resolve().is_relative_to(resources),'supporter cannot load from host source')
            check(Path(runtime['comtypesFile']).resolve().is_relative_to(resources),'comtypes cannot load from host site-packages')
            check(Path(runtime['genDirectory']).resolve().is_relative_to(data),'UIA codegen must use isolated userdata')
            check(Path(runtime['wrapperFile']).resolve().is_relative_to(data),'UIA wrapper must be generated in userdata')
            check(not runtime['resourceWriteAttempts'],'runtime attempted writes into immutable resources')
            check(not runtime['outsideUserdataWriteAttempts'],'runtime attempted writes outside isolated userdata')
            if hwnd:
                expected=['Fixture editable first','Fixture editable multiline']
                check(runtime['fixtureInputNames']==expected and runtime['bridgedInputNames']==expected,'embedded UIA native fixture filters')
                check(Path(runtime['probeExecutable']).resolve()==interpreter,'UIA child must reuse embedded interpreter')
                check(runtime['probeImplementation']=='native-uia','UIA must use bundled comtypes implementation')
            helper=Path(runtime['helper']).resolve();check(helper.is_relative_to(resources),'native helper must launch from resources')
            native=subprocess.run([str(helper),'--self-test'],capture_output=True,text=True,encoding='utf-8',timeout=5,env=env,creationflags=NO_CONSOLE)
            check(native.returncode==0,'native .NET helper loader failed')
            native_report=json.loads(native.stdout)
            check(native_report.get('ready') is True and native_report.get('clipboardUntouched') is True,'native helper self-test must avoid clipboard writes')
            report['nativeHelperStartedWithoutClipboardWrite']=True
            diagnostics=subprocess.run([str(interpreter),'-I','-B','-m','supporter.diagnostics','--no-backends'],
                cwd=data,env=env,capture_output=True,text=True,encoding='utf-8',timeout=10,creationflags=NO_CONSOLE)
            check(diagnostics.returncode==0,'packaged diagnostics failed: '+diagnostics.stderr[-1200:])
            diagnostic_report=json.loads(diagnostics.stdout)
            check(diagnostic_report.get('ready') is True and diagnostic_report.get('architecture')==64,'diagnostics must report a ready x64 runtime')
            check(Path(diagnostic_report['data']).resolve()==data,'diagnostics must use isolated userdata')
            report['diagnosticsAvailable']=True
            inbox=queue.Queue();events=[]
            worker=subprocess.Popen([str(interpreter),'-I','-B','-u','-m','supporter.service'],cwd=data,env=env,
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=NO_CONSOLE)
            def read():
                for line in worker.stdout:inbox.put(json.loads(line))
            threading.Thread(target=read,daemon=True).start()
            receive(inbox,events,'ready');inventory=receive(inbox,events,'inventory')
            check(inventory['backends']==[],'empty isolated plugin catalog cannot invoke installed CLIs')
            settings={'backend':'','environment':'markdown','appearance':{'theme':'light'},'distributionFixture':True}
            worker.stdin.write(json.dumps({'type':'settings','settings':settings,'request_id':'distribution-save'})+'\n');worker.stdin.flush()
            check(receive(inbox,events,'settings-persisted')['request_id']=='distribution-save','settings save receipt')
            check(json.loads((data/'settings.json').read_text(encoding='utf-8'))==settings,'settings must be saved under userdata')
            worker.stdin.write('{"type":"quit"}\n');worker.stdin.flush();check(worker.wait(timeout=5)==0,'service shutdown failed')
            report['emptyBackendFirstRun']=True;report['settingsSavedToUserdata']=True
            check(snapshot(resources)==before,'distribution resources changed during smoke')
            report['resourcesUnchanged']=True;report['passed']=True
        except Exception as error:
            report['error']=str(error)
            if worker is not None and worker.poll() is not None:
                report['serviceExitCode']=worker.returncode
                report['serviceError']=worker.stderr.read()[-1500:]
        finally:
            for child in (worker,fixture):
                if child is None:continue
                if child.poll() is None:child.terminate()
                child.wait(timeout=4)
                for stream in (child.stdin,child.stdout,child.stderr):
                    if stream is not None:
                        try:stream.close()
                        except OSError:pass
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(args.report)},ensure_ascii=False))
    return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
