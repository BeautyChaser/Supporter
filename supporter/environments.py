ENVIRONMENTS={
    'auto':'自动：根据输入控件判断格式，保持当前编辑内容',
    'bash':'Linux / Bash：使用 POSIX/Bash 命令，避免 PowerShell 与 cmd 语法',
    'powershell':'PowerShell：使用 cmdlet 与 PowerShell 引号、变量和管道规则',
    'cmd':'Windows cmd：使用 cmd.exe 命令与转义规则',
    'markdown':'Markdown 编辑：保留标题、列表、代码块与原始换行',
    'text':'普通文本：保留段落和换行，不强制命令格式',
    'code':'代码编辑：返回完整代码，保留缩进与换行',
}

def environment_instruction(name):
    if name not in ENVIRONMENTS:raise ValueError('未知对话环境：'+str(name))
    rules={
        'auto':'Infer the output format from the explicit request and current editor.',
        'bash':'Target syntax is Linux Bash/POSIX, even though the host runs Windows. Never substitute PowerShell or cmd syntax.',
        'powershell':'Target syntax is PowerShell. Use PowerShell cmdlets, variables, quoting and pipeline conventions.',
        'cmd':'Target syntax is Windows cmd.exe, not Bash or PowerShell.',
        'markdown':'This is a Markdown editing environment. Return complete Markdown source with real newline characters, lists, headings and intrinsic fenced code blocks preserved. Do not flatten lines. Use kind=text.',
        'text':'This is a plain text editing environment. Preserve paragraphs and real newlines. Use kind=text.',
        'code':'This is a code editor. Return complete code preserving indentation and real newlines. Do not wrap the entire result in extra Markdown fences. Use kind=text.',
    }
    return rules[name]
