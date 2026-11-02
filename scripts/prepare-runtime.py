"""Build an allowlisted, credential-free payload with a pinned Python runtime."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parent.parent
PYTHON_VERSION='3.14.8'
PYTHON_SHA256='a93abe456ab01bd96d7a085b3cdb6566b3063f4241360d114142fbdb07f0a310'
COMTYPES_SHA256='4e0a221dde2c589b82977bed802efd71cd5eb67a380347b732e02735e597f586'
PYTHON_URL=f'https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip'
MODULES=('__init__','anchors','backend_adapters','backend_plugins','backends','codex_runtime','connections',
         'defaults','diagnostics','environments','input_modes','paths','results','service','targets','terminal','uia_native','windows')
PLUGINS=('codex.json','opencode.json','hermes.json','README.md','custom-ai.json.example')

def sha256(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def unpack(archive,target):
    target=target.resolve()
    with zipfile.ZipFile(archive) as zipped:
        for info in zipped.infolist():
            candidate=(target/info.filename).resolve()
            if not candidate.is_relative_to(target):raise ValueError('Archive path outside destination')
        zipped.extractall(target)

def prepare():
    cache=ROOT/'.build-cache';cache.mkdir(exist_ok=True)
    archive=cache/f'python-{PYTHON_VERSION}-embed-amd64.zip'
    if not archive.exists():urllib.request.urlretrieve(PYTHON_URL,archive)
    if sha256(archive)!=PYTHON_SHA256:raise ValueError('Python runtime checksum mismatch')
    wheel=cache/'comtypes-1.4.17-py3-none-any.whl'
    if not wheel.is_file():raise ValueError('Run: python -m pip download --no-deps --only-binary=:all: --dest .build-cache -r requirements.txt')
    if sha256(wheel)!=COMTYPES_SHA256:raise ValueError('comtypes wheel checksum mismatch')
    payload=(ROOT/'build/payload').resolve()
    if not payload.is_relative_to(ROOT.resolve()):raise ValueError('Invalid payload directory')
    # Only the known generated staging directory is replaced.
    if payload.exists():shutil.rmtree(payload)
    payload.mkdir(parents=True)
    unpack(archive,payload/'python')
    (payload/'python/python314._pth').write_text('python314.zip\n.\n..\n../.vendor\n',encoding='utf-8')
    unpack(wheel,payload/'.vendor')
    for name in MODULES:
        target=payload/'supporter'/(name+'.py');target.parent.mkdir(exist_ok=True);shutil.copyfile(ROOT/'supporter'/(name+'.py'),target)
    for name in PLUGINS:
        target=payload/'backend-plugins'/name;target.parent.mkdir(exist_ok=True);shutil.copyfile(ROOT/'backend-plugins'/name,target)
    (payload/'defaults').mkdir();shutil.copyfile(ROOT/'defaults/settings.json',payload/'defaults/settings.json')
    for name,manifest in [('caret-probe','caret-path.txt'),('paste-bridge','paste-path.txt')]:
        source=Path((ROOT/'.runtime'/manifest).read_text(encoding='utf-8-sig').strip())
        if not source.is_file() or source.suffix.lower()!='.exe':raise ValueError('Build native helpers first')
        (payload/'native').mkdir(exist_ok=True);shutil.copyfile(source,payload/'native'/(name+'.exe'))
    shutil.copyfile(ROOT/'THIRD_PARTY_NOTICES.md',payload/'THIRD_PARTY_NOTICES.md')
    files={str(p.relative_to(payload)).replace('\\','/'):sha256(p) for p in sorted(payload.rglob('*')) if p.is_file()}
    manifest={'schemaVersion':1,'python':PYTHON_VERSION,'pythonSource':PYTHON_URL,'pythonSha256':PYTHON_SHA256,
              'comtypes':'1.4.17','comtypesSha256':sha256(wheel),'files':files}
    (payload/'distribution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'payload':str(payload),'files':len(files),'python':PYTHON_VERSION}))

if __name__=='__main__':prepare()
