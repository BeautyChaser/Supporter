"""Installed path isolation without launching Electron, CLI models, or UI input."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent


class DistributionPathsTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='distribution-python-',dir=ROOT/'.runtime')
        self.root=Path(self.temporary.name);self.resources=self.root/'Program Files spaces'/'resources'/'supporter'
        self.data=self.root/'User profile 中文'/'Supporter';self.resources.mkdir(parents=True)
        self.environment={**os.environ,'SUPPORTER_RESOURCE_ROOT':str(self.resources),'SUPPORTER_DATA_DIR':str(self.data),
            'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8'}

    def tearDown(self):self.temporary.cleanup()

    def run_probe(self,code):
        process=subprocess.run([sys.executable,'-B','-c',code],cwd=ROOT,env=self.environment,capture_output=True,
            text=True,encoding='utf-8',timeout=10,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.assertEqual(process.returncode,0,process.stderr)
        return json.loads(process.stdout)

    def test_python_modules_share_explicit_data_root_and_keep_resources_immutable(self):
        before={str(file.relative_to(self.resources)):file.read_bytes() for file in self.resources.rglob('*') if file.is_file()}
        result=self.run_probe("from supporter import paths,backends,backend_plugins,codex_runtime;import json;print(json.dumps({'data':str(paths.DATA_ROOT),'resources':str(paths.RESOURCE_ROOT),'runtime':str(paths.ensure_runtime()),'vendor':str(paths.VENDOR_ROOT),'native':str(paths.NATIVE_ROOT),'roots':[str(m.ROOT) for m in [backends,backend_plugins,codex_runtime]]}))")
        self.assertEqual(Path(result['data']),self.data);self.assertEqual(Path(result['resources']),self.resources)
        self.assertEqual(Path(result['runtime']),self.data/'.runtime');self.assertTrue((self.data/'.runtime').is_dir())
        self.assertEqual(Path(result['vendor']),self.resources/'.vendor');self.assertEqual(Path(result['native']),self.resources/'native')
        self.assertEqual([Path(path) for path in result['roots']],[self.data]*3)
        after={str(file.relative_to(self.resources)):file.read_bytes() for file in self.resources.rglob('*') if file.is_file()}
        self.assertEqual(after,before)

    def test_bundled_helpers_take_precedence_over_stale_developer_manifests(self):
        native=self.resources/'native';native.mkdir();runtime=self.data/'.runtime';runtime.mkdir(parents=True)
        poison=self.root/'old developer path.exe';poison.touch()
        for name,manifest in [('caret-probe','caret-path.txt'),('paste-bridge','paste-path.txt')]:
            (native/(name+'.exe')).touch();(runtime/manifest).write_text(str(poison),encoding='utf-8-sig')
        result=self.run_probe("from supporter.paths import helper_path;import json;print(json.dumps({name:str(helper_path(name)) for name in ['caret-probe','paste-bridge']}))")
        self.assertEqual(Path(result['caret-probe']),native/'caret-probe.exe');self.assertEqual(Path(result['paste-bridge']),native/'paste-bridge.exe')

    def test_development_manifest_bom_missing_target_and_runtime_fallback(self):
        runtime=self.data/'.runtime';runtime.mkdir(parents=True)
        custom=self.root/'helper with spaces.exe';custom.touch()
        (runtime/'caret-path.txt').write_text(str(custom),encoding='utf-8-sig')
        (runtime/'paste-path.txt').write_text(str(self.root/'missing.exe'),encoding='utf-8-sig');(runtime/'paste-bridge.exe').touch()
        result=self.run_probe("from supporter.paths import helper_path;import json;print(json.dumps({name:str(helper_path(name)) for name in ['caret-probe','paste-bridge']}))")
        self.assertEqual(Path(result['caret-probe']),custom);self.assertEqual(Path(result['paste-bridge']),runtime/'paste-bridge.exe')

    def test_missing_helpers_do_not_return_install_or_source_machine_paths(self):
        result=self.run_probe("from supporter.paths import helper_path;import json;print(json.dumps([helper_path(name) for name in ['caret-probe','paste-bridge']]))")
        self.assertEqual(result,[None,None]);self.assertFalse(self.data.exists())

    def test_child_environment_does_not_modify_parent_paths_or_proxy(self):
        before=dict(os.environ);self.run_probe("from supporter.paths import ensure_runtime;import json;ensure_runtime();print(json.dumps({'ok':True}))")
        self.assertTrue(dict(os.environ)==before,'parent environment changed')


if __name__=='__main__':unittest.main()
