@echo off
chcp 65001 > nul
echo ===============================================================
echo  NGII Map Studio - Cloudflare 보안 웹 터널 모드 실행
echo  (외부 어디서나 접속 가능한 HTTPS 웹 주소 자동 발급)
echo ===============================================================
cd /d "%~dp0"
py run_with_cloudflare.py
pause
