"""Read-only, bounded input metadata for a specifically requested app/window."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
from .uia_native import snapshot

parser=argparse.ArgumentParser();parser.add_argument('--pid',type=int,action='append',default=[])
parser.add_argument('--terminal',action='store_true');args=parser.parse_args()
u=C.WinDLL('user32');u.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
u.GetClassNameW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
records=[]
@C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
def visit(hwnd,param):
    pid=W.DWORD();u.GetWindowThreadProcessId(hwnd,C.byref(pid))
    cls=C.create_unicode_buffer(256);u.GetClassNameW(hwnd,cls,256)
    if u.IsWindowVisible(hwnd) and (pid.value in args.pid or (args.terminal and any(t in cls.value.lower() for t in ('cascadia','consolewindow')))):
        records.append({'hwnd':hwnd,'class':cls.value,'inputs':snapshot({'hwnd':hwnd,'inspect':True})})
    return True
u.EnumWindows(visit,0)
print(json.dumps(records,ensure_ascii=False,indent=2))
