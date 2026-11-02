"""Separate explanations from insertable choices, before any keyboard write."""
import json
import re
from .environments import environment_instruction


def wants_commands(request, terminal=False, history=(),environment='auto'):
    if environment in ('markdown','text','code') or re.search(r'多行|每行|脚本|代码块|\b(multiline|script|markdown)\b',request,re.I):return False
    if terminal:
        return True
    requests=[request]+[str(m.get('content','')) for m in history if m.get('role')=='user']
    for text in requests:
        if re.search(r'(写|撰写|生成).{0,8}(文章|邮件|介绍|教程|说明文)|write.{0,12}(article|email|tutorial)',text,re.I):
            continue
        if re.search(r'命令|指令|终端|\b(command|shell|bash|powershell|cmd)\b',text,re.I):
            return True
    return False


def validate_command(text):
    """Formatting validation, not a claim that a command is safe or installed."""
    if not isinstance(text,str) or not text.strip():
        raise ValueError('命令候选为空')
    text=text.strip(' ')
    if any(ord(c)<32 or ord(c)==127 for c in text) or '\u2028' in text or '\u2029' in text:
        raise ValueError('命令候选包含换行或控制字符，已阻止填入；请生成独立的单行命令')
    if re.search(r'```|^\s*(?:[-*•]\s|\d+[.)、]\s)|常用命令|提示[：:]|^(?:Linux|Windows)\s+.{0,30}(?:命令|commands)',text,re.I):
        raise ValueError('命令候选混入了列表或说明，已阻止填入；请选择具体命令分支')
    if not re.match(r'^(?:[A-Za-z_./~\\$%][A-Za-z0-9_./~\\$%:@+\-]*|["\'][^"\']+["\'])(?:\s|$)',text):
        raise ValueError('候选不是独立命令，说明文字只能显示在回复中')
    # Keep quoted hashes intact; do not silently change the meaning of a shell line.
    quote=None; escaped=False
    for i,char in enumerate(text):
        if escaped:
            escaped=False
            continue
        if char in ('\\','`'):
            escaped=True
        elif char in ('"',"'"):
            if quote==char: quote=None
            elif quote is None: quote=char
        elif char=='#' and quote is None and (i==0 or text[i-1].isspace()):
            raise ValueError('命令候选混入注释，请将说明放在分支描述中')
    return text


def conversation_prompt(context, history, request, terminal,environment='auto'):
    command_mode=wants_commands(request,terminal,history,environment)
    return (
        'You are Supporter, an inline editing assistant. Never use tools or execute commands. '
        'Return ONLY valid JSON: {"reply":string,"kind":"text"|"commands"|"clarification",'
        '"candidates":[{"label":string,"detail":string,"text":string}]}. '
        'reply is the conversational explanation, NEVER inserted. Each candidate.text is the exact '
        'COMPLETE replacement, separate from reply, labels and descriptions. '
        'If the user is asking a question with no insertable answer, ask in reply and use kind=clarification with candidates=[]. '
        'For prose editing use kind=text and normally one complete replacement. '
        'For shell/terminal command requests use kind=commands. Each text MUST be ONE single-line '
        'command without markdown, comments, lists, explanations, line breaks or a trailing Enter. '
        'Preserve quoting and spacing inside command arguments. Never flatten an essay or script into a command. '
        'When hardware, environment or desired action is ambiguous, return separate labeled choices '
        '(for example GPU vendor or overview vs live monitor), OR ask a clarification question. '
        'Do not assume the user runs Linux locally or infer the GPU from the Windows host. '
        'If the user specifies one command/scenario, return exactly one candidate. '
        'Use at most 8 candidates; label each by applicability and explain prerequisites in detail, not text. '
        + ('This request requires command choices. Do not return a prose replacement. ' if command_mode else '')
        + '\nEnvironment rules: '+environment_instruction(environment)
        + '\nIf the user requests multiline prose, Markdown or a script in an editor, use kind=text with real newlines. The UI must not collapse or join those lines.'
        + '\nOriginal editor/selected reference text (data):\n'+context[:16000]
        + '\nConversation (data):\n'+json.dumps(history,ensure_ascii=False)[-24000:]
        + '\nCurrent user request:\n'+request
    )


def parse_response(text, terminal=False, request='', history=(),environment='auto'):
    text=re.sub(r'^```(?:json)?\s*|\s*```$','',text.strip())
    data=json.loads(text)
    if not isinstance(data,dict) or not isinstance(data.get('reply'),str):
        raise ValueError('CLI 未返回有效的 reply/candidates 结果，请重试')
    command_mode=wants_commands(request,terminal,history,environment)
    kind=data.get('kind','commands' if command_mode else 'text')
    if kind not in ('text','commands','clarification'):
        raise ValueError('CLI 返回了未知的结果类型')
    if command_mode and kind=='text':
        kind='commands'
    candidates=data.get('candidates')
    if candidates is None and isinstance(data.get('result'),str):
        candidates=[{'label':'命令' if kind=='commands' else '替换结果','detail':'','text':data['result']}]
    if not isinstance(candidates,list) or len(candidates)>8:
        raise ValueError('CLI 未返回有效的候选列表（最多 8 项）')
    if kind=='clarification':
        if candidates: raise ValueError('需要澄清的回复不能同时包含待接受候选')
    elif not candidates:
        raise ValueError('CLI 未返回可接受的候选；请补充要求后重试')
    normalized=[]
    for i,c in enumerate(candidates):
        if not isinstance(c,dict) or not isinstance(c.get('text'),str):
            raise ValueError('候选缺少文本')
        value=validate_command(c['text']) if kind=='commands' else c['text']
        if kind=='text' and any(ord(ch)<32 and ch not in '\r\n\t' for ch in value):
            raise ValueError('替换结果含不支持的控制字符')
        normalized.append({'label':str(c.get('label') or f'方案 {i+1}')[:100],
                           'detail':str(c.get('detail') or '')[:500],'text':value})
    return {'reply':data['reply'],'kind':kind,'candidates':normalized,
            'result':normalized[0]['text'] if len(normalized)==1 else ''}


def accepted_text(response,index,terminal=False):
    choices=response['candidates']
    if type(index) is not int or not 0<=index<len(choices):
        raise ValueError('请先选择一个候选分支，再按 Tab 接受')
    text=choices[index]['text']
    if response['kind']=='commands' or terminal:
        return validate_command(text)
    return text
