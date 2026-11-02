"""Targeted UIA SetValue experiment restricted to a named local fixture control."""
import json
import sys
from supporter.uia_native import automation,U,pattern,prop

data=json.loads(sys.stdin.read())
root=automation.ElementFromHandle(int(data['hwnd']))
if prop(root,'CurrentProcessId')!=int(data['processId']):raise RuntimeError('fixture process mismatch; no write')
el=root.FindFirst(U.TreeScope_Descendants,automation.CreatePropertyCondition(U.UIA_NamePropertyId,data['name']))
if not el or prop(el,'CurrentProcessId')!=int(data['processId']):raise RuntimeError('fixture element mismatch; no write')
if prop(el,'CurrentIsPassword',False):raise RuntimeError('password controls excluded')
value=pattern(el,U.UIA_ValuePatternId,U.IUIAutomationValuePattern)
if not value or value.CurrentIsReadOnly:raise RuntimeError('fixture has no writable ValuePattern')
value.SetValue(data['text'])
print(json.dumps({'setValueReturned':True,'readBackLength':len(value.CurrentValue or '')}))
