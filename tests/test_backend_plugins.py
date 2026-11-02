"""Plugin contract tests using temporary catalogs and a local Python CLI only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,Mock,patch

from supporter import backend_adapters,backend_plugins,backends

ROOT=Path(__file__).resolve().parent.parent
FIXTURE_CODE=r'''
import json,os,pathlib,sys,time
sys.stdin.reconfigure(encoding='utf-8');sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
mode=sys.argv[1];args=sys.argv[2:]
if mode=='--version':print('supporter-local-fixture 1.2.3')
elif mode=='models-json':print(json.dumps({'catalog':{'items':['fixture-a','fixture-b','fixture-a',4,'bad\nmodel']}}))
elif mode=='models-lines':print('fixture-a\nfixture-b\nfixture-a')
elif mode=='jsonl':
    print(json.dumps({'type':'status','part':{'text':'ignored'}}))
    print('non-json progress')
    print(json.dumps({'type':'text','part':{'text':'first\n'}}))
    print(json.dumps({'type':'text','part':{'text':'second'}}))
elif mode=='bad-json':print('not JSON')
elif mode=='empty':pass
elif mode=='error-json':print(json.dumps({'type':'error','error':'fixture rejected request'}))
elif mode=='fail':print('fixture CLI failed',file=sys.stderr);sys.exit(9)
elif mode=='sleep':time.sleep(20)
else:
    text=sys.stdin.read()
    query=pathlib.Path(args[args.index('--query-file')+1]).read_text(encoding='utf-8') if '--query-file' in args else None
    result=json.dumps({'argv':args,'stdin':text,'query':query,'env':os.environ.get('SUPPORTER_FIXTURE_VAR')},ensure_ascii=False)
    output=json.dumps({'payload':{'text':result}},ensure_ascii=False)
    if mode=='file':pathlib.Path(args[args.index('--output-file')+1]).write_text(output,encoding='utf-8');print('progress only')
    else:print(output)
'''


class BackendPluginTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='backend-plugins-',dir=ROOT/'.runtime')
        self.root=Path(self.temporary.name);self.plugins=self.root/'plugins';self.plugins.mkdir()
        self.bin=self.root/'bin';self.bin.mkdir();self.versions={};self.model_outputs={};self.processes=[]
        self.fixture=self.root/'local_cli.py';self.fixture.write_text(FIXTURE_CODE,encoding='utf-8')
        self.env_patch=patch.dict(os.environ,{'SUPPORTER_BACKEND_DIR':str(self.plugins),'PATH':'','CODEX_HOME':str(self.root/'codex-home'),'HERMES_HOME':str(self.root/'hermes-home')})
        self.env_patch.start();self.cache_patch=patch.dict(backend_plugins._cache,{},clear=True);self.cache_patch.start()
        self.ctx=SimpleNamespace(ROOT=self.root,Backend=backends.Backend,DEFAULT=backends.DEFAULT,read_json=backends.read_json,
            call=Mock(side_effect=self.call),launch=Mock(side_effect=self.launch),stop=Mock(side_effect=self.stop))

    def tearDown(self):
        for process in self.processes:
            if process.poll() is None:self.stop(process)
            for stream in (process.stdin,process.stdout,process.stderr):
                if stream and not stream.closed:stream.close()
        self.cache_patch.stop();self.env_patch.stop();self.temporary.cleanup()

    def executable(self,name='fixture-agent.exe',version='fixture-agent 1.2.3',directory=None):
        path=(directory or self.bin)/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(version+' '+str(time.monotonic_ns()),encoding='utf-8');self.versions[str(path.resolve())]=version
        return path

    def description(self,identifier='fixture',path=None,**changes):
        result={'schemaVersion':1,'id':identifier,'label':'Local fixture','adapter':'generic',
            'detect':{'commands':[str(path or self.bin/'fixture-agent.exe')],'versionArgs':['--version']},
            'models':{'values':['fixture-model']},'reasoning':{'*':['low','high']},'generate':{'args':[]}}
        result.update(changes);return result

    def write_plugin(self,description,filename=None):
        path=self.plugins/(filename or description.get('id','invalid'))
        path=path.with_suffix('.json');path.write_text(json.dumps(description,ensure_ascii=False),encoding='utf-8');return path

    def call(self,path,args,timeout=20):
        if Path(path).resolve()==Path(sys.executable).resolve():
            # This is our fixed local fixture, never the installed backend CLI.
            self.assertEqual(Path(args[0]).resolve(),self.fixture.resolve())
            completed=subprocess.run([path,*args],capture_output=True,text=True,encoding='utf-8',timeout=timeout,
                cwd=self.root,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if completed.returncode:raise RuntimeError(completed.stderr.strip())
            return completed.stdout.strip()
        key=(str(Path(path).resolve()),tuple(args))
        if key in self.model_outputs:
            value=self.model_outputs[key]
        elif args==['--version']:value=self.versions.get(str(Path(path).resolve()),RuntimeError('unknown local fixture'))
        else:raise RuntimeError('undeclared fixture command: '+repr(args))
        if isinstance(value,BaseException):raise value
        return value.strip()

    def launch(self,path,args,input_text=None,env=None):
        self.assertEqual(Path(path).resolve(),Path(sys.executable).resolve())
        self.assertEqual(Path(args[0]).resolve(),self.fixture.resolve())
        process=subprocess.Popen([path,*args],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,encoding='utf-8',cwd=self.root,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.processes.append(process)
        return process,input_text

    def stop(self,process):
        if process.poll() is None:process.terminate()
        process.wait(timeout=2)

    def discover(self,**options):return backend_plugins.discover(self.ctx,**options)
    def backend(self,name='fixture',**options):return next(b for b in self.discover(**options) if b.name==name)

    def actual_plugin(self,mode='json',**changes):
        result=self.description(path=Path(sys.executable),
            detect={'commands':[sys.executable],'versionArgs':[str(self.fixture),'--version']},
            models={'args':[str(self.fixture),'models-json'],'format':'json','field':'catalog.items'},
            generate={'args':[str(self.fixture),mode,'--query-file','{query_file}'],
                'modelArgs':['--model','{model}'],'reasoningArgs':['--reasoning','{reasoning}'],
                'env':{'SUPPORTER_FIXTURE_VAR':'child-only'},'output':{'format':'json','field':'payload.text'}})
        result.update(changes);return result

    def generate(self,b,model='fixture-a',prompt='fixture prompt',reasoning='default',progress=None,cancel=None):
        return backend_plugins.generate(b,self.ctx,model,prompt,cancel or threading.Event(),reasoning=reasoning,on_progress=progress)

    def test_builtin_descriptors_remain_declarative_and_independent(self):
        plugins,errors=backend_plugins.load_plugins(ROOT/'backend-plugins')
        self.assertEqual(errors,[])
        self.assertEqual({p.id:p.adapter for p in plugins},{'codex':'codex','opencode':'opencode','hermes':'hermes'})
        self.assertEqual([p.id for p in plugins],['codex','opencode','hermes'])

    def test_dynamic_add_remove_disable_and_enable_require_no_core_edits(self):
        path=self.executable();self.assertEqual(self.discover(),[])
        description=self.description(path=path);plugin=self.write_plugin(description)
        self.assertEqual(self.backend().status,'available')
        description['enabled']=False;self.write_plugin(description)
        self.assertEqual(self.discover(),[])
        description['enabled']=True;self.write_plugin(description)
        self.assertFalse(self.backend().error)
        plugin.unlink();self.assertEqual(self.discover(),[])
        self.assertEqual(backend_plugins.discover_one('fixture',self.ctx).status,'missing')

    def test_install_delete_bad_version_and_reinstall_update_availability(self):
        path=self.bin/'fixture-agent.exe';self.write_plugin(self.description(path=path))
        self.assertEqual(self.backend().status,'missing');self.ctx.call.assert_not_called()
        self.executable(version='fixture-agent 1.0.0');self.assertEqual(self.backend().status,'available')
        path.unlink();self.assertEqual(self.backend().status,'missing')
        self.executable(version='broken');self.versions[str(path.resolve())]=RuntimeError('not a working CLI')
        bad=self.backend();self.assertEqual(bad.status,'unavailable');self.assertIn('not a working CLI',bad.error)
        self.executable(version='empty version');self.versions[str(path.resolve())]='\n'
        self.assertEqual(self.backend().status,'unavailable')
        self.executable(version='fixture-agent 1.0.1');self.assertEqual(self.backend().version,'fixture-agent 1.0.1')

    def test_version_probe_tries_other_candidates_and_selects_newest_semver(self):
        broken=self.executable('broken.exe');old=self.executable('old.exe','agent 2.9.9');new=self.executable('new.exe','agent 2.10.0')
        self.versions[str(broken.resolve())]=RuntimeError('broken executable')
        self.write_plugin(self.description(detect={'commands':[str(broken),str(old),str(new)],'selection':'newest'}))
        b=self.backend();self.assertEqual(b.path,str(new.resolve()));self.assertEqual(b.version,'agent 2.10.0');self.assertFalse(b.error)

    def test_newest_selection_orders_codex_prerelease_builds_and_stable_release(self):
        old=self.executable('old.exe','codex 0.166.0-alpha.5.1')
        latest=self.executable('latest.exe','codex 0.166.0-alpha.5.10')
        stable=self.executable('stable.exe','codex 0.166.0')
        description=self.description(detect={'commands':[str(old),str(latest)],'selection':'newest'})
        self.write_plugin(description);self.assertEqual(self.backend().path,str(latest.resolve()))
        description['detect']['commands'].append(str(stable));self.write_plugin(description)
        self.assertEqual(self.backend().path,str(stable.resolve()))

    def test_codex_glob_detection_works_without_path_and_loads_local_models_and_effort(self):
        local=self.root/'local-app-data';codex_home=Path(os.environ['CODEX_HOME']);codex_home.mkdir()
        old=self.executable('codex.exe','codex 0.160.0',local/'OpenAI/Codex/bin/v1')
        new=self.executable('codex.exe','codex 0.166.0-alpha.5',local/'OpenAI/Codex/bin/v2')
        cache={'models':[{'slug':'gpt-fixture-luna','visibility':'list','supported_reasoning_levels':[{'effort':'low'},{'effort':'high'}]},
            {'slug':'hidden-model','visibility':'hidden','supported_reasoning_levels':[{'effort':'xhigh'}]}]}
        (codex_home/'models_cache.json').write_text(json.dumps(cache),encoding='utf-8')
        (codex_home/'config.toml').write_text('model = "gpt-fixture-luna"\n',encoding='utf-8')
        descriptor=json.loads((ROOT/'backend-plugins/codex.json').read_text(encoding='utf-8'));self.write_plugin(descriptor)
        with patch.dict(os.environ,{'LOCALAPPDATA':str(local)}):b=self.backend('codex')
        self.assertEqual(b.path,str(new.resolve()));self.assertNotEqual(b.path,str(old.resolve()))
        self.assertIn('gpt-fixture-luna',b.models);self.assertNotIn('hidden-model',b.models)
        self.assertEqual(b.reasoning['gpt-fixture-luna'],['low','high']);self.assertEqual(b.reasoning[backends.DEFAULT],['low','high'])

    def test_generic_model_json_and_lines_are_deduplicated_and_scoped(self):
        description=self.actual_plugin();self.write_plugin(description);b=self.backend()
        self.assertEqual(b.models,[backends.DEFAULT,'fixture-a','fixture-b'])
        self.assertEqual(b.reasoning['fixture-a'],['low','high'])
        description['models']={'values':['declared'],'args':[str(self.fixture),'models-lines'],'format':'lines'}
        description['reasoning']={'*':['low'],'fixture-b':['high']};self.write_plugin(description)
        b=self.backend();self.assertEqual(b.models,[backends.DEFAULT,'declared','fixture-a','fixture-b'])
        self.assertEqual(b.reasoning['fixture-b'],['high']);self.assertEqual(b.reasoning['fixture-a'],['low'])

    def test_opencode_discovery_reads_models_variants_and_version_specific_style(self):
        executable=self.executable('opencode.exe','opencode 2.0.0')
        description=self.description('opencode',path=executable,adapter='opencode');self.write_plugin(description)
        self.model_outputs[(str(executable.resolve()),('run','--help'))]='--model provider/model#variant'
        self.model_outputs[(str(executable.resolve()),('models',))]='provider/model\nnot a model\nprovider/model\nprovider/other'
        config=self.root/'opencode.json';config.write_text(json.dumps({'provider':{'provider':{'models':{'model':{'variants':{
            'low':{},'high':{},'disabled':{'disabled':True}}}}}}}),encoding='utf-8')
        with patch.object(backend_adapters.ADAPTERS['opencode'],'watch_paths',return_value=[config]):b=self.backend('opencode')
        self.assertEqual(b.models,[backends.DEFAULT,'provider/model','provider/other'])
        self.assertEqual(b.reasoning['provider/model'],['low','high']);self.assertEqual(b.reasoning_style,'model-suffix')

    def test_hermes_discovery_keeps_provider_model_binding_and_supported_effort(self):
        executable=self.executable('hermes.exe','hermes 0.9.0');python=self.executable('python.exe','fixture-python')
        home=Path(os.environ['HERMES_HOME']);home.mkdir();(home/'config.yaml').write_text('model: fixture',encoding='utf-8')
        (home/'provider_models_cache.json').write_text(json.dumps({'provider-a':{'models':['chosen','other']},'provider-b':{'models':['remote']}}),encoding='utf-8')
        self.write_plugin(self.description('hermes',path=executable,adapter='hermes'))
        def call(path,args,timeout=20):
            if Path(path)==python and args[0]=='-c':
                return json.dumps('provider-a') if "m.get('provider'" in args[1] else json.dumps(['chosen'])
            return self.call(path,args,timeout)
        self.ctx.call=Mock(side_effect=call);b=self.backend('hermes')
        self.assertIn('chosen',b.models);self.assertIn('other',b.models);self.assertIn('provider-b :: remote',b.models)
        self.assertIn('provider-a :: chosen',b.models);self.assertIn('ultra',b.reasoning['provider-b :: remote'])

    def test_generic_actual_argv_stdin_query_and_child_env_preserve_shell_characters(self):
        self.write_plugin(self.actual_plugin());b=self.backend()
        sentinel=self.root/'must-not-be-created.txt'
        prompt='中文\n"quotes" `whoami` $(whoami) & echo injected > '+str(sentinel)+'\n{model} ${HOME} %PATH%'
        parent_environment=dict(os.environ);progress=[]
        result=json.loads(self.generate(b,prompt=prompt,reasoning='low',progress=progress.append))
        self.assertEqual(result['stdin'],prompt);self.assertEqual(result['query'],prompt)
        self.assertEqual(result['argv'][-4:],['--model','fixture-a','--reasoning','low'])
        self.assertEqual(result['env'],'child-only');self.assertEqual(dict(os.environ),parent_environment)
        self.assertFalse(sentinel.exists());self.assertTrue(progress)
        self.assertEqual(self.ctx.launch.call_count,1)

    def test_generic_prompt_argument_and_inline_templates_do_not_rewrite_user_data(self):
        description=self.actual_plugin();description['generate']['args']=[str(self.fixture),'json','--prompt','{prompt}','--combined','{prompt}|{model}']
        self.write_plugin(description);prompt='literal {model} {reasoning} & `whoami`'
        result=json.loads(self.generate(self.backend(),prompt=prompt))
        self.assertEqual(result['argv'][result['argv'].index('--prompt')+1],prompt)
        self.assertEqual(result['argv'][result['argv'].index('--combined')+1],prompt+'|fixture-a')

    def test_generic_jsonl_filters_events_preserves_lines_and_ignores_plain_progress(self):
        description=self.actual_plugin('jsonl');description['generate']['output']={'format':'jsonl','field':'part.text','eventType':'text'}
        self.write_plugin(description)
        self.assertEqual(self.generate(self.backend()),'first\nsecond')

    def test_generic_output_file_and_stdin_none_work(self):
        description=self.actual_plugin('file');description['generate']['stdin']='none'
        description['generate']['args']+=['--output-file','{output_file}'];description['generate']['output']['fromFile']=True
        self.write_plugin(description);result=json.loads(self.generate(self.backend(),prompt='first\nsecond'))
        self.assertEqual(result['stdin'],'');self.assertEqual(result['query'],'first\nsecond')

    def test_generic_script_path_with_spaces_and_default_model_need_no_shell(self):
        spaced=self.root/'directory with spaces';spaced.mkdir();self.fixture=spaced/'local CLI.py'
        self.fixture.write_text(FIXTURE_CODE,encoding='utf-8');self.write_plugin(self.actual_plugin())
        result=json.loads(self.generate(self.backend(),model=backends.DEFAULT,prompt='two\nlines'))
        self.assertEqual(result['stdin'],'two\nlines');self.assertEqual(result['query'],'two\nlines')
        self.assertNotIn('--model',result['argv']);self.assertNotIn('--reasoning',result['argv'])

    def test_generic_batch_launchers_are_unavailable_and_cannot_generate(self):
        for suffix in ['.cmd','.bat','.ps1']:
            with self.subTest(suffix=suffix):
                executable=self.executable('fixture-agent'+suffix)
                self.write_plugin(self.description(path=executable))
                b=self.backend();self.assertEqual(b.status,'unavailable');self.assertTrue(b.error)
                with self.assertRaisesRegex(RuntimeError,'cmd|bat|原生|batch'):self.generate(b,model='fixture-model',prompt='literal & text')
                manual=backends.Backend('fixture',path=str(executable),plugin_revision=b.plugin_revision)
                with self.assertRaisesRegex(RuntimeError,'cmd|bat|原生|batch'):self.generate(manual,model='fixture-model',prompt='literal & text')
                self.ctx.launch.assert_not_called()

    def test_generic_empty_malformed_json_cli_exit_and_error_events_are_reported(self):
        for mode,message in [('empty','未返回|JSON 无效'),('bad-json','JSON 无效'),('fail','fixture CLI failed'),('error-json','fixture rejected request')]:
            with self.subTest(mode=mode):
                self.write_plugin(self.actual_plugin(mode))
                with self.assertRaisesRegex(RuntimeError,message):self.generate(self.backend())

    def test_generic_generation_remains_cancellable(self):
        self.write_plugin(self.actual_plugin('sleep'));b=self.backend();cancel=threading.Event()
        timer=threading.Timer(.15,cancel.set);timer.start();started=time.monotonic()
        try:
            with self.assertRaisesRegex(RuntimeError,'取消'):self.generate(b,cancel=cancel)
        finally:timer.join()
        self.assertLess(time.monotonic()-started,2);self.ctx.stop.assert_called_once()

    def test_unsupported_reasoning_is_rejected_before_cli_launch(self):
        self.write_plugin(self.actual_plugin());b=self.backend()
        with self.assertRaisesRegex(RuntimeError,'未声明支持'):self.generate(b,reasoning='xhigh')
        self.ctx.launch.assert_not_called()
        description=self.actual_plugin();description['generate'].pop('reasoningArgs');self.write_plugin(description)
        with self.assertRaisesRegex(ValueError,'没有声明推理'):self.generate(self.backend(),reasoning='low')

    def test_malformed_and_duplicate_descriptors_do_not_disable_other_plugins(self):
        executable=self.executable();good=self.description('good',path=executable);self.write_plugin(good,'00-good')
        self.write_plugin(self.description('good',path=executable),'01-duplicate')
        (self.plugins/'02-broken.json').write_text('{broken json',encoding='utf-8')
        self.write_plugin(self.description('wrong-schema',schemaVersion=2),'03-wrong-schema')
        self.write_plugin(self.description('other',path=executable),'04-other')
        result=self.discover();self.assertEqual({b.name for b in result if b.status=='available'},{'good','other'})
        self.assertEqual(len([b for b in result if b.status=='plugin-error']),3)

    def test_invalid_plugin_cannot_reserve_an_id_a_valid_plugin_uses(self):
        executable=self.executable()
        for changes in [{'adapter':'unknown'},{'enabled':False}]:
            with self.subTest(changes=changes):
                self.write_plugin(self.description('fixture',**changes),'00-invalid')
                self.write_plugin(self.description('fixture',path=executable),'01-valid')
                result=self.discover();self.assertTrue(any(b.name=='fixture' and b.status=='available' for b in result))

    def test_schema_rejects_invalid_types_templates_and_oversized_descriptor(self):
        cases=[]
        for field,value in [('schemaVersion',True),('enabled','false'),('priority',True),('detect',[])]:
            description=self.description();description[field]=value;cases.append((field,description))
        for label,generate in [('unknown-template',{'args':['{unknown}']}),('bad-fromFile',{'args':[],'output':{'fromFile':'false'}})]:
            description=self.description();description['generate']=generate;cases.append((label,description))
        for field in ['modelArgs','reasoningArgs']:
            description=self.description();description['generate'][field]=['{unknown}'];cases.append((field,description))
        description=self.description();description['detect']['versionArgs']=['--version','{prompt}'];cases.append(('version-template',description))
        description=self.description();description['generate']['env']={'BAD=KEY':'value'};cases.append(('env-key',description))
        for index,(label,description) in enumerate(cases):
            description['id']='invalid-'+str(index);self.write_plugin(description,str(index)+'-'+label)
        (self.plugins/'large.json').write_text(' '*65537,encoding='utf-8')
        plugins,errors=backend_plugins.load_plugins();self.assertEqual(plugins,[]);self.assertEqual(len(errors),len(cases)+1)

    def test_cache_hot_update_force_invalidate_and_presence_do_not_probe_unnecessarily(self):
        executable=self.executable();description=self.description(path=executable);self.write_plugin(description)
        initial=self.discover(presence=True)[0];self.assertEqual(initial.status,'checking');self.ctx.call.assert_not_called()
        self.assertEqual(self.backend().status,'available');count=self.ctx.call.call_count
        self.assertEqual(self.backend().status,'available');self.assertEqual(self.ctx.call.call_count,count)
        self.discover(presence=True);self.assertEqual(self.ctx.call.call_count,count)
        self.discover(force=True);self.assertEqual(self.ctx.call.call_count,count+1)
        backend_plugins.invalidate();self.backend();self.assertEqual(self.ctx.call.call_count,count+2)
        description['models']['values']=['new-model'];self.write_plugin(description)
        self.assertIn('new-model',self.backend().models);self.assertEqual(self.ctx.call.call_count,count+3)

    def test_presence_invalidates_available_status_when_plugin_or_binary_changes(self):
        executable=self.executable();description=self.description(path=executable);self.write_plugin(description)
        original=self.backend();count=self.ctx.call.call_count
        description['models']['values']=['revised-model'];self.write_plugin(description)
        pending=self.discover(presence=True)[0]
        self.assertEqual(pending.status,'checking');self.assertTrue(pending.error)
        self.assertNotEqual(pending.plugin_revision,original.plugin_revision);self.assertEqual(self.ctx.call.call_count,count)
        current=self.backend();self.assertIn('revised-model',current.models)
        self.executable(version='replaced binary');pending=self.discover(presence=True)[0]
        self.assertEqual(pending.status,'checking');self.assertTrue(pending.error)

    def test_model_cache_ttl_reprobes_instead_of_reusing_forever(self):
        self.executable();self.write_plugin(self.description());self.backend();count=self.ctx.call.call_count
        future=time.monotonic()+backend_plugins.MODEL_TTL+1
        with patch.object(backend_plugins.time,'monotonic',return_value=future):self.backend()
        self.assertEqual(self.ctx.call.call_count,count+1)

    def test_executable_and_model_cache_changes_reprobe_without_force(self):
        executable=self.executable();self.write_plugin(self.description(path=executable));self.backend();count=self.ctx.call.call_count
        self.executable(version='fixture-agent 1.2.4');self.assertEqual(self.backend().version,'fixture-agent 1.2.4')
        self.assertEqual(self.ctx.call.call_count,count+1)
        with patch.object(backend_adapters.ADAPTERS['generic'],'watch_paths',return_value=[self.root/'watched.json']):
            self.backend();before=self.ctx.call.call_count
            (self.root/'watched.json').write_text('{}',encoding='utf-8');self.backend()
            self.assertEqual(self.ctx.call.call_count,before+1)

    def test_cache_results_do_not_share_mutable_model_and_reasoning_state(self):
        self.executable();self.write_plugin(self.description());first=self.backend()
        first.models.append('caller-mutation');first.reasoning['fixture-model'].append('caller-effort')
        second=self.backend();self.assertNotIn('caller-mutation',second.models);self.assertNotIn('caller-effort',second.reasoning['fixture-model'])

    def test_path_updates_install_and_remove_cli_in_running_process(self):
        first_dir=self.root/'path-one';second_dir=self.root/'path-two'
        first=self.executable('supporter-isolated-test.exe','agent 1.0.0',first_dir)
        second=self.executable('supporter-isolated-test.exe','agent 2.0.0',second_dir)
        self.write_plugin(self.description(detect={'commands':['supporter-isolated-test.exe']}))
        with patch.dict(os.environ,{'PATH':str(first_dir)}):self.assertEqual(self.backend().path,str(first.resolve()))
        with patch.dict(os.environ,{'PATH':str(second_dir)}):self.assertEqual(self.backend().path,str(second.resolve()))
        with patch.dict(os.environ,{'PATH':str(self.root/'empty')}):self.assertEqual(self.backend().status,'missing')

    @unittest.skipUnless(os.name=='nt','Windows registry PATH behavior')
    def test_user_registry_path_changes_are_seen_without_restarting(self):
        import winreg
        one=self.root/'user-one';two=self.root/'user-two'
        first=self.executable('supporter-user-path-fixture.exe','agent 1.0.0',one)
        second=self.executable('supporter-user-path-fixture.exe','agent 2.0.0',two)
        self.write_plugin(self.description(detect={'commands':['supporter-user-path-fixture.exe']}))
        current=[str(one)]
        def open_key(hive,key):
            handle=MagicMock();handle.__enter__.return_value='user' if hive==winreg.HKEY_CURRENT_USER else 'machine';return handle
        def query(handle,key):return (current[0] if handle=='user' else '',winreg.REG_EXPAND_SZ)
        with patch('winreg.OpenKey',side_effect=open_key),patch('winreg.QueryValueEx',side_effect=query):
            self.assertEqual(self.backend().path,str(first.resolve()));current[0]=str(two)
            self.assertEqual(self.backend().path,str(second.resolve()));current[0]=''
            self.assertEqual(self.backend().status,'missing')

    def test_removal_disable_and_revision_changes_reject_old_generation_before_launch(self):
        description=self.actual_plugin();path=self.write_plugin(description);b=self.backend()
        path.unlink()
        with self.assertRaisesRegex(RuntimeError,'移除或停用'):self.generate(b)
        description['enabled']=False;self.write_plugin(description)
        with self.assertRaisesRegex(RuntimeError,'移除或停用'):self.generate(b)
        description['enabled']=True;description['generate']['args'].append('--changed');self.write_plugin(description)
        with self.assertRaisesRegex(RuntimeError,'配置已变化'):self.generate(b)
        self.ctx.launch.assert_not_called()

    def test_public_discovery_and_generate_dispatch_custom_adapter_without_builtin_changes(self):
        self.write_plugin(self.actual_plugin())
        with patch.object(backends,'ROOT',self.root),patch.object(backends,'call',side_effect=self.call),patch.object(backends,'launch',side_effect=self.launch):
            b=backends.discover_one('fixture');self.assertEqual(b.adapter,'generic');self.assertEqual(b.status,'available')
            result=json.loads(backends.generate(b,'fixture-a','custom dispatch',threading.Event(),reasoning='low'))
            self.assertEqual(result['stdin'],'custom dispatch')


if __name__=='__main__':unittest.main()
