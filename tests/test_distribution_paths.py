"""Distribution path tests using isolated, disposable resources and userdata."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
PROBE=r'''
import json,os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1]);sys.dont_write_bytecode=True
resource=Path(os.environ['SUPPORTER_RESOURCE_ROOT']).resolve()
def within(path):
    try:Path(path).resolve().relative_to(resource);return True
    except (ValueError,TypeError):return False
def audit(event,args):
    if event=='open':
        path,mode,flags=args
        writing=bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if writing and within(path):raise PermissionError('resource tree is immutable')
    elif event in ('os.mkdir','os.remove','os.rmdir','os.chmod','os.truncate'):
        if within(args[0]):raise PermissionError('resource tree is immutable')
    elif event in ('os.rename','os.replace'):
        if within(args[0]) or within(args[1]):raise PermissionError('resource tree is immutable')
sys.addaudithook(audit)
from supporter import paths
before=paths.RUNTIME_ROOT.exists()
if sys.argv[2]=='ensure':paths.ensure_runtime()
def show(value):return str(value) if value is not None else None
print(json.dumps({'source':show(paths.SOURCE_ROOT),'resource':show(paths.RESOURCE_ROOT),
 'data':show(paths.DATA_ROOT),'runtime':show(paths.RUNTIME_ROOT),'vendor':show(paths.VENDOR_ROOT),
 'native':show(paths.NATIVE_ROOT),'runtimeBefore':before,'runtimeAfter':paths.RUNTIME_ROOT.exists(),
 'paste':show(paths.helper_path('paste-bridge')),'caret':show(paths.helper_path('caret-probe'))}))
'''

class DistributionPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='distribution-paths-',dir=ROOT/'.runtime')
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.resources=self.root/'不可写 安装目录';self.resources.mkdir()
        self.data=self.root/'用户数据 空格 Ω'
    def probe(self,ensure=False):
        env={key:value for key,value in os.environ.items() if not key.startswith('SUPPORTER_')}
        env.update(SUPPORTER_RESOURCE_ROOT=str(self.resources),SUPPORTER_DATA_DIR=str(self.data),PYTHONIOENCODING='utf-8')
        result=subprocess.run([sys.executable,'-I','-B','-c',PROBE,str(ROOT),'ensure' if ensure else 'inspect'],
            cwd=self.root,env=env,text=True,encoding='utf-8',capture_output=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)
    def test_source_resources_and_userdata_are_distinct_and_unicode_safe(self):
        result=self.probe()
        self.assertEqual(Path(result['source']),ROOT)
        self.assertEqual(Path(result['resource']),self.resources)
        self.assertEqual(Path(result['data']),self.data)
        self.assertEqual(Path(result['runtime']),self.data/'.runtime')
        self.assertEqual(Path(result['vendor']),self.resources/'.vendor')
        self.assertEqual(Path(result['native']),self.resources/'native')
        self.assertFalse(result['runtimeAfter'],'merely importing paths should not create files')
        self.assertFalse(self.data.exists())
    def test_runtime_creation_never_writes_immutable_resources(self):
        result=self.probe(ensure=True)
        self.assertFalse(result['runtimeBefore']);self.assertTrue(result['runtimeAfter'])
        self.assertEqual(list(self.resources.iterdir()),[])
        self.assertEqual([path.name for path in self.data.iterdir()],['.runtime'])
    def test_packaged_native_helpers_win_over_build_machine_manifests(self):
        native=self.resources/'native';native.mkdir()
        paste=native/'paste-bridge.exe';paste.write_bytes(b'path fixture, never executed')
        caret=native/'caret-probe.exe';caret.write_bytes(b'path fixture, never executed')
        runtime=self.data/'.runtime';runtime.mkdir(parents=True)
        other=self.root/'old build helper.exe';other.write_bytes(b'not executed')
        for name in ('paste-path.txt','caret-path.txt'):(runtime/name).write_text(str(other),encoding='utf-8-sig')
        result=self.probe();self.assertEqual(Path(result['paste']),paste);self.assertEqual(Path(result['caret']),caret)
    def test_development_manifest_fallback_accepts_bom_spaces_and_unicode(self):
        runtime=self.data/'.runtime';runtime.mkdir(parents=True)
        helper=self.root/'本地 bridge Ω.exe';helper.write_bytes(b'not executed')
        (runtime/'paste-path.txt').write_text(str(helper)+'\n',encoding='utf-8-sig')
        self.assertEqual(Path(self.probe()['paste']),helper)
    def test_missing_manifest_target_uses_userdata_fallback_not_resource_runtime(self):
        runtime=self.data/'.runtime';runtime.mkdir(parents=True)
        (runtime/'paste-path.txt').write_text(str(self.root/'missing.exe'),encoding='utf-8')
        expected=runtime/'paste-bridge.exe';expected.write_bytes(b'not executed')
        old=self.resources/'.runtime';old.mkdir()
        (old/'caret-path.txt').write_text(str(expected),encoding='utf-8')
        result=self.probe();self.assertEqual(Path(result['paste']),expected);self.assertIsNone(result['caret'])
    def test_missing_helpers_report_none_without_creating_runtime(self):
        result=self.probe();self.assertIsNone(result['paste']);self.assertIsNone(result['caret']);self.assertFalse(self.data.exists())

if __name__=='__main__':unittest.main()
