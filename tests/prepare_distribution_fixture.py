"""Build a disposable component-test layout, not a release artifact."""
import argparse
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parent.parent

def extract(archive,destination):
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            if not (destination/name).resolve().is_relative_to(destination.resolve()):raise ValueError('invalid archive member')
        bundle.extractall(destination)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);args=parser.parse_args()
    destination=args.directory.resolve()
    if not destination.is_relative_to((ROOT/'.runtime').resolve()) or destination.exists():raise ValueError('use a new isolated .runtime fixture directory')
    destination.mkdir(parents=True)
    python=destination/'python';python.mkdir()
    extract(ROOT/'.build-cache/python-3.14.8-embed-amd64.zip',python)
    (python/'python314._pth').write_text('python314.zip\n.\n..\n',encoding='utf-8')
    vendor=destination/'.vendor';vendor.mkdir();extract(ROOT/'.build-cache/comtypes-1.4.17-py3-none-any.whl',vendor)
    shutil.copytree(ROOT/'supporter',destination/'supporter',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    native=destination/'native';native.mkdir()
    for name,manifest in [('paste-bridge','paste-path.txt'),('caret-probe','caret-path.txt')]:
        path=Path((ROOT/'.runtime'/manifest).read_text(encoding='utf-8-sig').strip()).resolve()
        if not path.is_relative_to((ROOT/'.runtime').resolve()):raise ValueError('only locally built test helpers may be copied')
        shutil.copy2(path,native/(name+'.exe'))
    print(destination)

if __name__=='__main__':main()
