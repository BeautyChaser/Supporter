import argparse
import json
import sys

def main():
    parser = argparse.ArgumentParser(description='Supporter 全键盘全局输入助手')
    parser.add_argument('--diagnose',action='store_true',help='检测 CLI 和模型，不打开界面')
    args = parser.parse_args()
    if args.diagnose:
        from supporter.backends import discover
        from dataclasses import asdict
        print(json.dumps([asdict(b) for b in discover()],ensure_ascii=False,indent=2))
        return
    if sys.platform != 'win32':
        parser.error('Supporter 全局快捷键目前支持 Windows')
    import subprocess
    from pathlib import Path
    root=Path(__file__).resolve().parent
    subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(root/'start.ps1')],check=True)

if __name__ == '__main__':
    main()
