import os
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def create_shortcuts():
    repo_dir = Path(__file__).parent.resolve()
    bat_local = repo_dir / "start_web_studio.bat"
    bat_tunnel = repo_dir / "start_with_cloudflare_tunnel.bat"
    ico_path = repo_dir / "app_icon.ico"
    
    if not ico_path.exists():
        print(f"Error: {ico_path} does not exist.")
        return False

    desktop_dir = Path(os.environ.get("USERPROFILE", "C:/Users/princ2")) / "Desktop"
    
    # Target shortcuts configuration: (shortcut_path, bat_path, description)
    shortcuts_to_create = [
        (
            desktop_dir / "NGII 지적도 CAD 스튜디오.lnk",
            bat_local,
            "NGII 수치지형도 & VWorld 실시간 지적도 통합 Web CAD Studio (로컬/사내망)"
        ),
        (
            desktop_dir / "NGII 지적도 CAD 스튜디오 (어디서나 웹접속).lnk",
            bat_tunnel,
            "NGII 수치지형도 & VWorld 통합 Studio - Cloudflare 보안 웹 터널 (외부 어디서나 접속)"
        ),
        (
            repo_dir / "NGII 지적도 CAD 스튜디오.lnk",
            bat_local,
            "NGII 수치지형도 & VWorld 실시간 지적도 통합 Web CAD Studio (로컬/사내망)"
        ),
        (
            repo_dir / "NGII 지적도 CAD 스튜디오 (어디서나 웹접속).lnk",
            bat_tunnel,
            "NGII 수치지형도 & VWorld 통합 Studio - Cloudflare 보안 웹 터널 (외부 어디서나 접속)"
        ),
    ]

    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        use_com = True
    except Exception:
        use_com = False

    for target, bat_target, desc in shortcuts_to_create:
        if not bat_target.exists():
            continue
        try:
            if use_com:
                shortcut = shell.CreateShortCut(str(target))
                shortcut.TargetPath = str(bat_target)
                shortcut.WorkingDirectory = str(repo_dir)
                shortcut.IconLocation = f"{ico_path},0"
                shortcut.Description = desc
                shortcut.WindowStyle = 1
                shortcut.Save()
            else:
                import subprocess
                ps_script = f"""
                $WshShell = New-Object -comObject WScript.Shell
                $Shortcut = $WshShell.CreateShortcut('{str(target)}')
                $Shortcut.TargetPath = '{str(bat_target)}'
                $Shortcut.WorkingDirectory = '{str(repo_dir)}'
                $Shortcut.IconLocation = '{str(ico_path)},0'
                $Shortcut.Description = '{desc}'
                $Shortcut.Save()
                """
                subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], check=True)
            print(f"[OK] 바로가기 생성 완료: {target.name}")
        except Exception as e:
            print(f"[ERROR] 바로가기 생성 실패 ({target.name}): {e}")

    return True

if __name__ == "__main__":
    create_shortcuts()
