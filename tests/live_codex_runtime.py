"""Optional live benchmark. Calls the account-backed CLI; not a unit test."""
import argparse
import json
from pathlib import Path
import threading
import time
from supporter.backends import discover_one
from supporter.codex_runtime import CodexRuntime,TEXT_INSTRUCTIONS
from supporter.results import conversation_prompt,parse_response

parser=argparse.ArgumentParser();parser.add_argument('--runs',type=int,default=2);parser.add_argument('--timeout',type=float,default=55);parser.add_argument('--report',default='.runtime/codex-runtime-benchmark.json')
parser.add_argument('--reasoning',default='low');parser.add_argument('--production-prompt',action='store_true');parser.add_argument('--proxy',default='')
args=parser.parse_args()
backend=discover_one('codex')
if backend.error:raise RuntimeError(backend.error)
model=next((m for m in backend.models if m=='gpt-6-luna'),None)
if model is None:raise RuntimeError('Requested Luna model is not in the local CLI catalog')
runtime=CodexRuntime(backend.path,connection={'mode':'proxy','proxyUrl':args.proxy} if args.proxy else None)
report={'cliVersion':backend.version,'model':model,'reasoning':args.reasoning,'productionPrompt':args.production_prompt,'connection':'specified-proxy' if args.proxy else 'inherited','runs':[]}
def progress(message):print(message,flush=True)
try:
    report['warmSeconds']=runtime.warm(progress=progress)
    started=time.monotonic()
    result=runtime._rpc('thread/start',{'cwd':str(Path.cwd()),'ephemeral':True,'sandbox':'read-only','approvalPolicy':'never','model':model,'baseInstructions':TEXT_INSTRUCTIONS},timeout=30)
    report['probeThreadSeconds']=time.monotonic()-started
    report['inheritedReasoning']=result.get('reasoningEffort')
    runtime._rpc('thread/unsubscribe',{'threadId':result['thread']['id']},timeout=3)
    for i in range(args.runs):
        started=time.monotonic()
        try:
            prompt=conversation_prompt('询问 ChatGPT',[],'写一段查看gpu的命令',False,'bash') if args.production_prompt else 'Return ONLY the word READY. Do not use tools.'
            response=runtime.generate(model,prompt,threading.Event(),reasoning=args.reasoning,progress=progress,timeout=args.timeout)
            parsed=parse_response(response,request='写一段查看gpu的命令',environment='bash') if args.production_prompt else None
            report['runs'].append({'ok':bool(parsed) if parsed else response.strip()=='READY','candidateCount':len(parsed['candidates']) if parsed else None,**runtime.last_metrics})
        except Exception as error:
            report['runs'].append({'ok':False,'seconds':time.monotonic()-started,'error':str(error)})
        print(json.dumps(report['runs'][-1],ensure_ascii=False),flush=True)
except Exception as error:
    report['error']=str(error)
    report['startupDiagnostics']=list(runtime._stderr)[-8:]
finally:
    runtime.close()
    path=Path(args.report);path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
