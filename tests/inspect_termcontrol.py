"""Read-only terminal capability report. Never prints command text or executes it."""
import ctypes as C
from ctypes import wintypes as W
import json
from supporter.uia_native import automation,U,pattern,rectangle,prop
from supporter.terminal import parse_prompt

u=C.WinDLL('user32');u.GetClassNameW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
reports=[]
@C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
def visit(hwnd,param):
    cls=C.create_unicode_buffer(256);u.GetClassNameW(hwnd,cls,256)
    if not u.IsWindowVisible(hwnd) or 'cascadia' not in cls.value.lower():return True
    try:
        root=automation.ElementFromHandle(hwnd)
        nodes=root.FindAll(U.TreeScope_Descendants,automation.CreatePropertyCondition(U.UIA_ClassNamePropertyId,'TermControl'))
        for i in range(nodes.Length):
            node=nodes.GetElement(i);row={'hwnd':hwnd,'class':'TermControl','focused':bool(prop(node,'CurrentHasKeyboardFocus',False))}
            p2=pattern(node,U.UIA_TextPattern2Id,U.IUIAutomationTextPattern2)
            row['textPattern2']=bool(p2)
            p1=pattern(node,U.UIA_TextPatternId,U.IUIAutomationTextPattern)
            row['textPattern']=bool(p1)
            if p1:
                ranges=p1.GetSelection();row['selectionCount']=ranges.Length
                if ranges.Length:
                    r=ranges.GetElement(0);row['selectionLength']=len(r.GetText(2000) or '')
                    row['selectionRectangle']=rectangle(r)
                    expanded=r.Clone();expanded.ExpandToEnclosingUnit(U.TextUnit_Character);row['expandedRectangle']=rectangle(expanded)
                    row['collapsed']=r.CompareEndpoints(U.TextPatternRangeEndpoint_Start,r,U.TextPatternRangeEndpoint_End)==0
                    lr=r.Clone();lr.ExpandToEnclosingUnit(U.TextUnit_Line)
                    parsed1=parse_prompt(lr.GetText(2000) or '')
                    row['selectionLinePrompt']=parsed1 is not None
                    row['selectionLineShell']=parsed1['shell'] if parsed1 else None
                    row['selectionLineCommandLength']=len(parsed1['command']) if parsed1 else None
                    row['selectionLineCommandNonPaddingLength']=len(parsed1['command'].rstrip(' ')) if parsed1 else None
            if p2:
                active,caret=p2.GetCaretRange();row['caretActive']=bool(active);row['caretRectangle']=rectangle(caret)
                line=caret.Clone();line.ExpandToEnclosingUnit(U.TextUnit_Line)
                value=line.GetText(2000) or '';parsed=parse_prompt(value)
                row['lineLength']=len(value);row['promptRecognized']=parsed is not None
                row['shell']=parsed['shell'] if parsed else None
                row['commandLength']=len(parsed['command']) if parsed else None
            reports.append(row)
    except Exception as e:reports.append({'hwnd':hwnd,'error':type(e).__name__})
    return True
u.EnumWindows(visit,0)
print(json.dumps(reports,ensure_ascii=False,indent=2))
