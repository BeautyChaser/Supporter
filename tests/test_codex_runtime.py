import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

from supporter.codex_runtime import CodexRuntime,CodexRuntimeError,server_arguments

ROOT=Path(__file__).resolve().parent.parent

class CodexRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.spawns=[];self.messages=[];self.environments=[];self.fixture_options={}
        def popen(args,**kwargs):
            self.spawns.append(args)
            self.environments.append(dict(kwargs['env']))
            process=subprocess.Popen([sys.executable,'-u',str(ROOT/'tests/codex_app_server_fixture.py'),json.dumps(self.fixture_options)],**kwargs)
            original=process.stdin;messages=self.messages
            class RecordingInput:
                def write(self,line):messages.append(json.loads(line));return original.write(line)
                def flush(self):return original.flush()
                def close(self):return original.close()
            process.stdin=RecordingInput()
            return process
        self.popen_factory=popen
        self.runtime=CodexRuntime(str(ROOT/'codex.exe'),popen_factory=popen)

    def tearDown(self):self.runtime.close()

    def test_reuse_process_but_separate_ephemeral_threads(self):
        progress=[]
        for _ in range(2):
            result=json.loads(self.runtime.generate('gpt-6-luna','hello',threading.Event(),reasoning='low',progress=progress.append))
            self.assertEqual(result['candidates'][0]['text'],'line one\nline two')
        self.assertEqual(len(self.spawns),1)
        self.assertEqual(self.runtime.last_metrics['processStarts'],1)
        self.assertEqual(self.runtime.last_metrics['initializeSeconds'],0)
        self.assertIn('已复用 Codex CLI 后台',progress)
        self.assertEqual(sum(m.get('method')=='initialize' for m in self.messages),1)
        threads=[m['params'] for m in self.messages if m.get('method')=='thread/start']
        self.assertEqual(len(threads),2)
        for params in threads:
            self.assertTrue(params['ephemeral']);self.assertEqual(params['sandbox'],'read-only');self.assertEqual(params['approvalPolicy'],'never')
            self.assertEqual(params['model'],'gpt-6-luna')
            self.assertEqual(params['config']['model_reasoning_effort'],'low')
        self.assertTrue(all(m['params']['effort']=='low' for m in self.messages if m.get('method')=='turn/start'))
        self.assertEqual(self.runtime.last_metrics['effectiveReasoning'],'low')

    def test_default_reports_inherited_cli_effort_without_overriding_it(self):
        progress=[]
        self.runtime.generate('gpt-6-luna','hello',threading.Event(),progress=progress.append)
        thread=next(m['params'] for m in self.messages if m.get('method')=='thread/start')
        turn=next(m['params'] for m in self.messages if m.get('method')=='turn/start')
        self.assertNotIn('model_reasoning_effort',thread['config'])
        self.assertNotIn('effort',turn)
        self.assertEqual(self.runtime.last_metrics['effectiveReasoning'],'xhigh')
        self.assertTrue(any('本次推理：极高' in value for value in progress),progress)
        self.assertFalse(any('model_reasoning_effort=' in value for value in self.spawns[0]))

    def test_default_handles_nested_or_unreported_effort_without_claiming_low(self):
        for shape,expected,label in [('nested','xhigh','极高'),('none','default','跟随 CLI（未报告档位）')]:
            with self.subTest(shape=shape):
                self.runtime.close();self.fixture_options['reportedEffortShape']=shape
                progress=[]
                self.runtime.generate('gpt-6-luna','hello',threading.Event(),progress=progress.append)
                self.assertEqual(self.runtime.last_metrics['effectiveReasoning'],expected)
                self.assertTrue(any('本次推理：'+label in value for value in progress),progress)

    def test_explicit_effort_is_per_thread_and_turn_when_switching(self):
        for effort in ['default','low','xhigh','none','default']:
            self.runtime.generate('gpt-6-luna','hello',threading.Event(),reasoning=effort)
            expected='xhigh' if effort=='default' else effort
            self.assertEqual(self.runtime.last_metrics['effectiveReasoning'],expected)
        self.assertEqual(len(self.spawns),1)
        threads=[m['params'] for m in self.messages if m.get('method')=='thread/start']
        turns=[m['params'] for m in self.messages if m.get('method')=='turn/start']
        self.assertEqual([t['config'].get('model_reasoning_effort') for t in threads],[None,'low','xhigh','none',None])
        self.assertEqual([t.get('effort') for t in turns],[None,'low','xhigh','none',None])

    def test_metrics_distinguish_startup_submission_and_first_text_delay(self):
        self.fixture_options.update(initializeDelay=.03,threadDelay=.04,turnDelay=.05)
        progress=[]
        self.runtime.generate('gpt-6-luna','delayed',threading.Event(),reasoning='low',progress=progress.append)
        metrics=dict(self.runtime.last_metrics)
        self.assertGreaterEqual(metrics['initializeSeconds'],.025)
        self.assertGreaterEqual(metrics['threadSeconds'],.035)
        self.assertGreaterEqual(metrics['turnSubmitSeconds'],.045)
        self.assertGreaterEqual(metrics['firstTextSeconds'],metrics['initializeSeconds']+metrics['threadSeconds']+metrics['turnSubmitSeconds']+.12)
        self.assertGreaterEqual(metrics['totalSeconds'],metrics['firstTextSeconds']+.035)
        self.assertEqual(metrics['retryCount'],0)
        self.assertEqual(metrics['effectiveReasoning'],'low')
        self.assertTrue(metrics['connection'])
        self.assertTrue(any('请求已提交，等待模型首字' in value for value in progress),progress)
        self.assertIn('Codex 开始返回文本',progress)
        self.runtime.generate('gpt-6-luna','hello',threading.Event(),reasoning='low')
        self.assertEqual(self.runtime.last_metrics['initializeSeconds'],0)

    def test_retry_count_and_progress_reset_between_turns(self):
        progress=[]
        self.runtime.generate('gpt-6-luna','retry',threading.Event(),reasoning='low',progress=progress.append)
        self.assertEqual(self.runtime.last_metrics['retryCount'],2)
        self.assertTrue(any('正在重试 · 1' in value for value in progress),progress)
        self.assertTrue(any('正在重试 · 2' in value for value in progress),progress)
        self.runtime.generate('gpt-6-luna','hello',threading.Event(),reasoning='low')
        self.assertEqual(self.runtime.last_metrics['retryCount'],0)

    def test_final_only_message_records_first_text_and_progress(self):
        for prompt in ['final-only','turn-final-only','empty-delta']:
            with self.subTest(prompt=prompt):
                progress=[]
                self.assertIn('line one',self.runtime.generate('gpt-6-luna',prompt,threading.Event(),reasoning='low',progress=progress.append))
                self.assertIsNotNone(self.runtime.last_metrics['firstTextSeconds'])
                self.assertEqual(progress.count('Codex 开始返回文本'),1)
                if prompt=='empty-delta':self.assertGreaterEqual(self.runtime.last_metrics['firstTextSeconds'],.12)

    def test_failed_request_does_not_retain_previous_success_metrics(self):
        self.runtime.generate('gpt-6-luna','hello',threading.Event(),reasoning='low')
        self.assertTrue(self.runtime.last_metrics['completed'])
        cancel=threading.Event();timer=threading.Timer(.15,cancel.set);timer.start()
        try:
            with self.assertRaisesRegex(CodexRuntimeError,'取消'):
                self.runtime.generate('gpt-6-luna','wait',cancel,reasoning='xhigh')
        finally:timer.join()
        metrics=self.runtime.last_metrics
        self.assertFalse(metrics['completed'])
        self.assertIsNone(metrics['firstTextSeconds'])
        self.assertEqual(metrics['effectiveReasoning'],'xhigh')
        self.assertEqual(metrics['initializeSeconds'],0)

    def test_fatal_model_error_is_not_silently_retried(self):
        progress=[]
        with self.assertRaisesRegex(CodexRuntimeError,'fixture request rejected'):
            self.runtime.generate('gpt-6-luna','fatal-error',threading.Event(),reasoning='low',progress=progress.append)
        self.assertFalse(any('正在重试' in value for value in progress),progress)
        self.assertIn('line one',self.runtime.generate('gpt-6-luna','hello',threading.Event(),reasoning='low'))

    def test_model_timeout_interrupts_and_next_request_reuses_background(self):
        self.runtime.warm()
        started=time.monotonic()
        with self.assertRaisesRegex(CodexRuntimeError,'模型响应超时'):
            self.runtime.generate('gpt-6-luna','wait',threading.Event(),reasoning='low',timeout=.18)
        self.assertLess(time.monotonic()-started,1.5)
        self.assertTrue(any(m.get('method')=='turn/interrupt' for m in self.messages))
        self.assertIn('line one',self.runtime.generate('gpt-6-luna','hello',threading.Event(),reasoning='low'))
        self.assertEqual(len(self.spawns),1)

    def test_cancel_during_turn_submission_closes_incomplete_transport(self):
        self.fixture_options['turnDelay']=.4
        cancel=threading.Event();results={}
        def request():
            try:results['value']=self.runtime.generate('gpt-6-luna','hello',cancel,reasoning='low')
            except CodexRuntimeError as error:results['error']=str(error)
        worker=threading.Thread(target=request);worker.start()
        deadline=time.monotonic()+3
        while not any(m.get('method')=='turn/start' for m in self.messages):
            self.assertLess(time.monotonic(),deadline);time.sleep(.01)
        started=time.monotonic();cancel.set();worker.join(timeout=2)
        self.assertFalse(worker.is_alive());self.assertLess(time.monotonic()-started,2)
        self.assertIn('取消',results.get('error',''))
        self.fixture_options['turnDelay']=0
        self.assertIn('line one',self.runtime.generate('gpt-6-luna','hello',threading.Event(),reasoning='low'))
        self.assertEqual(len(self.spawns),2)

    def test_long_wait_notice_reports_model_wait_and_remains_cancellable(self):
        progress=[];cancel=threading.Event()
        def report(value):
            progress.append(value)
            if value.startswith('等待模型首字 · '):cancel.set()
        started=time.monotonic()
        with self.assertRaisesRegex(CodexRuntimeError,'取消'):
            self.runtime.generate('gpt-6-luna','wait',cancel,reasoning='low',progress=report,timeout=12)
        self.assertGreaterEqual(time.monotonic()-started,8)
        self.assertLess(time.monotonic()-started,11)
        self.assertTrue(any(value.startswith('等待模型首字 · ') for value in progress),progress)
        self.assertTrue(any(m.get('method')=='turn/interrupt' for m in self.messages))

    def test_cancel_turn_then_new_request_still_works(self):
        cancel=threading.Event();timer=threading.Timer(.15,cancel.set);timer.start()
        with self.assertRaisesRegex(CodexRuntimeError,'取消'):
            self.runtime.generate('gpt-6-luna','wait',cancel)
        timer.join()
        self.assertIn('line one',self.runtime.generate('gpt-6-luna','hello',threading.Event()))
        self.assertEqual(len(self.spawns),1)

    def test_server_exit_recovers_on_next_generation(self):
        with self.assertRaises(CodexRuntimeError):self.runtime.generate(None,'crash',threading.Event())
        self.assertIn('line two',self.runtime.generate(None,'hello',threading.Event()))
        self.assertEqual(len(self.spawns),2)

    def test_model_switch_cancels_old_turn_without_crossing_results(self):
        old_cancel=threading.Event();results={}
        def old_request():
            try:results['old']=self.runtime.generate('gpt-6-luna','wait',old_cancel)
            except CodexRuntimeError as error:results['old']=str(error)
        old=threading.Thread(target=old_request);old.start()
        deadline=time.monotonic()+2
        while not any(m.get('method')=='turn/start' for m in self.messages):
            self.assertLess(time.monotonic(),deadline);time.sleep(.01)
        def new_request():results['new']=self.runtime.generate('gpt-6.1-sol','hello',threading.Event())
        new=threading.Thread(target=new_request);new.start();old_cancel.set()
        old.join(timeout=3);new.join(timeout=3)
        self.assertFalse(old.is_alive());self.assertFalse(new.is_alive())
        self.assertIn('取消',results['old']);self.assertIn('line one',results['new'])
        self.assertEqual(len(self.spawns),1)
        turns=[m['params'] for m in self.messages if m.get('method')=='turn/start']
        self.assertEqual([t['model'] for t in turns],['gpt-6-luna','gpt-6.1-sol'])

    def test_server_initiated_execution_is_denied(self):
        self.assertEqual(self.runtime.generate(None,'tool-request',threading.Event()),'cancel')

    def test_nontext_item_stops_the_runtime(self):
        with self.assertRaisesRegex(CodexRuntimeError,'commandExecution'):
            self.runtime.generate(None,'tool-event',threading.Event())

    def test_local_only_restrictions_do_not_replace_auth_or_model_provider(self):
        args=server_arguments(str(ROOT/'codex.exe'))
        self.assertIn('features.shell_tool=false',args)
        self.assertIn('features.plugins=false',args)
        self.assertIn('features.hooks=false',args)
        self.assertFalse(any(arg.startswith(('model_provider=','model_providers.','chatgpt_base_url=')) for arg in args))
        with self.assertRaises(CodexRuntimeError):server_arguments('codex.cmd')

    def test_connection_environment_only_affects_spawned_fixture(self):
        inherited={'HTTP_PROXY':'http://inherited.invalid:8900','https_proxy':'http://inherited.invalid:8901','CODEX_TEST_PRESERVED':'yes'}
        with patch.dict(os.environ,inherited):
            parent_environment=dict(os.environ)
            for connection in [{'mode':'inherit'},{'mode':'direct'},{'mode':'proxy','proxyUrl':'http://127.0.0.1:7890'}]:
                with self.subTest(mode=connection['mode']):
                    self.runtime.close()
                    self.runtime=CodexRuntime(str(ROOT/'codex.exe'),popen_factory=self.popen_factory,connection=connection)
                    self.runtime.warm()
                    child=self.environments[-1]
                    self.assertEqual(child['CODEX_TEST_PRESERVED'],'yes')
                    if connection['mode']=='inherit':
                        self.assertEqual(child,parent_environment)
                    elif connection['mode']=='direct':
                        self.assertFalse(any(name in child for name in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy']))
                    else:
                        self.assertTrue(all(child[name]=='http://127.0.0.1:7890' for name in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy']))
                    self.assertEqual(dict(os.environ),parent_environment)

if __name__=='__main__':unittest.main()
