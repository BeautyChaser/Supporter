import json
import unittest
from supporter.results import parse_response, accepted_text, wants_commands, validate_command
from supporter.targets import describe_target

class ResultTests(unittest.TestCase):
    def test_gpu_scenarios_remain_independent(self):
        data={'reply':'按显卡类型选择。','kind':'commands','candidates':[
            {'label':'NVIDIA','detail':'需要驱动','text':'nvidia-smi'},
            {'label':'AMD','detail':'ROCm 环境','text':'rocm-smi'}]}
        result=parse_response(json.dumps(data),request='我要 linux 查看 gpu 状态的命令')
        self.assertEqual(result['result'],'')
        self.assertEqual(accepted_text(result,1),'rocm-smi')
        self.assertNotIn('按显卡',accepted_text(result,0))
        with self.assertRaises(ValueError):accepted_text(result,-1)
        with self.assertRaises(ValueError):accepted_text(result,None)

    def test_user_reported_flattened_essay_is_not_a_command(self):
        payload={'reply':'说明','result':'Linux 查看 GPU 状态的常用命令：1) NVIDIA 显卡 nvidia-smi # 查看温度 2) AMD 显卡 rocm-smi 提示：安装驱动'}
        with self.assertRaises(ValueError):parse_response(json.dumps(payload),request='查看GPU命令')

    def test_no_multiline_or_control_character_flattening(self):
        for invalid in ['nvidia-smi\nrocm-smi','nvidia-smi\r','echo a\x1b[0m','nvidia-smi # 查看显卡','```sh\nnvidia-smi\n```']:
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):validate_command(invalid)

    def test_spaces_quotes_pipelines_and_wraps_keep_meaning(self):
        for value in ['printf "two  spaces"',"echo '#literal'",'lspci | grep -i -E "vga|3d|display"','nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv']:
            self.assertEqual(validate_command(value),value)

    def test_single_command_followup_retains_command_intent(self):
        history=[{'role':'user','content':'我要查看gpu的命令'}]
        self.assertTrue(wants_commands('只给出一个',history=history))
        result=parse_response('{"reply":"查看概览","result":"nvidia-smi"}',request='只给出一个',history=history)
        self.assertEqual(result['kind'],'commands')

    def test_clarification_cannot_be_pasted(self):
        result=parse_response('{"reply":"你使用哪种显卡？","kind":"clarification","candidates":[]}',request='GPU状态命令')
        with self.assertRaises(ValueError):accepted_text(result,0)

    def test_multiline_prose_is_preserved_outside_terminal(self):
        result=parse_response('{"reply":"改好了","result":"第一段\\n第二段"}')
        self.assertEqual(accepted_text(result,0),'第一段\n第二段')
        with self.assertRaises(ValueError):accepted_text(result,0,terminal=True)

    def test_readonly_selection_is_reference_not_editor(self):
        target=describe_target({'selection':'页面已发布内容','editable':False})
        self.assertEqual(target['scope'],'reference')
        self.assertEqual(target['context'],'页面已发布内容')

    def test_editable_selection_and_empty_input(self):
        self.assertEqual(describe_target({'selection':'原文','editable':True})['scope'],'selection')
        self.assertEqual(describe_target({'text':'','editable':True})['scope'],'editor')
        self.assertEqual(describe_target({})['scope'],'unavailable')

if __name__=='__main__':unittest.main()
