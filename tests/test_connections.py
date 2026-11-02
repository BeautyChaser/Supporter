"""Connection routing tests use only local values and isolated service fixtures.

No proxy listener, authenticated CLI, or network request is started here.
"""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from supporter import codex_runtime
from supporter.connections import PROXY_NAMES,connection_environment,connection_label,normalize_connection
from tests.test_service import fixture_session

ROOT=Path(__file__).resolve().parent.parent


class ConnectionTests(unittest.TestCase):
    def test_normalize_defaults_and_valid_http_proxy_addresses(self):
        self.assertEqual(normalize_connection(),{'mode':'inherit','proxyUrl':''})
        self.assertEqual(normalize_connection({}),{'mode':'inherit','proxyUrl':''})
        self.assertEqual(normalize_connection({'mode':'direct','proxyUrl':'ignored'}),{'mode':'direct','proxyUrl':''})
        for url in ['http://127.0.0.1:7890','https://proxy.invalid:8443/','http://[::1]:7890']:
            with self.subTest(url=url):
                self.assertEqual(normalize_connection({'mode':'proxy','proxyUrl':' '+url+' '}),{'mode':'proxy','proxyUrl':url})

    def test_connection_settings_require_object_and_supported_mode(self):
        for invalid in [False,True,0,1,'','proxy',[],['proxy']]:
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):normalize_connection(invalid)
        for mode in ['','system','automatic',None,False,[],{}]:
            with self.subTest(mode=mode),self.assertRaises(ValueError):normalize_connection({'mode':mode})

    def test_proxy_rejects_credentials_non_http_paths_and_invalid_ports(self):
        invalid=[
            '',None,'127.0.0.1:7890','socks5://127.0.0.1:7890','file://localhost:7890',
            'http://localhost','http://localhost:0','http://localhost:65536','http://localhost:abc',
            'http://user:password@localhost:7890','http://user@localhost:7890',
            'http://@localhost:7890','http://:@localhost:7890',
            'http://localhost:7890/api','http://localhost:7890?token=private','http://localhost:7890#private',
            'http://local host:7890','http://local\nhost:7890',
        ]
        for url in invalid:
            with self.subTest(url=url),self.assertRaises(ValueError):normalize_connection({'mode':'proxy','proxyUrl':url})

    def test_inherit_direct_and_proxy_copy_source_environment(self):
        base={**{name:'http://inherited.invalid:8000' for name in PROXY_NAMES},'NO_PROXY':'private.invalid','no_proxy':'private.invalid','AUTH_FIXTURE':'untouched'}
        original=dict(base)
        inherited=connection_environment({'mode':'inherit'},base)
        self.assertEqual(inherited,base);self.assertIsNot(inherited,base)
        direct=connection_environment({'mode':'direct'},base)
        self.assertFalse(any(name in direct for name in PROXY_NAMES))
        self.assertEqual(direct['NO_PROXY'],'private.invalid');self.assertEqual(direct['AUTH_FIXTURE'],'untouched')
        proxied=connection_environment({'mode':'proxy','proxyUrl':'http://127.0.0.1:7890'},base)
        self.assertTrue(all(proxied[name]=='http://127.0.0.1:7890' for name in PROXY_NAMES))
        self.assertEqual(proxied['NO_PROXY'],'localhost,127.0.0.1,::1')
        self.assertEqual(proxied['no_proxy'],proxied['NO_PROXY'])
        self.assertEqual(proxied['AUTH_FIXTURE'],'untouched');self.assertEqual(base,original)

    def test_environment_builder_never_modifies_parent_environment(self):
        with patch.dict(os.environ,{'HTTP_PROXY':'http://inherited.invalid:8000'}):
            parent=dict(os.environ)
            for mode in ['inherit','direct','proxy']:
                connection_environment({'mode':mode,'proxyUrl':'http://127.0.0.1:7890'})
                self.assertEqual(dict(os.environ),parent)

    def test_labels_describe_effective_route_without_credentials(self):
        self.assertEqual(connection_label({'mode':'inherit'},{}),'继承环境（无代理）')
        self.assertEqual(connection_label({'mode':'inherit'},{'HTTPS_PROXY':'http://user:secret@private.invalid:8000'}),'继承环境代理')
        self.assertEqual(connection_label({'mode':'direct'}),'直连')
        self.assertEqual(connection_label({'mode':'proxy','proxyUrl':'https://proxy.invalid:8443/'}),'代理 proxy.invalid:8443')

    def test_runtime_pool_reuses_matching_route_and_isolates_route_path_and_codex_home(self):
        # Creating a runtime does not start its subprocess. Isolate the pool so
        # existing app runtimes, if any, are neither started nor closed by this test.
        with patch.dict(codex_runtime._clients,{},clear=True),patch.dict(os.environ,{'CODEX_HOME':'fixture-home-one'}):
            path=str(ROOT/'codex.exe')
            inherited=codex_runtime.get_runtime(path)
            self.assertIs(inherited,codex_runtime.get_runtime(path,{'mode':'inherit','proxyUrl':'ignored'}))
            direct=codex_runtime.get_runtime(path,{'mode':'direct'})
            proxy=codex_runtime.get_runtime(path,{'mode':'proxy','proxyUrl':'http://127.0.0.1:7890'})
            self.assertIs(proxy,codex_runtime.get_runtime(path,{'mode':'proxy','proxyUrl':' http://127.0.0.1:7890 '}))
            other_proxy=codex_runtime.get_runtime(path,{'mode':'proxy','proxyUrl':'http://127.0.0.1:7891'})
            other_path=codex_runtime.get_runtime(str(ROOT/'other-codex.exe'))
            with patch.dict(os.environ,{'CODEX_HOME':'fixture-home-two'}):other_home=codex_runtime.get_runtime(path)
            self.assertEqual(len({id(runtime) for runtime in [inherited,direct,proxy,other_proxy,other_path,other_home]}),6)
            self.assertTrue(all(runtime.process is None for runtime in codex_runtime._clients.values()))

    def test_invalid_connection_is_rejected_before_runtime_is_cached(self):
        with patch.dict(codex_runtime._clients,{},clear=True):
            with self.assertRaises(ValueError):codex_runtime.get_runtime(str(ROOT/'codex.exe'),{'mode':'proxy','proxyUrl':'http://user:secret@localhost:7890'})
            self.assertEqual(codex_runtime._clients,{})


class ConnectionSettingsIntegrationTests(unittest.TestCase):
    def test_service_saves_normalized_connection_only_in_its_fixture_directory(self):
        with fixture_session() as session:
            session.send(type='settings',request_id='route-save',settings={'backend':'codex','codexConnection':{'mode':'proxy','proxyUrl':' http://127.0.0.1:7890 '}})
            self.assertEqual(session.receive('settings-persisted')['request_id'],'route-save')
            saved=json.loads((session.tmp/'settings.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['codexConnection'],{'mode':'proxy','proxyUrl':'http://127.0.0.1:7890'})

    def test_service_rejects_invalid_connection_and_preserves_saved_settings(self):
        with fixture_session() as session:
            session.send(type='settings',request_id='valid',settings={'backend':'codex','codexConnection':{'mode':'direct'}})
            session.receive('settings-persisted')
            path=session.tmp/'settings.json';original=path.read_bytes()
            for index,connection in enumerate([{'mode':'unsupported'},{'mode':'proxy','proxyUrl':'http://user:secret@localhost:7890'},False,[]]):
                with self.subTest(connection=connection):
                    request_id='invalid-'+str(index)
                    session.send(type='settings',request_id=request_id,settings={'backend':'codex','codexConnection':connection})
                    event=session.receive('settings-persist-error')
                    self.assertEqual(event['request_id'],request_id)
                    self.assertTrue(event['message']);self.assertEqual(path.read_bytes(),original)


if __name__=='__main__':unittest.main()
