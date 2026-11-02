"""One targeted physical experiment against an explicitly identified fixture."""
import ctypes as C
import json
import sys
from supporter.windows import u,INPUT,KEY

hwnd=int(sys.argv[1])
payload=json.loads(sys.stdin.read())['text']
if u.GetForegroundWindow()!=hwnd:raise RuntimeError('fixture lost foreground; no input sent')
if any(u.GetAsyncKeyState(v)&0x8000 for v in (0x10,0x11,0x12)):
    raise RuntimeError('physical modifier held; experiment skipped')
events=[]
for i,line in enumerate(payload.split('\n')):
    if i:
        # Enter is always enclosed by Shift down/up. Never a bare submit key.
        events.extend(INPUT(type=1,ki=KEY(vk=vk,flags=flags)) for vk,flags in [(0x10,0),(0x0D,0),(0x0D,2),(0x10,2)])
    data=line.encode('utf-16-le')
    for offset in range(0,len(data),2):
        unit=int.from_bytes(data[offset:offset+2],'little')
        events.extend(INPUT(type=1,ki=KEY(scan=unit,flags=flags)) for flags in (4,6))
array=(INPUT*len(events))(*events)
if u.GetForegroundWindow()!=hwnd:raise RuntimeError('fixture lost foreground; no input sent')
if u.SendInput(len(events),array,C.sizeof(INPUT))!=len(events):raise RuntimeError('fixture rejected input events')
