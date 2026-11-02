using System;
using System.IO;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using System.Threading;
public class PasteBridge {
  [STAThread] public static void Main(string[] args) {
    Console.InputEncoding=new UTF8Encoding(false);Console.OutputEncoding=new UTF8Encoding(false);
    if(args.Length==1 && args[0]=="--self-test") {Console.WriteLine("{\"ready\":true,\"clipboardUntouched\":true}");return;}
    try {
      var input=new JavaScriptSerializer().Deserialize<System.Collections.Generic.Dictionary<string,string>>(Console.ReadLine());
      Clipboard.SetDataObject(new DataObject(DataFormats.UnicodeText,input["text"]),true,5,25);
      Console.WriteLine("ready");Console.Out.Flush();
      // The parent injects Ctrl+V. Keep the accepted result on the clipboard:
      // some editors retrieve paste data asynchronously after the key event.
      var consumed=new ManualResetEventSlim(false);
      ThreadPool.QueueUserWorkItem(delegate {try {Console.ReadLine();}finally {consumed.Set();}});
      while(!consumed.Wait(10))Application.DoEvents();
      for(int i=0;i<10;i++){Application.DoEvents();Thread.Sleep(10);}
    } catch(Exception error) {Console.WriteLine("error:"+error.Message);}
    finally {
      Console.WriteLine("done");Console.Out.Flush();
    }
  }
}
