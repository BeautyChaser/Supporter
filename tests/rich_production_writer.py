"""Exercise production insert only against a verified local fixture handle."""
import json
import sys
from supporter.windows import u,insert
data=json.loads(sys.stdin.read())
if u.GetForegroundWindow()!=data['target']['hwnd']:
    raise RuntimeError('fixture lost foreground; physical write skipped')
insert(data['target'],data['text'],replace=True)
