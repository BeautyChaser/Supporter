"""Read-only checks for portable public defaults and dependency metadata."""
import json
import ast
import hashlib
import os
from pathlib import Path
import re
import subprocess
import unittest
import zipfile
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent.parent
PAYLOAD=ROOT/'build/payload'


def preparation_constants():
    tree=ast.parse((ROOT/'scripts/prepare-runtime.py').read_text(encoding='utf-8'))
    result={}
    for node in tree.body:
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id in ('MODULES','PLUGINS','PYTHON_VERSION','PYTHON_SHA256','COMTYPES_SHA256'):
                    result[target.id]=ast.literal_eval(node.value)
    return result


def private_path(path):
    parts=Path(path).as_posix().split('/')
    if any(part in {'.runtime','.vendor','.build-cache','node_modules','__pycache__','release','dist'} for part in parts):return True
    if len(parts)>1 and parts[0]=='build' and parts[1] in {'payload','native'}:return True
    if parts[-1].endswith(('.log','.pyc','.pfx','.p12')) or parts[-1] in {'auth.json','.env'}:return True
    if path=='settings.json' or path.startswith('completions/user/') and path.endswith('.json'):return True
    if path.startswith('backend-plugins/') and path.endswith('.json') and path not in {'backend-plugins/'+name+'.json' for name in ('codex','opencode','hermes')}:return True
    return False


class ReleaseManifestTests(unittest.TestCase):
    def test_default_settings_do_not_contain_personal_preferences_or_proxy(self):
        data=json.loads((ROOT/'defaults/settings.json').read_text(encoding='utf-8'))
        self.assertEqual(data['models'],{});self.assertEqual(data['reasoning'],{})
        self.assertEqual(data['codexConnection'],{'mode':'inherit','proxyUrl':''})
        self.assertFalse(data['general']['autoStart']);self.assertFalse(data['onboarding']['completed'])
        encoded=json.dumps(data)
        self.assertFalse(bool(re.search(r'[A-Za-z]:[/\\]|https?://',encoded)),'defaults contain a machine path or network route')

    def test_builtin_descriptors_use_machine_detection_instead_of_saved_paths(self):
        for name in ['codex','opencode','hermes']:
            with self.subTest(name=name):
                data=json.loads((ROOT/'backend-plugins'/(name+'.json')).read_text(encoding='utf-8'))
                self.assertEqual(data['id'],name);self.assertEqual(data['adapter'],name)
                self.assertNotIn('path',data);self.assertNotIn('env',data)
                for value in data['detect'].get('commands',[])+data['detect'].get('pathGlobs',[]):
                    self.assertFalse(bool(re.match(r'^[A-Za-z]:[/\\]|^[/\\]{2}',value)),'builtin pins an absolute workstation path')
                self.assertFalse(bool(re.search(r'https?://|sk-[A-Za-z0-9_-]{20,}',json.dumps(data))),'builtin contains a saved endpoint or token-like literal')

    def test_dependency_lock_does_not_reference_local_files_or_embedded_credentials(self):
        lock=json.loads((ROOT/'package-lock.json').read_text(encoding='utf-8'))
        violations=[]
        for name,package in lock.get('packages',{}).items():
            resolved=package.get('resolved')
            if not resolved:continue
            parsed=urlsplit(resolved)
            if parsed.scheme not in ('https','http') or parsed.username is not None or parsed.password is not None:
                # Report package name only. A failing URL may contain private data.
                violations.append(name)
        self.assertEqual(violations,[],'dependency lock includes local references or credentials')

    def test_desktop_build_uses_explicit_product_files_instead_of_project_globs(self):
        process=subprocess.run(['node','-e','process.stdout.write(JSON.stringify(require(process.argv[1])))',str(ROOT/'electron-builder.cjs')],
            cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=10,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.assertEqual(process.returncode,0,'cannot load desktop build configuration')
        config=json.loads(process.stdout);files=config['files']
        self.assertIn('desktop/main.cjs',files);self.assertIn('desktop/onboarding.html',files)
        for path in files:
            self.assertFalse(bool(re.search(r'[*?{}!]',path)),'desktop build uses a non-explicit file selector')
            self.assertFalse(private_path(path),'desktop includes a private path: '+path)
            self.assertNotIn('test',Path(path).name.lower(),'desktop includes a test entry: '+path)
            self.assertTrue((ROOT/path).is_file(),'desktop product file missing: '+path)
        self.assertEqual(config['extraResources'],[{'from':'build/payload','to':'supporter','filter':['**/*']}])
        self.assertFalse(config['nsis']['perMachine']);self.assertFalse(config['nsis']['deleteAppDataOnUninstall'])
        self.assertTrue(config['nsis']['createDesktopShortcut']);self.assertTrue(config['nsis']['createStartMenuShortcut'])

    def test_source_preparation_lists_only_product_modules_and_builtin_plugins(self):
        constants=preparation_constants()
        self.assertTrue(constants['MODULES']);self.assertEqual(len(constants['MODULES']),len(set(constants['MODULES'])))
        self.assertEqual(set(constants['PLUGINS']),{'codex.json','opencode.json','hermes.json','README.md','custom-ai.json.example'})
        self.assertTrue({'paths','service','windows','uia_native','diagnostics'}.issubset(constants['MODULES']))
        self.assertFalse({'app','diagnose_uia'}.intersection(constants['MODULES']))
        for name in constants['MODULES']:
            self.assertTrue(bool(re.fullmatch(r'[a-z_]+',name)),'non-module name in payload list')
            self.assertTrue((ROOT/'supporter'/(name+'.py')).is_file())
        for field in ('PYTHON_SHA256','COMTYPES_SHA256'):self.assertTrue(bool(re.fullmatch('[a-f0-9]{64}',constants[field])))

    def test_public_readme_does_not_publish_current_user_route_or_authorization(self):
        violations=[]
        for relative in ['README.md','desktop/settings.html']:
            text=(ROOT/relative).read_text(encoding='utf-8')
            if re.search(r'当前用户已授权|用户现已明确批准|127\.0\.0\.1:7890',text):violations.append(relative)
        self.assertEqual(violations,[],'public product docs retain workstation-specific session details')

    def test_git_source_index_excludes_private_generated_and_custom_state(self):
        if not (ROOT/'.git').exists():self.skipTest('source is not a Git checkout yet')
        process=subprocess.run(['git','ls-files','--cached','-z'],cwd=ROOT,capture_output=True,timeout=10)
        self.assertEqual(process.returncode,0,'cannot inspect Git source index')
        paths=process.stdout.decode('utf-8').split('\0');violations=[path for path in paths if path and private_path(path)]
        self.assertEqual(violations,[],'source index includes private/generated files')
        roots={str(ROOT.resolve()),str(Path.home().resolve())}
        needles={value.encode(encoding) for root in roots for value in {root,root.replace('\\','/')} for encoding in ('utf-8','utf-16le')}
        content_violations=[]
        for relative in paths:
            if not relative:continue
            file=ROOT/relative
            if not file.is_file():continue
            data=file.read_bytes()
            if any(needle in data for needle in needles):content_violations.append(relative+': developer path')
            if re.search(rb'(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})',data):content_violations.append(relative+': token-like literal')
            if file.suffix.lower()=='.md':
                text=data.decode('utf-8-sig',errors='replace')
                if re.search(r'当前用户已授权|用户现已明确批准|127\.0\.0\.1:7890',text):content_violations.append(relative+': personal session details')
        self.assertEqual(content_violations,[],'tracked source contains private details; values are not printed')


@unittest.skipUnless(PAYLOAD.is_dir(),'run the runtime preparation before artifact audit')
class PreparedPayloadTests(unittest.TestCase):
    def test_distribution_manifest_covers_every_payload_file_with_correct_hash(self):
        manifest=json.loads((PAYLOAD/'distribution-manifest.json').read_text(encoding='utf-8'))
        files={path.relative_to(PAYLOAD).as_posix():path for path in PAYLOAD.rglob('*') if path.is_file() and path.name!='distribution-manifest.json'}
        self.assertEqual(set(files),set(manifest['files']),'payload has unlisted or missing files')
        violations=[]
        for name,path in files.items():
            if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['files'][name]:violations.append(name)
        self.assertEqual(violations,[],'payload changed after its manifest was generated')
        constants=preparation_constants();self.assertEqual(manifest['python'],constants['PYTHON_VERSION'])
        self.assertEqual(manifest['pythonSha256'],constants['PYTHON_SHA256']);self.assertEqual(manifest['comtypesSha256'],constants['COMTYPES_SHA256'])

    def test_payload_product_modules_plugins_defaults_and_helpers_are_exactly_allowlisted(self):
        constants=preparation_constants()
        self.assertEqual({p.name for p in (PAYLOAD/'supporter').iterdir()},{name+'.py' for name in constants['MODULES']})
        self.assertEqual({p.name for p in (PAYLOAD/'backend-plugins').iterdir()},set(constants['PLUGINS']))
        self.assertEqual({p.name for p in (PAYLOAD/'defaults').iterdir()},{'settings.json'})
        self.assertEqual({p.name for p in (PAYLOAD/'native').iterdir()},{'caret-probe.exe','paste-bridge.exe'})
        self.assertEqual((PAYLOAD/'defaults/settings.json').read_bytes(),(ROOT/'defaults/settings.json').read_bytes())
        for name in constants['MODULES']:
            self.assertEqual((PAYLOAD/'supporter'/(name+'.py')).read_bytes(),(ROOT/'supporter'/(name+'.py')).read_bytes(),'staged module is stale: '+name)
        for name in constants['PLUGINS']:
            self.assertEqual((PAYLOAD/'backend-plugins'/name).read_bytes(),(ROOT/'backend-plugins'/name).read_bytes(),'staged plugin is stale: '+name)

    def test_payload_contains_no_personal_state_logs_caches_manifests_or_project_paths(self):
        forbidden_parts={'.runtime','__pycache__','completions','.git','.agents','.codex'}
        violations=[];sensitive_roots={str(ROOT.resolve()),str(Path.home().resolve())}
        needles={value.encode(encoding) for root in sensitive_roots for value in {root,root.replace('\\','/')} for encoding in ('utf-8','utf-16le')}
        for file in PAYLOAD.rglob('*'):
            if not file.is_file():continue
            relative=file.relative_to(PAYLOAD);name=relative.as_posix()
            if forbidden_parts.intersection(relative.parts) or file.name in {'habits.json','auth.json','caret-path.txt','paste-path.txt'} or file.suffix.lower() in {'.log','.pyc','.pfx','.p12'}:
                violations.append(name+': private/generated path');continue
            if file.name=='settings.json' and name!='defaults/settings.json':violations.append(name+': user settings')
            if '.vendor' in relative.parts and 'gen' in relative.parts and file.name!='__init__.py':violations.append(name+': generated COM cache')
            data=file.read_bytes()
            if any(needle in data for needle in needles):violations.append(name+': developer machine path')
            if re.search(rb'(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})',data):violations.append(name+': token-like literal')
        self.assertEqual(violations,[],'payload includes private artifacts; only paths/categories are reported')

    def test_embedded_python_is_self_contained_and_never_adds_current_working_directory(self):
        constants=preparation_constants();version=constants['PYTHON_VERSION'].split('.')
        abi=''.join(version[:2]);directory=PAYLOAD/'python'
        for name in ['python.exe','pythonw.exe','python'+abi+'.dll','python'+abi+'.zip','LICENSE.txt']:
            self.assertTrue((directory/name).is_file(),'embedded Python required file missing: '+name)
        lines=(directory/('python'+abi+'._pth')).read_text(encoding='utf-8').splitlines()
        self.assertEqual(lines,['python'+abi+'.zip','.','..','../.vendor'])
        self.assertNotIn('import site',lines)


@unittest.skipUnless((ROOT/'release/win-unpacked/resources/app.asar').is_file(),'build the unpacked app before archive audit')
class BuiltUnpackedAuditTests(unittest.TestCase):
    def test_actual_asar_contains_only_allowlisted_product_files_and_current_sources(self):
        code="""const path=require('node:path'),crypto=require('node:crypto'),asar=require('@electron/asar');
const archive=path.resolve('release/win-unpacked/resources/app.asar'),config=require(path.resolve('electron-builder.cjs'));
const names=asar.listPackage(archive).map(name=>name.replace(/^[\\\\/]+/,'').replaceAll('\\\\','/')).filter(name=>!asar.statFile(archive,name).files);
const hashes=Object.fromEntries(names.map(name=>[name,crypto.createHash('sha256').update(asar.extractFile(archive,name)).digest('hex')]));
const metadata=JSON.parse(asar.extractFile(archive,'package.json').toString('utf8'));
process.stdout.write(JSON.stringify({names,allowed:config.files,hashes,metadata:{name:metadata.name,version:metadata.version,main:metadata.main}}));"""
        process=subprocess.run(['node','-e',code],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=10,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.assertEqual(process.returncode,0,'cannot inspect built ASAR archive')
        actual=json.loads(process.stdout);self.assertEqual(set(actual['names']),set(actual['allowed']))
        stale=[]
        for name,digest in actual['hashes'].items():
            if name!='package.json' and hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:stale.append(name)
        self.assertEqual(stale,[],'built desktop archive does not match current sources')
        metadata=json.loads((ROOT/'package.json').read_text(encoding='utf-8'))
        self.assertEqual(actual['metadata'],{name:metadata[name] for name in ('name','version','main')})

    def test_unpacked_resources_match_clean_staging_file_for_file(self):
        actual=ROOT/'release/win-unpacked/resources/supporter'
        self.assertTrue(actual.is_dir())
        staged={file.relative_to(PAYLOAD).as_posix():hashlib.sha256(file.read_bytes()).hexdigest() for file in PAYLOAD.rglob('*') if file.is_file()}
        built={file.relative_to(actual).as_posix():hashlib.sha256(file.read_bytes()).hexdigest() for file in actual.rglob('*') if file.is_file()}
        self.assertEqual(set(built),set(staged),'unpacked resources include unexpected or missing files')
        self.assertEqual([name for name in staged if staged[name]!=built[name]],[],'unpacked resources differ from clean staging')


@unittest.skipUnless((ROOT/'release').is_dir() and list((ROOT/'release').glob('Supporter-*-x64.zip')),'build Windows release assets before final archive audit')
class BuiltWindowsAssetsAuditTests(unittest.TestCase):
    def test_final_installer_and_zip_have_matching_published_sha256_sums(self):
        version=json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']
        required={f'Supporter-{version}-Setup-x64.exe',f'Supporter-{version}-x64.zip'}
        checksums=ROOT/'release/SHA256SUMS.txt'
        self.assertTrue(checksums.is_file(),'generate SHA256SUMS.txt after the final installer and ZIP build')
        records={}
        for line in checksums.read_text(encoding='utf-8-sig').splitlines():
            if not line.strip():continue
            match=re.fullmatch(r'([a-fA-F0-9]{64})\s+\*?([^/\\]+)',line)
            self.assertIsNotNone(match,'checksum entry must be a SHA256 and a release filename')
            digest,name=match.groups();self.assertNotIn(name,records,'duplicate checksum filename');records[name]=digest.lower()
        self.assertTrue(required.issubset(records),'checksum file does not cover the final installer and ZIP')
        mismatched=[]
        for name,digest in records.items():
            file=ROOT/'release'/name
            if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=digest:mismatched.append(name)
        self.assertEqual(mismatched,[],'release checksums are stale or reference missing artifacts')

    def test_final_zip_contains_current_asar_and_clean_manifest_verified_runtime(self):
        version=json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']
        file=ROOT/'release'/f'Supporter-{version}-x64.zip'
        self.assertTrue(file.is_file(),'matching-version ZIP missing')
        with zipfile.ZipFile(file) as archive:
            names=archive.namelist();self.assertEqual(len(names),len(set(names)),'ZIP contains duplicate entries')
            self.assertFalse(any(name.startswith(('/','\\')) or '..' in name.replace('\\','/').split('/') or re.match(r'^[A-Za-z]:',name) for name in names),'ZIP has an unsafe path')
            asars=[name for name in names if name.endswith('resources/app.asar')]
            self.assertEqual(len(asars),1,'ZIP must contain one application archive')
            self.assertEqual(hashlib.sha256(archive.read(asars[0])).hexdigest(),hashlib.sha256((ROOT/'release/win-unpacked/resources/app.asar').read_bytes()).hexdigest(),'ZIP desktop archive differs from unpacked app')
            prefix=asars[0][:-len('app.asar')]+'supporter/'
            manifest=json.loads(archive.read(prefix+'distribution-manifest.json'))
            actual={name[len(prefix):] for name in names if name.startswith(prefix) and not name.endswith('/')}
            self.assertEqual(actual,set(manifest['files'])|{'distribution-manifest.json'},'ZIP runtime contains unlisted or missing files')
            mismatched=[name for name,digest in manifest['files'].items() if hashlib.sha256(archive.read(prefix+name)).hexdigest()!=digest]
            self.assertEqual(mismatched,[],'ZIP runtime hash mismatch')
            self.assertEqual(archive.read(prefix+'distribution-manifest.json'),(PAYLOAD/'distribution-manifest.json').read_bytes(),'ZIP runtime does not match current staging manifest')


if __name__=='__main__':unittest.main()
