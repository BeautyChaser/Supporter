"""Optional paid/account-backed smoke test; never run during unit tests."""
import threading
from supporter.backends import discover_one, generate, conversation_prompt, parse_response
b=discover_one('codex')
model=next(m for m in b.models if b.reasoning.get(m))
effort=b.reasoning[model][0]
print(b.version,model,effort,flush=True)
cancel=threading.Event()
timer=threading.Timer(90,cancel.set);timer.daemon=True;timer.start()
response=generate(b,model,conversation_prompt('hello',[],'Translate the original into Chinese.',False),cancel,reasoning=effort,on_progress=lambda m:print(m,flush=True))
parsed=parse_response(response)
print('reply/result valid:',bool(parsed['reply']),bool(parsed['result']),flush=True)
