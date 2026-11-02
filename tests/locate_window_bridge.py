"""Fixture-only production locate bridge. Never sends keyboard/text input."""
import ctypes as C
from ctypes import wintypes as W
import json
import sys
from supporter import windows

def main():
    data=json.loads(sys.stdin.read());hwnd=data['hwnd'];pid=data['pid']
    owner=W.DWORD();windows.u.GetWindowThreadProcessId(hwnd,C.byref(owner))
    if owner.value!=pid or not windows.u.IsWindow(hwnd):raise RuntimeError('fixture window identity mismatch')
    def forbidden(*args):raise AssertionError('locate must never send input')
    windows.u.SendInput=forbidden
    target={'hwnd':hwnd}
    if data['action']=='list':return windows.list_inputs(target)
    if data['action']=='setup':
        windows.restore(target)
        foreground=windows.u.GetForegroundWindow()
        return {'foregroundVerified':foreground==hwnd,'foregroundUnavailable':not bool(foreground)}
    if windows.u.GetForegroundWindow()!=hwnd:return {'skipped':'fixture is not foreground','foregroundUnavailable':not bool(windows.u.GetForegroundWindow())}
    captured=windows.focus_input(target,data['id'])
    if captured['hwnd']!=hwnd:raise RuntimeError('fixture lost foreground')
    return {'hwnd':captured['hwnd'],'scope':captured['scope'],'editorId':captured['editor_id'],
            'unchanged':captured.get('context')==data.get('expected'),'terminal':captured['terminal']}

if __name__=='__main__':
    sys.stdin.reconfigure(encoding='utf-8');sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(main(),ensure_ascii=False))
