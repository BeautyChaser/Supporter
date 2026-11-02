"""Read only focused or named metadata from the explicitly supplied fixture."""
import json
import sys
from supporter.uia_native import automation,U,pattern,prop,snapshot

query=json.loads(sys.stdin.read())
if query.get('focused'):
    el=automation.GetFocusedElement()
    result=snapshot({})
else:
    root=automation.ElementFromHandle(int(query['hwnd']))
    el=root.FindFirst(U.TreeScope_Descendants,automation.CreatePropertyCondition(U.UIA_NamePropertyId,query['name']))
    result=snapshot({'hwnd':query['hwnd'],'name':query['name']})
if not el:raise RuntimeError('fixture element unavailable')
value=pattern(el,U.UIA_ValuePatternId,U.IUIAutomationValuePattern)
text=pattern(el,U.UIA_TextPatternId,U.IUIAutomationTextPattern)
readonly=None
if text:
    try:
        ro=text.DocumentRange.GetAttributeValue(U.UIA_IsReadOnlyAttributeId)
        readonly=ro if isinstance(ro,(bool,str,int,float)) else type(ro).__name__
    except Exception as error:readonly=type(error).__name__
print(json.dumps({
    'frameworkId':prop(el,'CurrentFrameworkId',''),
    'ariaRole':prop(el,'CurrentAriaRole',''),
    'ariaProperties':prop(el,'CurrentAriaProperties',''),
    'controlType':prop(el,'CurrentControlType',0),
    'className':prop(el,'CurrentClassName',''),
    'processId':prop(el,'CurrentProcessId',0),
    'valuePatternExists':bool(value),
    'textPatternExists':bool(text),
    'textReadonly':readonly,
    'valueReadonly':bool(value.CurrentIsReadOnly) if value else None,
    'isKeyboardFocusable':bool(prop(el,'CurrentIsKeyboardFocusable',False)),
    'hasKeyboardFocus':bool(prop(el,'CurrentHasKeyboardFocus',False)),
    'snapshotMode':result.get('paste_mode') if result else None,
    'snapshotSource':result.get('source') if result else None,
},ensure_ascii=False))
