"""Local runtime diagnostics. No account requests or clipboard/input actions."""
import argparse
import importlib.util
import json
import platform
import struct
import sys
from .paths import DATA_ROOT,RESOURCE_ROOT,VENDOR_ROOT,ensure_runtime,helper_path

def report():
    if str(VENDOR_ROOT) not in sys.path:sys.path.insert(0,str(VENDOR_ROOT))
    from .backend_plugins import load_plugins
    plugins,errors=load_plugins()
    helpers={name:bool(helper_path(name)) for name in ('caret-probe','paste-bridge')}
    vendor=importlib.util.find_spec('comtypes') is not None
    return {'protocolVersion':1,'python':platform.python_version(),'architecture':struct.calcsize('P')*8,
        'platform':sys.platform,'resources':str(RESOURCE_ROOT),'data':str(DATA_ROOT),'runtimeWritable':ensure_runtime().is_dir(),
        'comtypesAvailable':vendor,'helpers':helpers,'registeredBackends':[p.id for p in plugins],
        'pluginErrors':[{'plugin':name,'message':message} for name,message in errors],
        'ready':sys.platform=='win32' and vendor and all(helpers.values())}

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser();parser.add_argument('--no-backends',action='store_true');parser.parse_args()
    value=report();print(json.dumps(value,ensure_ascii=False),flush=True)
    return 0 if value['ready'] else 1

if __name__=='__main__':raise SystemExit(main())
