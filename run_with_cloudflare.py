# -*- coding: utf-8 -*-
"""NGII Map Studio 스마트폰 & 외부 접속 실행기.

1. 로컬 웹 서버(FastAPI/Uvicorn)를 안전한 충돌 방지 포트(기본 8088)로 띄웁니다.
2. PC에 설치된 Tailscale을 감지하여 평생 바뀌지 않는 [영구 고정 주소](http://100.x.x.x:8088)를 즉시 제공합니다.
3. 외부 지인 공유용 Cloudflare 보안 웹 터널(HTTPS)도 함께 연결하여 QR/주소 허브(phone_access.html)를 브라우저에 엽니다.
"""

import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

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
import share

CLOUDFLARED_DOWNLOAD_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/"
    "cloudflared-windows-amd64.exe"
)


def ensure_cloudflared() -> bool:
    if CLOUDFLARED_EXE.exists() and CLOUDFLARED_EXE.stat().st_size > 10_000_000:
        return True
    print("=" * 70)
    print("Cloudflare Tunnel 실행 파일(cloudflared.exe)을 내려받습니다...")
    print(f"  출처: {CLOUDFLARED_DOWNLOAD_URL}")
    print("=" * 70)
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
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/crs-list",
                headers={"User-Agent": "HealthCheck"}
            )
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
    print("\n[1/3] NGII Map Studio 로컬 서버 기동 중...")
    threading.Thread(target=start_server_in_thread, daemon=True).start()
    if not wait_for_port(PORT, timeout=15.0):
        print(f"로컬 서버 기동 시간 초과 (포트 {PORT})")
        sys.exit(1)

    lan_ip = get_lan_ip()
    print(f"[1/3] 서버 가동 완료: 포트 {PORT}")

    # Tailscale 정보 확인 (영구 고정 주소)
    ts_info = share.tailscale_self()

    # 안내 페이지 1차 오픈 (Tailscale 영구 주소 즉시 노출)
    if ts_info:
        print(f"[2/3] Tailscale 감지 성공! 평생 고정 주소(http://{ts_info[0]}:{PORT})가 활성화되었습니다.")
        share.announce_hub(ROOT_DIR, PORT, ts_info, None, lan_ip, open_browser=True)
    else:
        print("[2/3] Tailscale 이 비활성화 상태입니다. Cloudflare 터널을 연결합니다.")

    # Cloudflare 준비
    if not ensure_cloudflared():
        print("Cloudflare 터널 실행 파일이 없어 Tailscale 및 사내망 주소로만 접속할 수 있습니다.")
        _idle()
        return

    os.environ.setdefault("CLOUDFLARED", str(CLOUDFLARED_EXE))

    def on_cf_url(cf_url: str):
        # Cloudflare 주소가 발급되면 허브 페이지 갱신
        share.announce_hub(ROOT_DIR, PORT, ts_info, cf_url, lan_ip, open_browser=not ts_info)

    tunnel = share.CloudflareTunnel(PORT, ROOT_DIR, on_url=on_cf_url)
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
        print("\n프로그램을 종료합니다...")


if __name__ == "__main__":
    main()
