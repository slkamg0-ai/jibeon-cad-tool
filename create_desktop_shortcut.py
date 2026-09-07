import os
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def create_shortcuts():
    repo_dir = Path(__file__).parent.resolve()
    bat_path = repo_dir / "start_web_studio.bat"
    ico_path = repo_dir / "app_icon.ico"
    
    if not bat_path.exists():
        print(f"Error: {bat_path} does not exist.")
        return False
    if not ico_path.exists():
        print(f"Error: {ico_path} does not exist.")
        return False

    desktop_dir = Path(os.environ.get("USERPROFILE", "C:/Users/princ2")) / "Desktop"
    
    # Target shortcuts
    targets = [
        desktop_dir / "NGII 지적도 CAD 스튜디오.lnk",
        repo_dir / "NGII 지적도 CAD 스튜디오.lnk"
    ]

    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        use_com = True
    except Exception:
        use_com = False

    for target in targets:
        try:
            if use_com:
                shortcut = shell.CreateShortCut(str(target))
                shortcut.TargetPath = str(bat_path)
                shortcut.WorkingDirectory = str(repo_dir)
                shortcut.IconLocation = f"{ico_path},0"
                shortcut.Description = "NGII 수치지형도 & VWorld 실시간 지적도 통합 Web CAD Studio"
                shortcut.WindowStyle = 1
                shortcut.Save()
            else:
                import subprocess
                ps_script = f"""
                $WshShell = New-Object -comObject WScript.Shell
                $Shortcut = $WshShell.CreateShortcut('{str(target)}')
                $Shortcut.TargetPath = '{str(bat_path)}'
                $Shortcut.WorkingDirectory = '{str(repo_dir)}'
                $Shortcut.IconLocation = '{str(ico_path)},0'
                $Shortcut.Description = 'NGII 수치지형도 & VWorld 실시간 지적도 통합 Web CAD Studio'
                $Shortcut.Save()
                """
                subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], check=True)
            print(f"[OK] 실행 아이콘 바로가기 생성 완료: {target}")
        except Exception as e:
            print(f"[ERROR] 바로가기 생성 실패 ({target}): {e}")

    return True

if __name__ == "__main__":
    create_shortcuts()
