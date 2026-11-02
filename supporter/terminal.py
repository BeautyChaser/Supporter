"""Recognize the editable prompt line without treating terminal history as input."""
import re

def parse_prompt(line):
    if not isinstance(line,str):return None
    line=line.rstrip('\r\n')
    if '\n' in line or '\r' in line:return None
    # Conda/venv prefixes and an empty command without a trailing space are valid.
    prefix=r'^(?:\([^\r\n()]*\)\s*)*'
    for kind,pattern in (
        ('powershell',prefix+r'PS\s+[^\r\n]*?>(?: ?)(.*)$'),
        ('cmd',prefix+r'[A-Za-z]:\\[^\r\n]*?>(?: ?)(.*)$'),
        ('posix',prefix+r'(?:\[[^\r\n\]]+@[^\r\n\]]+\](?::[^\r\n$#❯]*)?|[^\s\r\n$#❯]+@[^\r\n$#❯]*|(?:~|/)[^\r\n$#❯]*|[^\s\r\n$#❯]+:[~/][^\r\n$#❯]*|)[\$#❯](?: (.*)|())$'),
    ):
        match=re.match(pattern,line)
        if match:
            command=match.group(1) or ''
            start=match.start(1) if match.start(1)>=0 else len(line)
            if not command.strip(' '):command=''
            return {'shell':kind,'command':command,'prompt':line[:start],'line':line}
    return None
