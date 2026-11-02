"""Backend maintenance integration tests; all CLIs and windows are substitutes."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parent.parent

def alpha():return {'name':'alpha','models':['model-alpha']}
def beta():return {'name':'beta','models':['model-beta']}
def available(event):return {backend['name'] for backend in event['backends'] if not backend.get('error')}

class LifecycleSession:
    def __init__(self,directory,rows=None,poll_seconds='.1'):
        self.directory=Path(directory);self.events=[];self.inbox=queue.Queue()
        self.write_state(backends=[alpha()] if rows is None else rows)
        self.settings={'backend':'alpha','models':{'alpha':'model-alpha','beta':'model-beta'},
            'appearance':{'theme':'fixture-theme'},'fixturePreference':'keep-me'}
        (self.directory/'settings.json').write_text(json.dumps(self.settings),encoding='utf-8')
        self.child=subprocess.Popen([sys.executable,'-u','-m','tests.backend_lifecycle_fixture',str(directory),poll_seconds],
            cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        def read():
            for line in self.child.stdout:self.inbox.put(json.loads(line))
        self.reader=threading.Thread(target=read,daemon=True);self.reader.start()
    def write_state(self,**changes):
        file=self.directory/'backend-state.json'
        data=json.loads(file.read_text(encoding='utf-8')) if file.exists() else {}
        data.update(changes);temporary=file.with_suffix('.tmp')
        temporary.write_text(json.dumps(data),encoding='utf-8');temporary.replace(file)
    def send(self,**command):
        self.child.stdin.write(json.dumps(command)+'\n');self.child.stdin.flush()
    def receive(self,kind,predicate=lambda event:True,timeout=4):
        deadline=time.monotonic()+timeout
        while True:
            event=self.inbox.get(timeout=max(.01,deadline-time.monotonic()));self.events.append(event)
            if event['type']==kind and predicate(event):return event
            if time.monotonic()>deadline:raise AssertionError('missing event '+kind)
    def settle(self,seconds=.15):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            try:self.events.append(self.inbox.get(timeout=deadline-time.monotonic()))
            except queue.Empty:break
    def inventory(self,names,**kwargs):return self.receive('inventory',lambda event:available(event)==set(names),**kwargs)
    def generate(self,backend='alpha',model='complete',cid='request',history=None):
        self.send(type='generate',backend=backend,model=model,request='fixture request',history=history or [],client_request_id=cid)
    def release_scan(self,number):(self.directory/('scan-'+str(number)+'.release')).touch()
    def release_generation(self,model):(self.directory/(model+'.release')).touch()
    def close(self):
        if self.child.poll() is None:
            try:self.send(type='quit')
            except OSError:self.child.kill()
        try:self.child.wait(timeout=2)
        except subprocess.TimeoutExpired:self.child.kill();self.child.wait(timeout=2)
        self.reader.join(timeout=1)
        for stream in (self.child.stdin,self.child.stdout,self.child.stderr):
            try:stream.close()
            except OSError:pass

@contextmanager
def lifecycle_session(rows=None,poll_seconds='.1'):
    with tempfile.TemporaryDirectory(prefix='backend-lifecycle-',dir=ROOT/'.runtime') as directory:
        session=LifecycleSession(directory,rows,poll_seconds)
        try:
            session.receive('ready');session.inventory({row['name'] for row in ([alpha()] if rows is None else rows)})
            session.send(type='capture');session.receive('wake')
            yield session
        finally:session.close()

class BackendLifecycleTests(unittest.TestCase):
    def test_poll_automatically_adds_removes_and_falls_back_without_refresh(self):
        with lifecycle_session() as s:
            s.write_state(backends=[alpha(),beta()]);added=s.inventory({'alpha','beta'})
            self.assertEqual(added['reason'],'scan');self.assertEqual(added['settings']['backend'],'alpha')
            s.write_state(backends=[beta()]);removed=s.inventory({'beta'})
            self.assertEqual(removed['settings']['backend'],'beta')
            self.assertEqual(removed['settings']['fixturePreference'],'keep-me')
            self.assertEqual(removed['settings']['appearance'],{'theme':'fixture-theme'})
            self.assertEqual(removed['settings']['models']['beta'],'model-beta')

    def test_fallback_preserves_completed_candidate_and_subsequent_history(self):
        with lifecycle_session() as s:
            s.generate();result=s.receive('result')
            s.write_state(backends=[beta()]);s.inventory({'beta'})
            s.send(type='copy',response_id=result['response_id'],candidate_index=0)
            self.assertEqual(s.receive('copy-ready')['text'],'fixture result complete')
            s.generate('beta','next','next',[{'role':'user','content':'fixture-history-seed'}])
            started=s.receive('test-generation-started',lambda event:event['model']=='next')
            self.assertTrue(started['historyPresent']);self.assertEqual(s.receive('result')['client_request_id'],'next')

    def test_backend_removal_does_not_cancel_inflight_generation(self):
        with lifecycle_session() as s:
            s.generate(model='held-removal');s.receive('test-generation-started')
            s.write_state(backends=[beta()]);s.inventory({'beta'})
            s.release_generation('held-removal');finished=s.receive('test-generation-finished')
            self.assertFalse(finished['cancelled']);self.assertEqual(s.receive('result')['client_request_id'],'request')
            self.assertFalse(any(event['type']=='generation-stopped' for event in s.events))

    def test_no_available_backend_keeps_candidate_usable(self):
        with lifecycle_session() as s:
            s.generate();result=s.receive('result');s.write_state(backends=[])
            empty=s.receive('inventory',lambda event:not available(event) and event['settings'].get('backend')=='')
            self.assertEqual(empty['settings']['backend'],'')
            s.send(type='copy',response_id=result['response_id'],candidate_index=0)
            self.assertEqual(s.receive('copy-ready')['text'],'fixture result complete')

    def test_refreshes_coalesce_and_generation_does_not_wait_for_scan(self):
        with lifecycle_session() as s:
            s.write_state(holdScan=True);s.send(type='refresh')
            scanning=s.receive('test-scan-started',lambda event:event['number']>1)
            for _ in range(8):s.send(type='refresh')
            s.generate(model='during-scan',cid='during-scan');s.receive('test-generation-started',timeout=.8)
            self.assertEqual(s.receive('result',timeout=.8)['client_request_id'],'during-scan')
            s.write_state(holdScan=False);s.release_scan(scanning['number']);s.receive('test-scan-finished',lambda event:event['number']==scanning['number'])
            s.settle(.35)
            scans=[event for event in s.events if event['type']=='test-scan-started']
            self.assertTrue(all(event['active']==1 for event in scans),'no concurrent version/model scans')
            invalidations=sum(event['type']=='test-invalidated' for event in s.events)
            self.assertGreaterEqual(invalidations,1,'F5 invalidates the discovery cache')
            self.assertLessEqual(invalidations,2,'eight refreshes coalesce to at most one forced follow-up scan')

    def test_scan_result_applies_to_latest_settings(self):
        with lifecycle_session() as s:
            s.write_state(holdScan=True);s.send(type='refresh')
            scanning=s.receive('test-scan-started',lambda event:event['number']>1)
            changed={**s.settings,'appearance':{'theme':'changed-during-scan'},'fixturePreference':'new-value'}
            s.send(type='settings',settings=changed,request_id='save-during-scan');s.receive('settings-persisted')
            s.write_state(holdScan=False);s.release_scan(scanning['number'])
            updated=s.receive('inventory',lambda event:event['settings'].get('fixturePreference')=='new-value')
            self.assertEqual(updated['settings']['appearance'],{'theme':'changed-during-scan'})

    def test_cli_or_manifest_revision_change_gets_redetected_automatically(self):
        with lifecycle_session() as s:
            replacement={**alpha(),'version':'fixture2','revision':'rev2','models':['model-new']}
            s.write_state(backends=[replacement])
            updated=s.receive('inventory',lambda event:any(b['name']=='alpha' and b['version']=='fixture2' and not b['error'] for b in event['backends']))
            alpha_backend=next(b for b in updated['backends'] if b['name']=='alpha')
            self.assertEqual(alpha_backend['plugin_revision'],'rev2');self.assertIn('model-new',alpha_backend['models'])

    def test_selected_backend_stays_selected_during_revalidation_with_alternative(self):
        with lifecycle_session(rows=[alpha(),beta()]) as s:
            replacement={**alpha(),'version':'fixture2','revision':'rev2'}
            s.write_state(backends=[replacement,beta()],holdScan=True)
            checking=s.receive('inventory',lambda event:any(b['name']=='alpha' and b['status']=='checking' for b in event['backends']))
            self.assertEqual(checking['settings']['backend'],'alpha','checking must not persist an unrequested fallback')
            scanning=next((event for event in reversed(s.events) if event['type']=='test-scan-started' and event['number']>1),None)
            if scanning is None:scanning=s.receive('test-scan-started',lambda event:event['number']>1)
            s.write_state(holdScan=False);s.release_scan(scanning['number'])
            completed=s.receive('inventory',lambda event:any(b['name']=='alpha' and b['version']=='fixture2' and not b['error'] for b in event['backends']))
            self.assertEqual(completed['settings']['backend'],'alpha')

    def test_cancel_and_quit_work_while_background_scan_is_held(self):
        with lifecycle_session() as s:
            s.write_state(holdScan=True);s.send(type='refresh');s.receive('test-scan-started',lambda event:event['number']>1)
            s.generate(model='held-cancel');s.receive('test-generation-started')
            s.send(type='cancel-generation',client_request_id='request');s.receive('generation-stopped',timeout=.8)
            self.assertTrue(s.receive('test-generation-finished')['cancelled'])
            s.generate(model='held-quit',cid='quit');s.receive('test-generation-started',lambda event:event['model']=='held-quit')
            s.send(type='quit');s.receive('test-detection-stopped',timeout=.8)
            s.receive('test-process-stopped',timeout=.8);s.receive('test-runtimes-closed',timeout=.8)
            self.assertEqual(s.child.wait(timeout=1),0)

    def test_scan_error_does_not_break_candidate_or_future_polling(self):
        with lifecycle_session() as s:
            s.generate();result=s.receive('result')
            s.write_state(scanError=True);s.send(type='refresh')
            self.assertIn('deliberate',s.receive('backend-scan-error')['message'])
            s.send(type='copy',response_id=result['response_id'],candidate_index=0)
            self.assertEqual(s.receive('copy-ready')['text'],'fixture result complete')
            s.write_state(scanError=False,backends=[beta()]);self.assertEqual(s.inventory({'beta'})['settings']['backend'],'beta')

    def test_zero_poll_disables_periodic_scan_but_menu_refresh_still_works(self):
        with lifecycle_session(poll_seconds='0') as s:
            s.write_state(backends=[alpha(),beta()]);s.settle(.25)
            self.assertEqual(sum(event['type']=='test-scan-started' for event in s.events),1)
            s.send(type='refresh',force=False);self.assertEqual(available(s.inventory({'alpha','beta'})),{'alpha','beta'})
            self.assertFalse(any(event['type']=='test-invalidated' for event in s.events))


class BackendRegistryCacheTests(unittest.TestCase):
    @contextmanager
    def registry(self):
        from supporter import backend_plugins as plugins
        from supporter.backends import Backend,DEFAULT
        with tempfile.TemporaryDirectory(prefix='backend-cache-',dir=ROOT/'.runtime') as directory:
            directory=Path(directory);executable=directory/'fixture-cli.bin';executable.write_bytes(b'fixture-only-not-executable')
            manifest=directory/'fixture.json'
            data={'schemaVersion':1,'id':'fixture','label':'Fixture CLI','adapter':'generic',
                'detect':{'commands':[str(executable)],'versionArgs':['--version']},
                'models':{'values':['fixture-model']},'generate':{'args':[]}}
            manifest.write_text(json.dumps(data),encoding='utf-8');calls=[]
            def call(path,args,timeout=20):
                self.assertEqual(path,str(executable.resolve()));calls.append(list(args));return 'fixture 1.2.3'
            ctx=SimpleNamespace(Backend=Backend,DEFAULT=DEFAULT,ROOT=directory,call=call)
            with mock.patch.dict(os.environ,{'SUPPORTER_BACKEND_DIR':str(directory)}),mock.patch.object(plugins,'_cache',{}),mock.patch.object(plugins,'search_path',return_value=''):
                yield SimpleNamespace(api=plugins,ctx=ctx,calls=calls,manifest=manifest,data=data,executable=executable)

    def test_model_cache_and_fast_presence_do_not_reexecute_version(self):
        with self.registry() as fixture:
            api,ctx=fixture.api,fixture.ctx
            first=api.discover(ctx)[0];self.assertFalse(first.error);self.assertIn('fixture-model',first.models)
            api.discover(ctx);api.discover(ctx,presence=True)
            self.assertEqual(fixture.calls,[['--version']])
            api.invalidate();api.discover(ctx,presence=True)
            self.assertEqual(len(fixture.calls),1,'fast presence cannot execute version/model commands')
            api.discover(ctx);self.assertEqual(len(fixture.calls),2,'F5 expiry forces the next discovery')

    def test_remove_reinstall_and_upgrade_invalidate_file_signature(self):
        with self.registry() as fixture:
            api,ctx=fixture.api,fixture.ctx;api.discover(ctx)
            fixture.executable.unlink();missing=api.discover(ctx,presence=True)[0]
            self.assertEqual(missing.status,'missing');self.assertTrue(missing.error);self.assertEqual(len(fixture.calls),1)
            fixture.executable.write_bytes(b'fixture replacement version 2');api.discover(ctx)
            self.assertEqual(len(fixture.calls),2)

    def test_manifest_revision_and_bad_descriptor_are_reloaded(self):
        with self.registry() as fixture:
            api,ctx=fixture.api,fixture.ctx;first=api.discover(ctx)[0]
            fixture.data['models']['values']=['new-fixture-model'];fixture.manifest.write_text(json.dumps(fixture.data),encoding='utf-8')
            revised=api.discover(ctx)[0];self.assertNotEqual(first.plugin_revision,revised.plugin_revision)
            self.assertIn('new-fixture-model',revised.models);self.assertEqual(len(fixture.calls),2)
            fixture.manifest.write_text('{"schemaVersion":1,"id":"fixture","adapter":"unknown"}',encoding='utf-8')
            invalid=api.discover(ctx)[0];self.assertEqual(invalid.status,'plugin-error');self.assertTrue(invalid.error)
            self.assertEqual(len(fixture.calls),2,'invalid descriptors never invoke a CLI')

if __name__=='__main__':unittest.main()
