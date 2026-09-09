"""폰에서 접속할 주소를 만든다. (cad-viewer 의 같은 모듈과 동일한 구조)

접속 방식이 두 가지다.

  tailscale (기본)  이 PC의 테일넷 주소로 직접 붙는다. 폰에 Tailscale 앱만 켜져 있으면
                    LTE 로도 접속되고, 인터넷에 공개되지 않는다.
  cloudflare        무계정 quick tunnel 로 공인 HTTPS 주소를 받는다.
                    다만 Cloudflare 가 호스트명을 DNS 에 올려주지 않는 경우가 있어
                    (터널은 등록되는데 이름이 NXDOMAIN) 주소를 넘기기 전에 확인한다.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

URL_RE = re.compile(r"https://[a-zA-Z0-9][-a-zA-Z0-9.]*\.trycloudflare\.com")

# ------------------------------------------------------------------ QR 페이지

def qr_svg(url: str) -> str:
    try:
        import segno

        buf = io.BytesIO()
        segno.make(url, error="m").save(
            buf, kind="svg", scale=9, border=2,
            dark="#14171c", light="#ffffff", xmldecl=False, svgns=True,
        )
        return buf.getvalue().decode("utf-8")
    except Exception as exc:                       # segno 미설치 등
        print(f"[공유] QR 생성 실패({exc}) - 주소만 표시합니다.")
        return '<p style="color:#e06c75">아래 주소를 폰에 직접 입력하세요.</p>'


def write_qr_page(url: str, dest: Path, note: str, warn: str = "") -> Path | None:
    html = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<title>NGII CAD 스튜디오 - 폰으로 열기</title>
<style>
 body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#14171c;color:#e4e8ef;
      font:16px/1.5 "Malgun Gothic","맑은 고딕",sans-serif;text-align:center;padding:28px}}
 .card{{max-width:470px}}
 h1{{font-size:22px;margin:0 0 6px;color:#ffb454}}
 p.note{{color:#8c96a6;margin:0 0 22px;font-size:14px;line-height:1.7}}
 .qr{{background:#fff;padding:14px;border-radius:16px;display:inline-block;line-height:0}}
 .qr svg{{width:260px;height:260px}}
 .url{{margin-top:20px;background:#1b1f26;border:1px solid #333b47;border-radius:10px;
       padding:13px;font:13px/1.5 monospace;word-break:break-all;color:#4ec9b0}}
 button{{margin-top:12px;background:#ffb454;border:0;color:#1a1204;font:600 15px/1 inherit;
         padding:13px 20px;border-radius:10px;cursor:pointer}}
 .warn{{margin-top:24px;font-size:12.5px;color:#e06c75;line-height:1.6}}
</style></head><body><div class="card">
<h1>폰으로 열기</h1>
<p class="note">{note}</p>
<div class="qr">{qr_svg(url)}</div>
<div class="url" id="u">{url}</div>
<button onclick="navigator.clipboard.writeText(document.getElementById('u').textContent);this.textContent='복사됨'">주소 복사</button>
{f'<p class="warn">{warn}</p>' if warn else ''}
</div></body></html>"""
    try:
        dest.write_text(html, encoding="utf-8")
        return dest
    except OSError:
        return None


def announce(url: str, project_dir: Path, note: str, warn: str = "") -> None:
    print("\n" + "=" * 66)
    print(f"  폰에서 접속:  {url}")
    for line in note.replace("<br>", "\n").split("\n"):
        if line.strip():
            print(f"  {line.strip()}")
    print("=" * 66 + "\n")
    (project_dir / "tunnel_url.txt").write_text(url, encoding="utf-8")
    try:
        import urllib.parse
        import urllib.request
        qr_api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(url)}"
        urllib.request.urlretrieve(qr_api_url, str(project_dir / "mobile_access_qr.png"))
    except Exception:
        pass
    page = write_qr_page(url, project_dir / "phone_access.html", note, warn)
    if page:
        webbrowser.open(page.as_uri())


# ------------------------------------------------------------------ Tailscale

TAILSCALE_PATHS = [
    r"C:\Program Files\Tailscale\tailscale.exe",
    r"C:\Program Files (x86)\Tailscale\tailscale.exe",
]


def find_tailscale() -> str | None:
    env = os.environ.get("TAILSCALE")
    if env and Path(env).exists():
        return env
    which = shutil.which("tailscale")
    if which:
        return which
    for p in TAILSCALE_PATHS:
        if Path(p).exists():
            return p
    return None


def tailscale_self() -> tuple[str, str] | None:
    """(테일넷 IPv4, MagicDNS 이름) 을 돌려준다. 로그인 상태가 아니면 None."""
    exe = find_tailscale()
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "status", "--json"], capture_output=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        data = json.loads(out.stdout.decode("utf-8", "replace"))
    except Exception:
        return None

    if data.get("BackendState") != "Running":
        return None
    me = data.get("Self") or {}
    ips = [ip for ip in (me.get("TailscaleIPs") or []) if ":" not in ip]
    if not ips:
        return None
    return ips[0], (me.get("DNSName") or "").rstrip(".")


TAILSCALE_HINT = (
    "Tailscale 로 접속할 수 없습니다.\n"
    "  - 작업표시줄의 Tailscale 이 켜져 있고 로그인돼 있는지 확인하세요.\n"
    "  - 폰에도 Tailscale 앱을 설치해 같은 계정으로 로그인해야 합니다.\n"
    "  - 설치 경로가 다르면 환경변수 TAILSCALE 에 tailscale.exe 경로를 지정하세요."
)


# ------------------------------------------------------------------ Cloudflare

CLOUDFLARED_PATHS = [
    r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
    r"C:\Program Files\cloudflared\cloudflared.exe",
    r"C:\Users\{user}\Documents\Claude\jibeon-cad-tool\cloudflared.exe",
]

CLOUDFLARED_HINT = (
    "cloudflared 를 찾지 못했습니다.\n"
    "  https://github.com/cloudflare/cloudflared/releases 에서 받아 프로젝트 폴더에 두거나,\n"
    "  환경변수 CLOUDFLARED 에 실행 파일 경로를 지정하세요."
)

QUICK_TUNNEL_BLOCKED = (
    "Cloudflare 가 이 터널 주소를 DNS 에 올려주지 않았습니다.\n"
    "  터널 연결 자체는 성공했지만 호스트명이 조회되지 않습니다(무계정 quick tunnel 제한).\n"
    "  Cloudflare 쪽 문제라 이 PC 에서 고칠 수 없습니다.\n"
    "  Tailscale 경유로 접속하세요 (이 창 위쪽 안내 참고)."
)


def find_cloudflared(project_dir: Path) -> str | None:
    env = os.environ.get("CLOUDFLARED")
    if env and Path(env).exists():
        return env
    local = project_dir / "cloudflared.exe"
    if local.exists():
        return str(local)
    which = shutil.which("cloudflared")
    if which:
        return which
    user = os.environ.get("USERNAME", "")
    for pat in CLOUDFLARED_PATHS:
        p = Path(pat.format(user=user))
        if p.exists():
            return str(p)
    return None


def hostname_resolves(host: str, timeout_s: float = 45.0) -> bool:
    """터널 호스트명이 실제로 DNS 에 올라올 때까지 기다린다."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            socket.getaddrinfo(host, 443)
            return True
        except socket.gaierror:
            time.sleep(3)
    return False


class CloudflareTunnel:
    def __init__(self, port: int, project_dir: Path):
        self.port = port
        self.project_dir = project_dir
        self.proc: subprocess.Popen | None = None
        self.url: str | None = None
        self.running: bool = True

    def start(self, delay: float = 1.5) -> None:
        exe = find_cloudflared(self.project_dir)
        if not exe:
            print("\n[공유] " + CLOUDFLARED_HINT + "\n")
            return
        threading.Thread(target=self._run, args=(exe, delay), daemon=True).start()

    def _run(self, exe: str, delay: float) -> None:
        time.sleep(delay)                       # 웹서버가 먼저 뜨도록 잠깐 기다린다
        while self.running:
            cmd = [exe, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{self.port}"]
            try:
                self.proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    encoding="utf-8", errors="replace", bufsize=1,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError as exc:
                print(f"[공유] cloudflared 실행 실패: {exc}")
                return

            self.url = None
            if self.proc.stdout:
                for line in self.proc.stdout:
                    if self.url:
                        continue                        # 주소를 얻은 뒤 로그는 흘려보낸다
                    found = URL_RE.search(line)
                    if found:
                        self.url = found.group(0)
                        self._verify_and_announce()

            if not self.running:
                break
            print("\n[공유] Cloudflare 터널 연결이 종료/갱신되었습니다. 2초 후 자동 재연결합니다...")
            time.sleep(2)

    def _verify_and_announce(self) -> None:
        host = self.url.split("//", 1)[1]
        print(f"[공유] 주소 발급: {self.url}  — DNS 등록을 확인하는 중…")
        if not hostname_resolves(host):
            print("\n" + "!" * 66)
            print(QUICK_TUNNEL_BLOCKED)
            print("!" * 66 + "\n")
            return
        announce(
            self.url, self.project_dir,
            "폰 카메라로 QR을 비추면 CAD 스튜디오가 열립니다.",
            "이 주소는 인터넷에 공개됩니다. 링크를 함부로 공유하지 말고, "
            "다 쓰면 서버 창을 닫아 터널을 내리세요.",
        )

    def stop(self) -> None:
        self.running = False
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
