"""Regression tests for terminal prompt and input-anchor interpretation.

These are deterministic metadata tests, not claims of native shell support.
Physical UI Automation coverage lives in tests/terminal-fixture-app.
"""
import unittest
from supporter.terminal import parse_prompt
from supporter.targets import describe_target
from supporter.anchors import choose_anchor


class PromptTests(unittest.TestCase):
    def test_empty_conda_powershell_without_trailing_space(self):
        prompt=parse_prompt(r'(base) PS C:\Users\fixture-user>')
        self.assertEqual(prompt['shell'],'powershell')
        self.assertEqual(prompt['command'],'')

    def test_powershell_preserves_command_quotes_and_internal_spaces(self):
        prompt=parse_prompt(r'(base) PS C:\Program Files\work> Write-Output "a  b"')
        self.assertEqual(prompt['command'],'Write-Output "a  b"')

    def test_nested_environment_prefixes(self):
        prompt=parse_prompt(r'(base) (.venv) PS C:\work> Get-ChildItem')
        self.assertEqual(prompt['command'],'Get-ChildItem')

    def test_cmd_prompt_without_space(self):
        prompt=parse_prompt(r'C:\Users\name>dir')
        self.assertEqual(prompt['shell'],'cmd')
        self.assertEqual(prompt['command'],'dir')

    def test_bash_ssh_prompt(self):
        prompt=parse_prompt('[user@101 remote-linux]$ watch -n 2 nvidia-smi')
        self.assertEqual(prompt['shell'],'posix')
        self.assertEqual(prompt['command'],'watch -n 2 nvidia-smi')

    def test_bash_empty_prompt(self):
        self.assertEqual(parse_prompt('[user@host ~/work]$')['command'],'')

    def test_bash_venv_and_unicode_path(self):
        prompt=parse_prompt('(env) user@host:~/项目$ printf "两  格"')
        self.assertEqual(prompt['shell'],'posix')
        self.assertEqual(prompt['command'],'printf "两  格"')

    def test_command_operators_remain_part_of_input(self):
        prompt=parse_prompt(r'PS C:\work> Get-ChildItem | Where-Object Name -Like "a*>b"')
        self.assertEqual(prompt['command'],'Get-ChildItem | Where-Object Name -Like "a*>b"')

    def test_terminal_history_is_not_a_current_line(self):
        self.assertIsNone(parse_prompt('PS C:\\work> old\r\nold output\r\nPS C:\\work> new'))

    def test_wrapped_or_multiline_command_is_not_guessed(self):
        self.assertIsNone(parse_prompt('[user@host]$ command --long\ncontinued'))

    def test_ordinary_output_not_recognized(self):
        for value in ('Windows PowerShell','Command finished successfully','Temperature 42 C',''):
            with self.subTest(value=value):self.assertIsNone(parse_prompt(value))

    def test_command_and_output_markers_are_not_prompts(self):
        for value in ('export PRICE=$20','--output $HOME/path','finished # comment','Cost: $20'):
            with self.subTest(value=value):self.assertIsNone(parse_prompt(value))

    def test_terminal_right_padding_is_empty_but_snapshot_is_preserved(self):
        value=r'(base) PS C:\work>'+' '*80
        prompt=parse_prompt(value)
        self.assertEqual(prompt['command'],'')
        self.assertEqual(prompt['line'],value)


class TerminalTargetTests(unittest.TestCase):
    def test_empty_terminal_line_is_editable(self):
        target=describe_target({'line':r'(base) PS D:\Users\name>','terminal':True},terminal=True)
        self.assertEqual(target['scope'],'terminal-line')
        self.assertEqual(target['command'],'')
        self.assertEqual(target['shell'],'powershell')

    def test_unreadable_terminal_is_not_mistaken_for_empty_line(self):
        target=describe_target({'line':'','terminal':True},terminal=True)
        self.assertEqual(target['scope'],'terminal-unknown')
        self.assertIsNone(target['command'])

    def test_multiline_editor_keeps_newlines(self):
        value='# 标题\n\n第一段\n第二段\n'
        target=describe_target({'text':value,'editable':True})
        self.assertEqual(target['scope'],'editor')
        self.assertEqual(target['context'],value)

    def test_readonly_selection_remains_reference(self):
        target=describe_target({'selection':'说明\n下一行','editable':False})
        self.assertEqual(target['scope'],'reference')
        self.assertEqual(target['context'],'说明\n下一行')


class AnchorTests(unittest.TestCase):
    window=(0,0,1920,1080)

    def test_zero_height_native_caret_does_not_pin_to_top_left(self):
        result=choose_anchor({'x':0,'y':0,'width':0,'height':0},None,self.window)
        self.assertFalse(result['caret'])
        self.assertEqual(result['source'],'window-fallback')

    def test_xterm_cell_wins_over_stale_native_position(self):
        result=choose_anchor({'x':20,'y':30,'width':2,'height':16},
            {'x':1030,'y':600,'width':8,'height':20,'source':'xterm-input-cell'},self.window)
        self.assertEqual((result['x'],result['y']),(1030,600))

    def test_active_caret_wins_over_large_document_bounds(self):
        result=choose_anchor(None,{'x':650,'y':800,'width':0,'height':22,'source':'uia-caret-active'},self.window)
        self.assertTrue(result['caret'])
        self.assertEqual(result['y'],800)

    def test_root_document_is_not_labeled_as_editor(self):
        result=choose_anchor(None,{'x':0,'y':0,'width':1920,'height':1080,'source':'uia-editor'},self.window)
        self.assertFalse(result['caret'])

    def test_editor_field_rejects_native_caret_outside_its_bounds(self):
        result=choose_anchor({'x':30,'y':40,'height':16,'width':1},
            {'x':600,'y':900,'width':700,'height':90,'source':'uia-editor','focus':{'bounds':[600,900,700,90]}},self.window)
        self.assertEqual((result['x'],result['y']),(600,900))

    def test_negative_monitor_coordinates_preserved(self):
        result=choose_anchor(None,{'x':-1100,'y':700,'width':8,'height':20,'source':'xterm-input-cell'},(-1920,0,0,1080))
        self.assertEqual(result['x'],-1100)

    def test_outside_window_rectangle_is_not_used(self):
        result=choose_anchor(None,{'x':5000,'y':900,'width':8,'height':20,'source':'xterm-input-cell'},self.window)
        self.assertFalse(result['caret'])


if __name__=='__main__':unittest.main()
