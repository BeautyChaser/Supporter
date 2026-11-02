import unittest
from supporter.input_modes import browser_input_mode
from supporter.results import parse_response,conversation_prompt,wants_commands

class EnvironmentTests(unittest.TestCase):
    def test_markdown_in_terminal_generates_multiline_for_copy(self):
        self.assertFalse(wants_commands('输出多行 Markdown',True,environment='markdown'))
        result=parse_response('{"reply":"已生成","kind":"text","candidates":[{"text":"# 标题\\n\\n正文"}]}',terminal=True,environment='markdown')
        self.assertEqual(result['result'],'# 标题\n\n正文')
    def test_environment_constraints_are_sent_to_model(self):
        self.assertIn('Linux Bash/POSIX',conversation_prompt('',[],'查看显卡',False,'bash'))
        self.assertIn('PowerShell cmdlets',conversation_prompt('',[],'列目录',False,'powershell'))
        with self.assertRaises(ValueError):conversation_prompt('',[],'hello',False,'unknown')
    def test_multiline_browser_text_input_softlines(self):
        self.assertEqual(browser_input_mode('Chrome','multiline=true',''), 'soft-lines')
    def test_code_and_terminal_surfaces_never_get_shift_enter(self):
        for classes in ('monaco-editor inputarea','cm-content','xterm-helper-textarea','jp-InputArea'):
            self.assertEqual(browser_input_mode('Chrome','multiline=true',classes),'standard')
        self.assertEqual(browser_input_mode('Chrome','multiline=true','',True),'standard')
        self.assertEqual(browser_input_mode('Win32','multiline=true',''),'standard')

if __name__=='__main__':unittest.main()
