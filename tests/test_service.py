import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager

class FixtureSession:
    def __init__(self,root,tmp):
        self.tmp=Path(tmp);self.events=[];self.inbox=queue.Queue()
        self.child=subprocess.Popen([sys.executable,'-u','-m','tests.service_fixture',tmp],cwd=root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        def read():
            for line in self.child.stdout:self.inbox.put(json.loads(line))
        self.reader=threading.Thread(target=read,daemon=True);self.reader.start()
    def send(self,**data):self.child.stdin.write(json.dumps(data)+'\n');self.child.stdin.flush()
    def receive(self,kind,predicate=lambda event:True):
        deadline=time.monotonic()+4
        while True:
            event=self.inbox.get(timeout=max(.01,deadline-time.monotonic()));self.events.append(event)
            if event['type']==kind and predicate(event):return event
    def settle(self,seconds=.12):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            try:event=self.inbox.get(timeout=deadline-time.monotonic());self.events.append(event)
            except queue.Empty:break
    def release(self,model):(self.tmp/(model+'.release')).touch()
    def location_mode(self,mode):(self.tmp/'locate-mode.txt').write_text(mode,encoding='utf-8')
    def generate(self,model,cid):self.send(type='generate',backend='codex',model=model,client_request_id=cid,request='fixture request',history=[])
    def close(self):
        if self.child.poll() is None:
            try:self.send(type='quit')
            except OSError:self.child.kill()
        try:self.child.wait(timeout=4)
        except subprocess.TimeoutExpired:self.child.kill();self.child.wait(timeout=2)
        self.reader.join(timeout=1)
        for stream in (self.child.stdin,self.child.stdout,self.child.stderr):
            try:stream.close()
            except OSError:pass

@contextmanager
def fixture_session():
    root=Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix='service-race-',dir=root/'.runtime') as tmp:
        session=FixtureSession(root,tmp)
        try:
            session.receive('ready');session.send(type='capture');session.receive('wake')
            yield session
        finally:session.close()

class ServiceIntegrationTests(unittest.TestCase):
    def test_location_lists_metadata_and_retargets_existing_result_without_inserting(self):
        with fixture_session() as s:
            s.generate('test-complete','complete');result=s.receive('result')
            s.send(type='locate-window',request_id='loc1');listing=s.receive('locate-results')
            self.assertEqual(listing['request_id'],'loc1');self.assertEqual(listing['title'],'Isolated locate fixture')
            self.assertEqual(len(listing['controls']),2);self.assertFalse(listing['limited'])
            self.assertEqual(next(e for e in s.events if e['type']=='test-list-inputs')['hwnd'],910001)
            for item in listing['controls']:
                self.assertEqual(set(item),{'id','name','class','bounds','focused','terminal'})
            s.send(type='locate-select',request_id='loc1',candidate_id='fixture-second')
            wake=s.receive('wake');self.assertTrue(wake['resume'])
            self.assertEqual(wake['target']['editor_id'],'fixture-second')
            self.assertEqual(wake['target']['hwnd'],910001)
            self.assertFalse(any(e['type']=='test-insert' for e in s.events))
            s.send(type='accept',response_id=result['response_id'],candidate_index=0)
            self.assertEqual(s.receive('test-insert')['text'],'printf test-complete');s.receive('accepted')

    def test_location_selection_preserves_active_generation(self):
        with fixture_session() as s:
            s.generate('test-held-locate','live');s.receive('test-generation-started')
            s.send(type='locate-window',request_id='loc1');s.receive('locate-results')
            s.send(type='locate-select',request_id='loc1',candidate_id='fixture-first');self.assertTrue(s.receive('wake')['resume'])
            s.release('test-held-locate');self.assertFalse(s.receive('test-generation-finished')['cancelled'])
            self.assertEqual(s.receive('result')['client_request_id'],'live')

    def test_location_rejects_stale_unknown_and_replayed_selection_without_focus(self):
        with fixture_session() as s:
            for rid in ('old','new'):
                s.send(type='locate-window',request_id=rid);s.receive('locate-results')
            for rid,identifier in [('old','fixture-first'),('new','outside-window-id')]:
                s.send(type='locate-select',request_id=rid,candidate_id=identifier)
                self.assertIn('过期',s.receive('locate-error')['message'])
            self.assertFalse(any(e['type']=='test-focus-input' for e in s.events))
            s.send(type='locate-select',request_id='new',candidate_id='fixture-first');s.receive('wake')
            s.send(type='locate-select',request_id='new',candidate_id='fixture-first');s.receive('locate-error')
            self.assertEqual(sum(e['type']=='test-focus-input' for e in s.events),1)

    def test_location_list_expires_on_fresh_capture_or_context_close(self):
        for action in ('capture','cancel'):
            with self.subTest(action=action),fixture_session() as s:
                s.send(type='locate-window',request_id='loc1');s.receive('locate-results')
                if action=='capture':s.send(type='capture',force=True);s.receive('wake')
                else:s.send(type='cancel',restore=False)
                s.send(type='locate-select',request_id='loc1',candidate_id='fixture-first');s.receive('locate-error')
                self.assertFalse(any(e['type']=='test-focus-input' for e in s.events))

    def test_location_empty_and_error_clear_previous_choices_but_preserve_candidate(self):
        with fixture_session() as s:
            s.generate('test-complete','complete');result=s.receive('result')
            s.send(type='locate-window',request_id='first');s.receive('locate-results')
            s.location_mode('empty');s.send(type='locate-window',request_id='empty')
            self.assertEqual(s.receive('locate-results')['controls'],[])
            s.send(type='locate-select',request_id='first',candidate_id='fixture-first');s.receive('locate-error')
            s.location_mode('error');s.send(type='locate-window',request_id='broken')
            self.assertIn('deliberate',s.receive('locate-error')['message'])
            s.send(type='locate-select',request_id='broken',candidate_id='fixture-first');s.receive('locate-error')
            self.assertFalse(any(e['type']=='test-focus-input' for e in s.events))
            s.send(type='copy',response_id=result['response_id'],candidate_index=0)
            self.assertEqual(s.receive('copy-ready')['text'],'printf test-complete')

    def test_location_focus_failure_can_retry_and_limited_flag_is_forwarded(self):
        with fixture_session() as s:
            s.location_mode('limited');s.send(type='locate-window',request_id='loc1')
            self.assertTrue(s.receive('locate-results')['limited'])
            s.location_mode('focus-error');s.send(type='locate-select',request_id='loc1',candidate_id='fixture-first')
            self.assertIn('focus error',s.receive('locate-error')['message'])
            s.location_mode('');s.send(type='locate-select',request_id='loc1',candidate_id='fixture-first')
            self.assertTrue(s.receive('wake')['resume'])

    def test_location_without_target_reports_error_and_never_enumerates(self):
        root=Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory(prefix='service-no-target-',dir=root/'.runtime') as tmp:
            s=FixtureSession(root,tmp)
            try:
                s.receive('ready');s.send(type='locate-window',request_id='no-target')
                self.assertEqual(s.receive('locate-error')['request_id'],'no-target')
                self.assertFalse(any(e['type']=='test-list-inputs' for e in s.events))
            finally:s.close()

    def test_stop_discards_late_result_and_does_not_block_next_request(self):
        with fixture_session() as s:
            s.generate('test-held-old','old');s.receive('test-generation-started')
            s.send(type='cancel-generation',client_request_id='old');s.receive('generation-stopped')
            s.release('test-held-old');s.receive('test-generation-finished');s.settle()
            self.assertFalse(any(e['type']=='result' and e.get('client_request_id')=='old' for e in s.events))
            s.generate('test-new','new');result=s.receive('result')
            self.assertEqual(result['client_request_id'],'new')
            self.assertEqual(result['text'],'printf test-new')

    def test_stop_discards_late_error_without_hiding_new_request(self):
        with fixture_session() as s:
            s.generate('test-held-old-error','old');s.receive('test-generation-started')
            s.send(type='cancel-generation',client_request_id='old');s.receive('generation-stopped')
            s.generate('test-new','new');s.receive('result')
            s.release('test-held-old-error');s.receive('test-generation-finished',lambda e:e['model']=='test-held-old-error');s.settle()
            self.assertFalse(any(e['type']=='error' and e.get('client_request_id')=='old' for e in s.events))

    def test_stale_stop_cannot_cancel_new_active_generation(self):
        with fixture_session() as s:
            s.generate('test-held-old','old');s.receive('test-generation-started')
            s.generate('test-held-new','new');s.receive('test-generation-started',lambda e:e['model']=='test-held-new')
            s.send(type='cancel-generation',client_request_id='old');s.receive('generation-stopped')
            s.release('test-held-new');finished=s.receive('test-generation-finished',lambda e:e['model']=='test-held-new')
            self.assertFalse(finished['cancelled'])
            result=s.receive('result');self.assertEqual(result['client_request_id'],'new')
            s.release('test-held-old')

    def test_result_arriving_before_stop_remains_acceptible(self):
        with fixture_session() as s:
            s.generate('test-complete','complete');result=s.receive('result')
            s.send(type='cancel-generation',client_request_id='complete');s.receive('generation-stopped')
            s.send(type='copy',response_id=result['response_id'],candidate_index=0)
            copied=s.receive('copy-ready')
            self.assertEqual(copied['text'],'printf test-complete')

    def test_stale_stop_does_not_invalidate_new_completed_result(self):
        with fixture_session() as s:
            s.generate('test-old','old');s.receive('result')
            s.generate('test-new','new');result=s.receive('result')
            s.send(type='cancel-generation',client_request_id='old');s.receive('generation-stopped')
            s.send(type='copy',response_id=result['response_id'],candidate_index=0)
            self.assertEqual(s.receive('copy-ready')['text'],'printf test-new')

    def test_suspend_preserves_generation_but_context_close_discards_result(self):
        with fixture_session() as s:
            s.generate('test-held-live','live');s.receive('test-generation-started')
            s.send(type='suspend');s.send(type='capture',force=True)
            self.assertTrue(s.receive('wake')['resume'])
            s.release('test-held-live');finished=s.receive('test-generation-finished')
            self.assertFalse(finished['cancelled']);result=s.receive('result')
            s.send(type='cancel',restore=False)
            s.send(type='copy',response_id=result['response_id'],candidate_index=0)
            self.assertIn('过期',s.receive('error')['message'])

    def test_readonly_handoff_branch_write_and_settings_receipt(self):
        root=Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory(prefix='service-test-',dir=root/'.runtime') as tmp:
            child=subprocess.Popen([sys.executable,'-u','-m','tests.service_fixture',tmp],cwd=root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
            inbox=queue.Queue()
            def read():
                for line in child.stdout:inbox.put(json.loads(line))
            reader=threading.Thread(target=read,daemon=True);reader.start()
            def send(**data):child.stdin.write(json.dumps(data)+'\n');child.stdin.flush()
            def receive(kind):
                for _ in range(12):
                    event=inbox.get(timeout=4)
                    if event['type']==kind:return event
                self.fail('missing event '+kind)
            try:
                receive('ready')
                send(type='capture');self.assertEqual(receive('wake')['target']['scope'],'reference')
                send(type='generate',backend='codex',request='Linux GPU 状态命令',history=[])
                result=receive('result');rid=result['response_id']
                send(type='accept',response_id=rid,candidate_index=1)
                self.assertEqual(receive('copy-ready')['text'],'rocm-smi')
                send(type='clipboard-written');send(type='capture')
                self.assertTrue(receive('wake')['resume'])
                send(type='accept',response_id=rid,candidate_index=1)
                inserted=receive('test-insert')
                self.assertEqual(inserted['text'],'rocm-smi');self.assertEqual(inserted['scope'],'editor');self.assertTrue(inserted['replace'])
                receive('accepted')
                send(type='accept',response_id=rid,candidate_index=1);self.assertIn('过期',receive('error')['message'])
                send(type='settings',settings={'backend':'codex'},request_id='save-1')
                self.assertEqual(receive('settings-persisted')['request_id'],'save-1')
                self.assertEqual(json.loads((Path(tmp)/'settings.json').read_text(encoding='utf-8')),{'backend':'codex'})
            finally:
                if child.poll() is None:
                    try:send(type='quit')
                    except OSError:child.kill()
                child.wait(timeout=5);reader.join(timeout=1)
                for stream in (child.stdin,child.stdout,child.stderr):
                    try:stream.close()
                    except OSError:pass

if __name__=='__main__':unittest.main()
