"""Publish explicitly authorized source/releases using existing Git credentials.

Credentials are held in memory, never logged or written to a project file.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parent.parent

def credential():
    for name in ('GH_TOKEN','GITHUB_TOKEN'):
        if os.environ.get(name):return os.environ[name]
    result=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',capture_output=True,text=True,
        env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GCM_INTERACTIVE':'never'},timeout=25)
    if result.returncode:raise RuntimeError('Existing GitHub login is unavailable; use gh auth login or Git credential manager.')
    fields=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
    if not fields.get('password'):raise RuntimeError('No GitHub credential available')
    return fields['password']

class GitHub:
    def __init__(self,repo):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('Use owner/repository')
        self.repo=repo;self.token=credential()
        profile=self.request('GET','/user')
        if profile['login'].lower()!=repo.split('/')[0].lower():raise RuntimeError('Authenticated account does not match the requested owner')
    def request(self,method,path,data=None,*,binary=False,missing=False,upload=False,label=None):
        host='https://uploads.github.com' if upload else 'https://api.github.com'
        headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Supporter-release'}
        if data is not None:
            headers['Content-Type']='application/octet-stream' if binary else 'application/json'
            if not binary:data=json.dumps(data).encode()
        request=urllib.request.Request(host+path,data=data,headers=headers,method=method)
        try:
            with urllib.request.urlopen(request,timeout=300 if binary else 35) as response:return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code==404 and missing:return None
            raise RuntimeError(f'GitHub {method} failed with HTTP {error.code}') from None
    def prepare(self):
        found=self.request('GET','/repos/'+self.repo,missing=True)
        if found:
            if found.get('private'):raise RuntimeError('Existing repository is private; refusing to expose existing contents')
            return found
        return self.request('POST','/user/repos',{'name':self.repo.split('/')[1],'description':'Keyboard-first Windows AI input assistant with self-detecting CLI backends','private':False,'auto_init':False})
    def release(self,tag):
        version=json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']
        if tag!='v'+version:raise RuntimeError('Tag does not match package version')
        from checksums import verify
        verify(ROOT/'release',version)
        self.request('GET','/repos/'+self.repo+'/git/ref/tags/'+urllib.parse.quote(tag,safe=''))
        files=[ROOT/'release'/f'Supporter-{version}-Setup-x64.exe',ROOT/'release'/f'Supporter-{version}-x64.zip',ROOT/'release/SHA256SUMS.txt']
        if not all(file.is_file() for file in files):raise RuntimeError('Installer, ZIP and checksum file are required')
        release=self.request('GET','/repos/'+self.repo+'/releases/tags/'+urllib.parse.quote(tag,safe=''),missing=True)
        if release is None:
            body=(ROOT/'docs/RELEASE_NOTES.md').read_text(encoding='utf-8')
            release=self.request('POST','/repos/'+self.repo+'/releases',{'tag_name':tag,'name':'Supporter '+version,'body':body,'draft':False,'prerelease':False})
        existing=self.request('GET',f'/repos/{self.repo}/releases/{release["id"]}/assets')
        for file in files:
            content=file.read_bytes();digest=hashlib.sha256(content).hexdigest();prior=next((a for a in existing if a['name']==file.name),None)
            if prior:
                if prior.get('label')=='sha256:'+digest and prior.get('size')==len(content):continue
                raise RuntimeError('Conflicting release asset: '+file.name)
            query=urllib.parse.urlencode({'name':file.name,'label':'sha256:'+digest})
            self.request('POST',f'/repos/{self.repo}/releases/{release["id"]}/assets?'+query,content,binary=True,upload=True)
            print('Uploaded '+file.name,flush=True)
        final=self.request('GET','/repos/'+self.repo+'/releases/tags/'+urllib.parse.quote(tag,safe=''))
        return {'url':final['html_url'],'assets':[{'name':a['name'],'url':a['browser_download_url'],'size':a['size']} for a in final['assets']]}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--repo',default='BeautyChaser/Supporter');parser.add_argument('--publish',action='store_true')
    sub=parser.add_subparsers(dest='action',required=True);sub.add_parser('inspect');sub.add_parser('prepare');release=sub.add_parser('release');release.add_argument('--tag',required=True)
    args=parser.parse_args()
    if args.action!='inspect' and not args.publish:parser.error('Mutating operations require --publish and user authorization')
    github=GitHub(args.repo)
    if args.action=='inspect':result=github.request('GET','/repos/'+args.repo,missing=True);print(json.dumps({'repository':args.repo,'exists':bool(result)}))
    elif args.action=='prepare':result=github.prepare();print(json.dumps({'url':result['html_url'],'private':result['private']}))
    else:print(json.dumps(github.release(args.tag),indent=2))

if __name__=='__main__':main()
