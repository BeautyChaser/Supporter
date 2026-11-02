"""Connection settings affect only Supporter's Codex child process."""
import os
from urllib.parse import urlsplit

PROXY_NAMES=('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy')

def normalize_connection(value=None):
    value={} if value is None else value
    if not isinstance(value,dict):raise ValueError('Codex 连接设置必须是对象')
    mode=value.get('mode','inherit')
    if mode not in ('inherit','direct','proxy'):raise ValueError('请选择有效的 Codex 连接方式')
    url=str(value.get('proxyUrl','')).strip()
    if mode=='proxy':
        try:
            parsed=urlsplit(url)
            valid=(parsed.scheme in ('http','https') and parsed.hostname and parsed.port and parsed.username is None and parsed.password is None and parsed.path in ('','/') and not parsed.query and not parsed.fragment and not any(c.isspace() for c in url))
        except ValueError:valid=False
        if not valid:raise ValueError('代理地址需为 http(s)://主机:端口，不含账号、密码或路径')
    return {'mode':mode,'proxyUrl':url if mode=='proxy' else ''}

def connection_environment(value=None,base=None):
    config=normalize_connection(value);env=dict(os.environ if base is None else base)
    if config['mode']=='direct':
        for name in PROXY_NAMES:env.pop(name,None)
    elif config['mode']=='proxy':
        for name in PROXY_NAMES:env[name]=config['proxyUrl']
        env['NO_PROXY']=env['no_proxy']='localhost,127.0.0.1,::1'
    return env

def connection_label(value=None,env=None):
    config=normalize_connection(value)
    if config['mode']=='direct':return '直连'
    if config['mode']=='proxy':
        parsed=urlsplit(config['proxyUrl']);return '代理 '+parsed.netloc
    inherited=os.environ if env is None else env
    return '继承环境代理' if any(inherited.get(n) for n in PROXY_NAMES) else '继承环境（无代理）'
