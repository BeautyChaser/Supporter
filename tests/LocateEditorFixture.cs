// Isolated native edit-control fixture. Never launches a shell or sends input.
using System;
using System.Diagnostics;
using System.Drawing;
using System.Web.Script.Serialization;
using System.Windows.Forms;

public class LocateEditorFixture {
    class DecoyForm : Form {
        protected override bool ShowWithoutActivation { get { return true; } }
    }
    static TextBox Add(Form form, string id, string label, int top) {
        TextBox box = new TextBox();
        box.Name=id; box.AccessibleName=label; box.Text="fixture sentinel "+id;
        box.Location=new Point(24,top); box.Size=new Size(420,28);
        form.Controls.Add(box); return box;
    }
    [STAThread]
    public static void Main() {
        Application.EnableVisualStyles();
        Form main=new Form(); main.Text="Supporter isolated locate fixture";
        main.StartPosition=FormStartPosition.CenterScreen; main.Size=new Size(500,480);
        TextBox first=Add(main,"editable-first","Fixture editable first",24);
        TextBox multiline=Add(main,"editable-multiline","Fixture editable multiline",64);
        multiline.Multiline=true; multiline.Size=new Size(420,58);
        TextBox ro=Add(main,"readonly","Fixture readonly",134); ro.ReadOnly=true;
        TextBox password=Add(main,"password","Fixture password",174); password.UseSystemPasswordChar=true;
        TextBox disabled=Add(main,"disabled","Fixture disabled",214); disabled.Enabled=false;
        TextBox hidden=Add(main,"hidden","Fixture hidden",254); hidden.Visible=false;
        TextBox outside=Add(main,"offscreen","Fixture offscreen",10000);
        Button button=new Button();button.Name="nonedit-button";button.AccessibleName="Fixture nonedit button";
        button.Text="Non-editable button";button.Location=new Point(24,294);button.Size=new Size(240,30);main.Controls.Add(button);
        Label label=new Label();label.Name="readonly-label";label.AccessibleName="Fixture readonly label";
        label.Text="Read-only label";label.Location=new Point(24,334);label.Size=new Size(240,24);main.Controls.Add(label);
        Form decoy=new DecoyForm();decoy.Text="Supporter isolated locate decoy";decoy.Size=new Size(480,140);
        decoy.StartPosition=FormStartPosition.Manual;decoy.Location=new Point(80,80);
        Add(decoy,"other-window","Fixture other window",24);
        main.Shown+=(sender,args)=>{
            decoy.Show();main.Activate();first.Focus();
            Console.WriteLine(new JavaScriptSerializer().Serialize(new {
                hwnd=main.Handle.ToInt64(),decoyHwnd=decoy.Handle.ToInt64(),pid=Process.GetCurrentProcess().Id,
                title=main.Text,decoyTitle=decoy.Text
            }));Console.Out.Flush();
        };
        System.Windows.Forms.Timer deadline=new System.Windows.Forms.Timer();deadline.Interval=20000;
        deadline.Tick+=(sender,args)=>{deadline.Stop();main.Close();};deadline.Start();
        main.FormClosed+=(sender,args)=>{if(!decoy.IsDisposed)decoy.Close();};
        Application.Run(main);
    }
}
