import os
import sys
import re
import time
import socket
import signal
import threading
import subprocess
import urllib.request
import webbrowser
from pathlib import Path

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).parent.resolve()
STUDIO_DIR = ROOT_DIR / "ngii_cad_studio"
CLOUDFLARED_EXE = ROOT_DIR / "cloudflared.exe"
URL_FILE = ROOT_DIR / "tunnel_url.txt"

CLOUDFLARED_DOWNLOAD_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"

def ensure_cloudflared() -> bool:
    """Ensure cloudflared.exe exists, download if missing."""
    if CLOUDFLARED_EXE.exists() and CLOUDFLARED_EXE.stat().st_size > 10_000_000:
        return True
    
    print("=" * 68)
    print("📥 Cloudflare Tunnel 실행 파일(cloudflared.exe)을 다운로드합니다...")
    print(f"   출처: {CLOUDFLARED_DOWNLOAD_URL}")
    print("=" * 68)
    try:
        urllib.request.urlretrieve(CLOUDFLARED_DOWNLOAD_URL, str(CLOUDFLARED_EXE))
        print("✅ cloudflared.exe 다운로드 완료!")
        return True
    except Exception as e:
        print(f"❌ cloudflared.exe 다운로드 실패: {e}")
        return False

def get_lan_ip() -> str:
    """Detect LAN IP address for local network sharing."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

def wait_for_port(port: int = 8000, timeout: float = 15.0) -> bool:
    """Wait until the local server starts accepting connections."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.3)
    return False

def start_server_in_thread():
    """Start Uvicorn server in a separate thread."""
    import uvicorn
    # Switch working directory to ngii_cad_studio
    os.chdir(str(STUDIO_DIR))
    if str(STUDIO_DIR) not in sys.path:
        sys.path.insert(0, str(STUDIO_DIR))
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, log_level="warning")

def run_tunnel():
    """Main launcher: starts local server & Cloudflare tunnel."""
    if not ensure_cloudflared():
        print("Cloudflare Tunnel을 시작할 수 없습니다.")
        sys.exit(1)

    port = 8000
    lan_ip = get_lan_ip()

    print("\n[1/3] NGII Map Studio 로컬 서버 기동 중...")
    server_thread = threading.Thread(target=start_server_in_thread, daemon=True)
    server_thread.start()

    if not wait_for_port(port, timeout=12.0):
        print("❌ 로컬 서버 기동 시간 초과 (Port 8000)")
        sys.exit(1)

    print("[2/3] 로컬 서버 기동 완료 (Port 8000 OK)")
    print("[3/3] Cloudflare 보안 터널(HTTPS) 연결 생성 중...")

    # Check for custom tunnel token in environment
    token = os.environ.get("CLOUDFLARE_TUNNEL_TOKEN", "").strip()
    if token:
        cmd = [str(CLOUDFLARE_EXE), "tunnel", "run", "--token", token]
    else:
        cmd = [str(CLOUDFLARED_EXE), "tunnel", "--url", f"http://localhost:{port}"]

    tunnel_proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace"
    )

    public_url = None

    def read_tunnel_output():
        nonlocal public_url
        try:
            for line in tunnel_proc.stdout:
                match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if match and not public_url:
                    public_url = match.group(0)
                    with open(URL_FILE, "w", encoding="utf-8") as f:
                        f.write(public_url)
                    
                    print("\n" + "=" * 72)
                    print("🚀 NGII Map Studio - Cloudflare 보안 웹 터널 활성화 완료!")
                    print("=" * 72)
                    print(f"  🏠 내 컴퓨터(로컬):     http://localhost:{port}")
                    print(f"  🏢 사내망/LAN 접속:     http://{lan_ip}:{port}")
                    print(f"  🌍 [외부 어디서나 접속]:  {public_url}")
                    print("=" * 72)
                    print("  ※ 공유기 포트포워딩 없이 외부 인터넷/스마트폰/노트북 어디서나 접속됩니다.")
                    print("  ※ 종단 간 암호화(HTTPS)가 적용되어 도면 데이터가 안전하게 보호됩니다.")
                    print(f"  ※ 주소 파일 저장됨: {URL_FILE}")
                    print("  ※ 종료하려면 콘솔 창에서 Ctrl + C 를 누르세요.")
                    print("=" * 72 + "\n")
                    sys.stdout.flush()

                    # Automatically open in browser
                    threading.Thread(target=lambda: (time.sleep(1.0), webbrowser.open(public_url)), daemon=True).start()
        except Exception:
            pass

    tunnel_thread = threading.Thread(target=read_tunnel_output, daemon=True)
    tunnel_thread.start()

    # Wait for tunnel URL or termination
    try:
        while True:
            time.sleep(1)
            if tunnel_proc.poll() is not None:
                print(f"Cloudflare 터널 프로세스가 종료되었습니다 (Code: {tunnel_proc.returncode})")
                break
    except KeyboardInterrupt:
        print("\n프로그램을 종료합니다...")
    finally:
        if tunnel_proc.poll() is None:
            tunnel_proc.terminate()
            try:
                tunnel_proc.wait(timeout=3)
            except Exception:
                tunnel_proc.kill()
        print("터널이 안전하게 종료되었습니다.")

if __name__ == "__main__":
    run_tunnel()
