"""UI Automation COM probe, including TextPattern2.GetCaretRange.

Runs in a disposable process so an unresponsive application cannot block the
desktop hotkey indefinitely. The explicit location-selection query may SetFocus;
it never sends keyboard, mouse, or text input.
"""
import json
from pathlib import Path
import re
import sys
import types
from .input_modes import browser_input_mode
from .paths import VENDOR_ROOT,ensure_runtime
sys.dont_write_bytecode=True
sys.path.insert(0,str(VENDOR_ROOT))
import comtypes
# Redirect the generated package before importing client: its import performs
# a writeability check and otherwise selects an installation/global cache.
gen_root=ensure_runtime()/'uia-gen';gen_root.mkdir(exist_ok=True)
generated=types.ModuleType('comtypes.gen');generated.__path__=[str(gen_root)]
sys.modules['comtypes.gen']=generated;comtypes.gen=generated
import comtypes.client

U=comtypes.client.GetModule('UIAutomationCore.dll')
automation=comtypes.client.CreateObject(U.CUIAutomation,interface=U.IUIAutomation)

def prop(el,name,default=None):
    try:return getattr(el,name)
    except Exception:return default

def bounds(el):
    r=prop(el,'CurrentBoundingRectangle')
    if r is None:return None
    return [float(r.left),float(r.top),float(r.right-r.left),float(r.bottom-r.top)]

def pattern(el,pattern_id,interface):
    try:return el.GetCurrentPattern(pattern_id).QueryInterface(interface)
    except Exception:return None

def metadata(el):
    return {'name':prop(el,'CurrentName','') or '','class':prop(el,'CurrentClassName','') or '',
            'automation_id':prop(el,'CurrentAutomationId','') or '','type':prop(el,'CurrentControlType',0),
            'focused':bool(prop(el,'CurrentHasKeyboardFocus',False)),'bounds':bounds(el)}

def runtime_id(el):
    try:return '-'.join(map(str,el.GetRuntimeId()))
    except Exception:return ''

def input_metadata(el):
    if prop(el,'CurrentIsPassword',False) or not prop(el,'CurrentIsEnabled',False) or prop(el,'CurrentIsOffscreen',True) or not prop(el,'CurrentIsKeyboardFocusable',False):return None
    m=metadata(el);r=m['bounds']
    if not r or r[2]<=0 or r[3]<=1:return None
    terminal=bool(re.search(r'xterm|termcontrol|terminal input|终端输入|输入终端',m['class']+' '+m['name']+' '+m['automation_id'],re.I))
    if not terminal and m['type'] not in (U.UIA_EditControlTypeId,U.UIA_DocumentControlTypeId):return None
    value=pattern(el,U.UIA_ValuePatternId,U.IUIAutomationValuePattern)
    editable=False
    if value:
        try:editable=not bool(value.CurrentIsReadOnly)
        except Exception:pass
    elif terminal:editable=True
    else:
        tp=pattern(el,U.UIA_TextPatternId,U.IUIAutomationTextPattern)
        if tp:
            try:ro=tp.DocumentRange.GetAttributeValue(U.UIA_IsReadOnlyAttributeId);editable=isinstance(ro,bool) and not ro
            except Exception:pass
    if not editable:return None
    identifier=runtime_id(el)
    if not identifier:return None
    return {'id':identifier,'name':m['name'][:120] or m['automation_id'][:120] or ('终端输入' if terminal else '未命名输入区'),
            'class':m['class'][:100],'bounds':r,'focused':m['focused'],'terminal':terminal}

def locate_inputs(root,query):
    nodes=root.FindAll(U.TreeScope_Subtree,automation.CreatePropertyCondition(U.UIA_IsKeyboardFocusablePropertyId,True));records=[]
    outer=bounds(root)
    for i in range(min(nodes.Length,1600)):
        node=nodes.GetElement(i);m=input_metadata(node)
        if not m:continue
        rect=m['bounds']
        if outer and (rect[0]+rect[2]<=outer[0] or rect[1]+rect[3]<=outer[1] or rect[0]>=outer[0]+outer[2] or rect[1]>=outer[1]+outer[3]):continue
        if query.get('focus_runtime_id'):
            if m['id']!=query['focus_runtime_id']:continue
            import ctypes
            native=ctypes.WinDLL('user32');native.GetForegroundWindow.restype=ctypes.c_void_p
            if native.GetForegroundWindow()!=int(query['hwnd']):return {'error':'原窗口焦点已切换，未更改输入位置'}
            node.SetFocus()
            if not prop(node,'CurrentHasKeyboardFocus',False):return {'error':'该输入区未接受键盘焦点'}
            return {'focused':True,'id':m['id']}
        records.append(m)
        if len(records)>=40:break
    if query.get('focus_runtime_id'):return {'error':'输入区已消失或不再可编辑，请重新定位'}
    records.sort(key=lambda m:(not m['focused'],m['bounds'][1],m['bounds'][0]))
    return {'controls':records,'limited':nodes.Length>1600 or len(records)>=40}

def rectangle(rng):
    try:
        values=rng.GetBoundingRectangles()
        if len(values)>=4 and values[3]>1:return [float(v) for v in values[:4]]
    except Exception:pass
    return None

def snapshot(query):
    el=automation.GetFocusedElement()
    if query.get('hwnd'):
        root=automation.ElementFromHandle(int(query['hwnd']))
        if query.get('locate_inputs') or query.get('focus_runtime_id'):return locate_inputs(root,query)
        if query.get('inspect'):
            nodes=root.FindAll(U.TreeScope_Descendants,automation.CreateTrueCondition())
            records=[]
            for i in range(min(nodes.Length,1200)):
                node=nodes.GetElement(i);m=metadata(node)
                if m['type'] in (U.UIA_EditControlTypeId,U.UIA_DocumentControlTypeId) or m['focused'] or re.search('xterm|terminal input|终端输入|TermControl',m['class']+' '+m['name'],re.I):records.append(m)
                if len(records)>=60:break
            return {'controls':records}
        if query.get('name'):
            el=root.FindFirst(U.TreeScope_Descendants,automation.CreatePropertyCondition(U.UIA_NamePropertyId,query['name']))
        elif query.get('class'):
            el=root.FindFirst(U.TreeScope_Descendants,automation.CreatePropertyCondition(U.UIA_ClassNamePropertyId,query['class']))
        elif query.get('focused'):
            el=root.FindFirst(U.TreeScope_Subtree,automation.CreatePropertyCondition(U.UIA_HasKeyboardFocusPropertyId,True))
    if not el or prop(el,'CurrentIsPassword',False):return None
    original=el;focus=metadata(el);chain=[];node=el
    for _ in range(7):
        if not node:break
        chain.append(metadata(node))
        try:node=automation.RawViewWalker.GetParentElement(node)
        except Exception:break
    terminal=any(re.search(r'xterm|termcontrol|terminal input|终端输入|输入终端',m['class']+' '+m['name']+' '+m['automation_id'],re.I) for m in chain)
    text_pattern=None;caret=None;caret_active=False
    # Keep the focused cell's rectangle even if its text provider is a parent.
    for depth in range(7):
        p2=pattern(el,U.UIA_TextPattern2Id,U.IUIAutomationTextPattern2)
        if p2:
            try:
                active,rng=p2.GetCaretRange()
                if active or query.get('name'):
                    caret=rng;caret_active=bool(active)
            except Exception:pass
        text_pattern=pattern(el,U.UIA_TextPatternId,U.IUIAutomationTextPattern)
        if text_pattern or caret:break
        if prop(el,'CurrentControlType')==U.UIA_WindowControlTypeId:break
        try:el=automation.RawViewWalker.GetParentElement(el)
        except Exception:break
        if not el:break
    if not el:return None
    value=pattern(original,U.UIA_ValuePatternId,U.IUIAutomationValuePattern)
    editable=prop(original,'CurrentControlType')==U.UIA_EditControlTypeId
    text='';selection='';line='';source='uia-editor';rect=None
    if value:
        editable=not bool(value.CurrentIsReadOnly)
        if editable and not terminal:text=value.CurrentValue or ''
    if text_pattern:
        if not value:
            try:
                ro=text_pattern.DocumentRange.GetAttributeValue(U.UIA_IsReadOnlyAttributeId)
                if isinstance(ro,bool):editable=not ro and bool(prop(el,'CurrentIsKeyboardFocusable',False))
            except Exception:pass
        if editable and not terminal and not value:text=text_pattern.DocumentRange.GetText(16001) or ''
        try:
            ranges=text_pattern.GetSelection()
            if ranges.Length:
                selected=ranges.GetElement(0);selection=selected.GetText(16001) or ''
                if caret is None:
                    collapsed=selected.CompareEndpoints(U.TextPatternRangeEndpoint_Start,selected,U.TextPatternRangeEndpoint_End)==0
                    if not terminal:
                        caret=selected.Clone();caret.MoveEndpointByRange(U.TextPatternRangeEndpoint_End,caret,U.TextPatternRangeEndpoint_Start)
                    elif collapsed and not selection:
                        # TermControl often implements TextPattern but not
                        # TextPattern2. Its genuinely collapsed selection is the
                        # cursor range; a nonempty output selection is NOT input.
                        caret=selected.Clone()
                        caret_active=bool(prop(original,'CurrentHasKeyboardFocus',False))
        except Exception:pass
    if caret:
        rect=rectangle(caret)
        if rect is None:
            try:
                expanded=caret.Clone();expanded.ExpandToEnclosingUnit(U.TextUnit_Character);rect=rectangle(expanded)
            except Exception:pass
        try:
            lr=caret.Clone();lr.ExpandToEnclosingUnit(U.TextUnit_Line);line=lr.GetText(2000) or ''
        except Exception:pass
        if rect:source='uia-caret-active' if caret_active else 'uia-selection'
    cell=focus['bounds']
    if terminal and cell and 0<cell[2]<=80 and 1<cell[3]<=100:
        # xterm synchronizes this hidden textarea's cell to its actual cursor.
        rect=cell;source='xterm-input-cell'
    if rect is None:
        rect=bounds(original)
        if not rect or rect[2]<=0 or rect[3]<=1:return None
        source='terminal-input' if terminal else 'uia-editor'
    try:editor_id='-'.join(map(str,el.GetRuntimeId()))
    except Exception:editor_id=''
    return {'x':rect[0]+(0 if terminal or source.startswith('uia-caret') else min(16,rect[2]/4)),
            'y':rect[1],'bottom':rect[1]+rect[3],'width':rect[2],'height':rect[3],
            'source':source,'text':text,'selection':selection,'line':line,'editable':editable,
            'terminal':terminal,'editor_id':editor_id,'focus':focus,'ancestors':chain[:4],
            'caret_active':caret_active,
            'paste_mode':browser_input_mode(prop(original,'CurrentFrameworkId',''),prop(original,'CurrentAriaProperties','') or '',
                ' '.join(m['class'] for m in chain),terminal),
            'supports_multiline':('multiline=true' in (prop(original,'CurrentAriaProperties','') or '').lower()) if prop(original,'CurrentFrameworkId','')=='Chrome' else None}

def main():
    sys.stdin.reconfigure(encoding='utf-8');sys.stdout.reconfigure(encoding='utf-8')
    for raw in sys.stdin:
        try:
            query=json.loads(raw) if raw.startswith('{') else {}
            result=snapshot(query)
        except Exception:result=None
        print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
