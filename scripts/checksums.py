import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def expected(version):return [f'Supporter-{version}-Setup-x64.exe',f'Supporter-{version}-x64.zip']
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(directory,version):
    directory=Path(directory);lines=[]
    for name in expected(version):lines.append(digest(directory/name)+'  '+name)
    (directory/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n',encoding='ascii')
    return verify(directory,version)
def verify(directory,version):
    directory=Path(directory);records={}
    for line in (directory/'SHA256SUMS.txt').read_text(encoding='ascii').splitlines():
        value,name=line.split('  ',1)
        if name not in expected(version) or name in records:raise ValueError('Unexpected checksum entry')
        records[name]=value
    if set(records)!=set(expected(version)):raise ValueError('Incomplete checksum file')
    for name,value in records.items():
        if digest(directory/name)!=value:raise ValueError('Release checksum mismatch: '+name)
    return True
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    version=json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']
    (verify if args.verify else write)(ROOT/'release',version);print('Release checksums verified.')
