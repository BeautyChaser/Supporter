import re

def browser_input_mode(framework,aria_properties,classes,terminal=False):
    """Soft breaks only for multiline browser text boxes, never code/terminal surfaces."""
    if framework!='Chrome' or terminal:return 'standard'
    if re.search(r'xterm|monaco|inputarea|codemirror|cm-content|ace_text|jp-|notebook',classes,re.I):return 'standard'
    return 'soft-lines' if 'multiline=true' in aria_properties.lower() else 'standard'
