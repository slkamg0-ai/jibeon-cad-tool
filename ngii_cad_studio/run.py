import sys
import os
import socket
import webbrowser
import threading
import time
from pathlib import Path

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Add project root to sys.path
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

def get_lan_ip():
    """Detect LAN IP address for team / intranet sharing."""
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

def open_browser():
    time.sleep(1.2)
    url = "http://127.0.0.1:8000"
    print(f"\n🌐 내 컴퓨터 브라우저를 엽니다: {url}\n")
    webbrowser.open(url)

if __name__ == "__main__":
    import uvicorn
    
    lan_ip = get_lan_ip()
    port = 8000
    
    print("=" * 68)
    print("🚀 NGII Map Studio - 통합 현황지적지형도 CAD 추출기 (사내망/팀 공유 모드)")
    print("=" * 68)
    print(f"  📌 내 컴퓨터 접속:    http://localhost:{port}")
    print(f"  🌐 팀원/사내망 접속:  http://{lan_ip}:{port}")
    print("=" * 68)
    print("  ※ 같은 사무실 Wi-Fi / 사내 네트워크의 동료들도 위 주소로 동시 사용 가능합니다.")
    print("  ※ 서비스를 종료하려면 콘솔 창에서 Ctrl + C 를 누르세요.")
    print("=" * 68 + "\n")
    
    # Auto-open browser in background thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
