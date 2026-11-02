using System;
using System.Globalization;
using System.Windows.Automation;
using System.Windows.Automation.Text;
using System.Web.Script.Serialization;
public class CaretProbe {
  static string N(double n) { return n.ToString(CultureInfo.InvariantCulture); }
  [STAThread] public static void Main() {
    Console.InputEncoding=new System.Text.UTF8Encoding(false);
    Console.OutputEncoding=new System.Text.UTF8Encoding(false);
    string request;
    while ((request=Console.ReadLine())!=null) {
      try {
        var el=AutomationElement.FocusedElement;
        // A scoped query is also used by local accessibility regression tests;
        // it never reads an unrelated foreground window.
        if(request.StartsWith("{")) {
          var query=new JavaScriptSerializer().Deserialize<System.Collections.Generic.Dictionary<string,object>>(request);
          var root=AutomationElement.FromHandle(new IntPtr(Convert.ToInt64(query["hwnd"])));
          if(Convert.ToString(query["name"])=="__test-inspect__") {
            var nodes=root.FindAll(TreeScope.Descendants,Condition.TrueCondition);
            var items=new System.Collections.Generic.List<object>();
            foreach(AutomationElement node in nodes) {
              items.Add(new {name=node.Current.Name,type=node.Current.ControlType.ProgrammaticName});
              if(items.Count>=40)break;
            }
            Console.WriteLine(new JavaScriptSerializer().Serialize(items));continue;
          }
          el=root.FindFirst(TreeScope.Descendants,new PropertyCondition(AutomationElement.NameProperty,Convert.ToString(query["name"])));
        }
        if(el==null) { Console.WriteLine("null"); continue; }
        if(el.Current.IsPassword) { Console.WriteLine("null"); continue; }
        object focusPattern;
        if(!el.TryGetCurrentPattern(TextPattern.Pattern,out focusPattern) &&
           !el.TryGetCurrentPattern(ValuePattern.Pattern,out focusPattern)) {
          // A page selection can leave focus on a static child. Find its text
          // provider, but still use IsReadOnly to prohibit modifying that page.
          var ancestor=el;
          for(int depth=0;depth<8;depth++) {
            ancestor=TreeWalker.RawViewWalker.GetParent(ancestor);
            if(ancestor==null) break;
            if(ancestor.Current.IsPassword) { Console.WriteLine("null"); goto NextRequest; }
            if(ancestor.TryGetCurrentPattern(TextPattern.Pattern,out focusPattern)) { el=ancestor; break; }
          }
        }
        object raw; bool isCaret=false;
        string text="",selection="",line="";
        bool editable=el.Current.ControlType==ControlType.Edit,hasValue=false;
        object val;
        if(el.TryGetCurrentPattern(ValuePattern.Pattern,out val)) {
          var vp=(ValuePattern)val;
          hasValue=true;
          editable=!vp.Current.IsReadOnly;
          if(editable) text=vp.Current.Value;
        }
        var rect=el.Current.BoundingRectangle;
        if(el.TryGetCurrentPattern(TextPattern.Pattern,out raw)) {
          // Chromium contenteditable controls often expose Document + TextPattern,
          // rather than ValuePattern. The readonly attribute distinguishes them
          // from selected text in the surrounding, non-editable web page.
          if(!hasValue) {
            try {
              var readOnly=((TextPattern)raw).DocumentRange.GetAttributeValue(TextPattern.IsReadOnlyAttribute);
              if(readOnly is bool) editable=!(bool)readOnly && el.Current.IsKeyboardFocusable;
            } catch { }
          }
          var ranges=((TextPattern)raw).GetSelection();
          if(editable && !hasValue) text=((TextPattern)raw).DocumentRange.GetText(16001);
          if(ranges.Length>0) {
            selection=ranges[0].GetText(16001);
            var lr=ranges[0].Clone(); lr.ExpandToEnclosingUnit(TextUnit.Line); line=lr.GetText(2000);
            var r=ranges[0].Clone();
            r.MoveEndpointByRange(TextPatternRangeEndpoint.End,r,TextPatternRangeEndpoint.Start);
            var rs=r.GetBoundingRectangles();
            if(rs.Length==0) { r.ExpandToEnclosingUnit(TextUnit.Character); rs=r.GetBoundingRectangles(); }
            if(rs.Length>0 && !rs[0].IsEmpty) { rect=rs[0]; isCaret=true; }
          }
        }
        // Browser empty editors expose their editable field rectangle even
        // when they cannot expose a collapsed text range.
        bool edit=el.Current.ControlType==ControlType.Edit || el.Current.ControlType==ControlType.Document;
        if(rect.IsEmpty || rect.Width<=0 || rect.Height<=0 || (!isCaret && !edit)) { Console.WriteLine("null"); continue; }
        double x=rect.Left+(isCaret?0:16), y=rect.Top;
        var result=new {
          x=x,y=y,bottom=isCaret?rect.Bottom:rect.Top+24,
          source=isCaret?"uia-caret":"uia-editor",text=text,selection=selection,line=line,
          editable=editable,editor_id=String.Join("-",el.GetRuntimeId())
        };
        Console.WriteLine(new JavaScriptSerializer().Serialize(result));
        NextRequest:;
      } catch(Exception error) {
        if(request.StartsWith("{")) Console.WriteLine(new JavaScriptSerializer().Serialize(new {error=error.GetType().Name,message=error.Message}));
        else Console.WriteLine("null");
      }
    }
  }
}
