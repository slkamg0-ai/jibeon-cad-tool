"""NGII Map Studio 를 폰/외부에서 접속할 수 있게 띄운다.

접속 경로는 두 가지이고 Tailscale 을 먼저 시도한다.

  1) Tailscale   이 PC 의 테일넷 주소로 직접 붙는다. 폰에 Tailscale 앱만 켜져 있으면
                 LTE 로도 접속되고 인터넷에 공개되지 않는다.
  2) Cloudflare  무계정 quick tunnel. 다만 Cloudflare 가 발급한 호스트명을 DNS 에
                 올려주지 않는 경우가 있어(터널은 등록되는데 NXDOMAIN) 주소를 알리기
                 전에 실제로 조회되는지 확인한다.

환경변수 SHARE=cloudflare 로 강제 지정할 수 있다.
"""

import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

# Windows 콘솔 UTF-8 출력
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

ROOT_DIR = Path(__file__).parent.resolve()
STUDIO_DIR = ROOT_DIR / "ngii_cad_studio"
CLOUDFLARED_EXE = ROOT_DIR / "cloudflared.exe"
def get_safe_port() -> int:
    env_port = os.environ.get("NGII_PORT")
    if env_port:
        return int(env_port)
    for p in (8088, 8089, 8090, 8080, 8888, 8000):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return 8088

PORT = get_safe_port()

sys.path.insert(0, str(ROOT_DIR))
import share  # noqa: E402

CLOUDFLARED_DOWNLOAD_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/"
    "cloudflared-windows-amd64.exe"
)


def ensure_cloudflared() -> bool:
    if CLOUDFLARED_EXE.exists() and CLOUDFLARED_EXE.stat().st_size > 10_000_000:
        return True
    print("=" * 68)
    print("Cloudflare Tunnel 실행 파일(cloudflared.exe)을 내려받습니다…")
    print(f"  출처: {CLOUDFLARED_DOWNLOAD_URL}")
    print("=" * 68)
    try:
        urllib.request.urlretrieve(CLOUDFLARED_DOWNLOAD_URL, str(CLOUDFLARED_EXE))
        print("cloudflared.exe 다운로드 완료")
        return True
    except Exception as exc:
        print(f"cloudflared.exe 다운로드 실패: {exc}")
        return False


def get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def wait_for_port(port: int, timeout: float = 15.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/crs-list", headers={"User-Agent": "HealthCheck"})
            with urllib.request.urlopen(req, timeout=1.0) as res:
                if res.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def start_server_in_thread():
    import uvicorn

    os.chdir(str(STUDIO_DIR))
    if str(STUDIO_DIR) not in sys.path:
        sys.path.insert(0, str(STUDIO_DIR))
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, log_level="warning")


def main() -> None:
    print("\n[1/2] NGII Map Studio 로컬 서버 기동 중…")
    threading.Thread(target=start_server_in_thread, daemon=True).start()
    if not wait_for_port(PORT, timeout=15.0):
        print(f"로컬 서버 기동 시간 초과 (포트 {PORT})")
        sys.exit(1)

    lan_ip = get_lan_ip()
    print(f"[1/2] 완료 - 로컬 http://localhost:{PORT}   사내망 http://{lan_ip}:{PORT}")

    forced = os.environ.get("SHARE", "cloudflare").strip().lower()

    # 1) Tailscale
    if forced != "cloudflare":
        me = share.tailscale_self()
        if me:
            ip, dns_name = me
            url = f"http://{ip}:{PORT}/"
            print("[2/2] Tailscale 경유로 공유합니다.")
            share.announce(
                url, ROOT_DIR,
                "폰 카메라로 QR을 비추면 CAD 스튜디오가 열립니다.<br>"
                "폰에도 Tailscale 앱이 켜져 있어야 합니다 (LTE 로도 접속됩니다).<br>"
                f"이름으로도 됩니다: http://{dns_name}:{PORT}/",
            )
            _idle()
            return
        print("[2/2] " + share.TAILSCALE_HINT)
        print("      Cloudflare 터널로 대신 시도합니다.\n")

    # 2) Cloudflare quick tunnel
    if not ensure_cloudflared():
        print("Cloudflare 터널을 시작할 수 없습니다. 사내망 주소로만 접속하세요.")
        _idle()
        return

    os.environ.setdefault("CLOUDFLARED", str(CLOUDFLARED_EXE))
    tunnel = share.CloudflareTunnel(PORT, ROOT_DIR)
    tunnel.start(delay=0.5)
    try:
        _idle()
    finally:
        tunnel.stop()


def _idle() -> None:
    print("  종료하려면 이 창에서 Ctrl + C 를 누르거나 창을 닫으세요.\n")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n프로그램을 종료합니다…")


if __name__ == "__main__":
    main()
