"""Optional live CLI smoke test; uses the user's selected backend/model."""
import json
import threading
from supporter.backends import ROOT, DEFAULT, discover_one, generate
from supporter.results import conversation_prompt,parse_response,accepted_text
try:settings=json.loads((ROOT/'settings.json').read_text(encoding='utf-8'))
except (ValueError,OSError):settings={}
name=settings.get('backend','opencode')
backend=discover_one(name)
if backend.error:raise RuntimeError(backend.error)
model=settings.get('models',{}).get(name,DEFAULT)
effort=settings.get('reasoning',{}).get(name+'|'+model,'default')
cancel=threading.Event();timer=threading.Timer(65,cancel.set);timer.daemon=True;timer.start()
request='我要 Linux 中查看 GPU 状态的命令，请区分 NVIDIA、AMD、Intel，不要猜我的硬件。'
print(name,model,effort,flush=True)
raw=generate(backend,model,conversation_prompt('',[],request,False),cancel,reasoning=effort,on_progress=lambda m:print(m,flush=True))
response=parse_response(raw,request=request)
for i in range(len(response['candidates'])):accepted_text(response,i,terminal=True)
print(json.dumps({'kind':response['kind'],'choices':len(response['candidates']),'allCommandsValidated':True},ensure_ascii=False),flush=True)
