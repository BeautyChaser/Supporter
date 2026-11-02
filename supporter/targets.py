"""Interpret accessibility metadata without treating webpage selections as editors."""
import re
from .terminal import parse_prompt

def describe_target(context,terminal=False):
    selection=context.get('selection','')
    editable=bool(context.get('editable'))
    scope='selection' if selection and editable else 'editor' if editable else 'reference' if selection else 'unavailable'
    text=selection if selection else context.get('text','') if editable else ''
    prompt=parse_prompt(context.get('line',''))
    command=prompt['command'] if prompt else None
    result={'context':text[:16000], 'scope':scope,'editor_id':context.get('editor_id'),
            'command':command,'editor_context':text[:16000],'editor_scope':scope,'shell':prompt['shell'] if prompt else None,
            'prompt_line':prompt['line'] if prompt else '','paste_mode':context.get('paste_mode','standard'),
            'supports_multiline':context.get('supports_multiline')}
    if terminal:
        result.update(context=command or '',scope='terminal-line' if command is not None else 'terminal-unknown')
    if len(text)>16000 and not terminal: result['scope']='too-large'
    return result
