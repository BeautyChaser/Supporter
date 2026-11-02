import threading
import unittest
from unittest.mock import patch
from pathlib import Path
from supporter.backends import Backend, DEFAULT, command, generate, prompt_for, sanitize
from supporter.backends import parse_response,conversation_prompt

class CoreTests(unittest.TestCase):
    def test_reply_and_replacement_are_separate(self):
        result=parse_response('{"reply":"已改写","result":"原文的新版本"}')
        self.assertEqual(result['result'],'原文的新版本')
        with self.assertRaises(ValueError): parse_response('{"reply":"只有解释"}')

    def test_conversation_contains_original_and_history(self):
        result=conversation_prompt('原编辑文字',[{'role':'assistant','content':'上一回复'}],'再简短些',False)
        for part in ['原编辑文字','上一回复','再简短些','COMPLETE replacement']: self.assertIn(part,result)

    def test_reasoning_reaches_cli(self):
        class Process:
            returncode=0
            def communicate(self,data): return ('result','')
        b=Backend('hermes','fake',reasoning={DEFAULT:['high']})
        with patch('supporter.backends.launch',return_value=(Process(),None)) as launch:
            generate(b,DEFAULT,'hello',threading.Event(),reasoning='high')
            args=launch.call_args.args[1]
            self.assertEqual(args[args.index('--reasoning')+1],'high')
        with self.assertRaises(RuntimeError): generate(b,DEFAULT,'hello',threading.Event(),reasoning='ultra')

    def test_opencode_v2_reasoning_suffix(self):
        class Process:
            returncode=0
            def communicate(self,data): return ('{"type":"text","part":{"text":"ok"}}','')
        b=Backend('opencode','fake',reasoning={'provider/model':['high']},reasoning_style='model-suffix')
        with patch('supporter.backends.launch',return_value=(Process(),None)) as launch:
            generate(b,'provider/model','hello',threading.Event(),reasoning='high')
            self.assertIn('provider/model#high',launch.call_args.args[1])
    def test_terminal_never_submits_or_injects_escape_sequences(self):
        with self.assertRaises(ValueError):sanitize('echo hello\r\n\x1b\x00world\t done\n',True)
        self.assertEqual(sanitize('echo "two  spaces"',True),'echo "two  spaces"')

    def test_revision_preserves_previous_and_request(self):
        text = prompt_for('改成中文','previous candidate',False)
        self.assertIn('previous candidate',text)
        self.assertIn('改成中文',text)

    def test_native_arguments_preserve_shell_characters(self):
        prompt = '中文 "quoted" `whoami` $(whoami) & echo example'
        argv,data = command('agent.exe',['run',prompt])
        self.assertEqual(argv[-1],prompt)
        self.assertIsNone(data)

    def test_opencode_extracts_only_final_text(self):
        class Process:
            returncode=0
            def communicate(self,data):
                return ('{"type":"step_start"}\n{"type":"text","part":{"text":"echo hello"}}\n','')
        with patch('supporter.backends.launch',return_value=(Process(),None)):
            self.assertEqual(generate(Backend('opencode','fake'),DEFAULT,'request',threading.Event()),'echo hello')

    def test_hermes_provider_model_binding(self):
        class Process:
            returncode=0
            def communicate(self,data): return ('result','')
        with patch('supporter.backends.launch',return_value=(Process(),None)) as launch:
            generate(Backend('hermes','fake'),'deepseek :: deepseek-chat','hello',threading.Event())
            args=launch.call_args.args[1]
            self.assertEqual(args[args.index('--provider')+1],'deepseek')
            self.assertEqual(args[args.index('--model')+1],'deepseek-chat')

if __name__=='__main__': unittest.main()
