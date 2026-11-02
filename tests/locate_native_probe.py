"""Real UIA locate/SetFocus regression, confined to our own native form.

Launch only the compiled LocateEditorFixture. Never sends keys, text or mouse
input, and skips focus checks if another window becomes foreground.
"""
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import queue
import subprocess
import threading
import time

from supporter import windows
from supporter import uia_native as native

ROOT=Path(__file__).resolve().parent.parent
REPORT=ROOT/'.runtime/locate-native-test.json'

def check(condition,message):
    if not condition:raise AssertionError(message)

def owns(hwnd,pid):
    actual=W.DWORD();windows.u.GetWindowThreadProcessId(hwnd,C.byref(actual))
    return actual.value==pid and bool(windows.u.IsWindow(hwnd))

def main():
    report={'passed':False,'noKeyboardMouseOrTextInput':True,'nativeFixture':True}
    child=None;original_send=windows.u.SendInput
    def forbidden_input(*args):raise AssertionError('locate path must never send input')
    windows.u.SendInput=forbidden_input
    try:
        executable=Path((ROOT/'.runtime/locate-fixture-path.txt').read_text(encoding='utf-8-sig').strip()).resolve()
        check(executable.parent==ROOT/'.runtime' and executable.name.startswith('locate-editor-fixture-'),'only our own fixture executable may launch')
        child=subprocess.Popen([str(executable)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
        ready=queue.Queue()
        def read_ready():ready.put(child.stdout.readline())
        threading.Thread(target=read_ready,daemon=True).start()
        identity=json.loads(ready.get(timeout=5));hwnd=identity['hwnd'];pid=identity['pid'];decoy=identity['decoyHwnd']
        check(pid==child.pid and owns(hwnd,pid) and owns(decoy,pid),'fixture HWND/process identity verified')
        target={'hwnd':hwnd,'title':identity['title']}
        # One explicit setup attempt to foreground our verified fixture. Never
        # retry if the user switches away during the actual focus checks.
        windows.restore(target);report['focusSetupAttempted']=True
        listing=windows.list_inputs(target);controls=listing['controls']
        expected={'Fixture editable first','Fixture editable multiline'}
        names={control['name'] for control in controls}
        report['listedNames']=sorted(names);report['listedControls']=controls;report['limited']=listing['limited']
        check(not listing['limited'],'small fixture should be complete')
        check(len({control['id'] for control in controls})==len(controls),'runtime ids are unique')
        check('fixture sentinel' not in json.dumps(listing),'listing must not contain fixture text values')
        for control in controls:
            check(set(control)=={'id','name','class','bounds','focused','terminal'},'listing exposes metadata fields only')
        # Inspect known fixture controls only. Do not read their text or values.
        root=native.automation.ElementFromHandle(hwnd)
        report['windowBounds']=native.bounds(root)
        nodes=root.FindAll(native.U.TreeScope_Subtree,native.automation.CreateTrueCondition())
        evidence={}
        for index in range(nodes.Length):
            node=nodes.GetElement(index);name=native.prop(node,'CurrentName','') or ''
            if not name.startswith('Fixture '):continue
            value=native.pattern(node,native.U.UIA_ValuePatternId,native.U.IUIAutomationValuePattern)
            evidence[name]={'password':bool(native.prop(node,'CurrentIsPassword',False)),
                'enabled':bool(native.prop(node,'CurrentIsEnabled',False)),
                'offscreen':bool(native.prop(node,'CurrentIsOffscreen',True)),
                'focusable':bool(native.prop(node,'CurrentIsKeyboardFocusable',False)),
                'readOnly':bool(value.CurrentIsReadOnly) if value else None,
                'bounds':native.bounds(node),'listed':name in names}
        report['controlFlags']=evidence
        check(names==expected,'only visible enabled nonpassword writable editors should be listed')
        check(evidence['Fixture password']['password'],'fixture password must expose real password metadata')
        check(evidence['Fixture readonly']['readOnly'],'fixture readonly must expose actual ValuePattern readonly')
        check(not evidence['Fixture disabled']['enabled'],'fixture disabled must expose disabled metadata')
        # A second real top-level window must remain outside the original list.
        other=windows.list_inputs({'hwnd':decoy})['controls']
        check(len(other)==1 and other[0]['name']=='Fixture other window','decoy editor is independently discoverable')
        report['crossWindowExcluded']=other[0]['id'] not in {control['id'] for control in controls}
        check(report['crossWindowExcluded'],'original hwnd list cannot include a different top-level window')
        foreground=windows.u.GetForegroundWindow()
        if foreground!=hwnd:
            report['focusSkipped']='fixture is not foreground; did not restore or change focus'
        else:
            before=native.metadata(native.automation.GetFocusedElement())
            rejected=False
            try:windows.focus_input(target,other[0]['id'])
            except RuntimeError:rejected=True
            check(rejected,'cross-window runtime id must be rejected')
            after=native.metadata(native.automation.GetFocusedElement())
            check(before['name']==after['name'],'rejected foreign id must leave current control focused')
            report['crossWindowSelectionRejected']=True
            if windows.u.GetForegroundWindow()!=hwnd:
                report['focusSkipped']='fixture lost foreground; did not attempt another focus'
            else:
                chosen=next(control for control in controls if control['name']=='Fixture editable multiline')
                captured=windows.focus_input(target,chosen['id'])
                focused=native.metadata(native.automation.GetFocusedElement())
                check(owns(captured['hwnd'],pid) and captured['hwnd']==hwnd,'focus capture remains in fixture window')
                check(focused['name']==chosen['name'] and focused['focused'],'requested real control has keyboard focus')
                check(captured['scope']=='editor','focused control recaptured as editable target')
                check(captured['context']=='fixture sentinel editable-multiline','SetFocus must not change editor text')
                report['focusSelection']={'passed':True,'name':focused['name'],'scope':captured['scope'],'textUnchanged':True}
        report['metadataPassed']=True
        report['passed']=bool(report.get('focusSelection',{}).get('passed'))
        report['status']='passed' if report['passed'] else 'skipped-focus'
    except Exception as error:
        report['error']=str(error)
    finally:
        windows.u.SendInput=original_send
        if child is not None:
            if child.poll() is None:child.terminate()
            child.wait(timeout=4)
            for stream in (child.stdout,child.stderr):
                if stream:stream.close()
        REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report['passed'] else 77 if report.get('focusSkipped') else 1

if __name__=='__main__':raise SystemExit(main())
