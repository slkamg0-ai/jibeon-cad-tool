@echo off
echo ===============================================================
echo  NGII Map Studio - Cloudflare secure tunnel (HTTPS, anywhere)
echo ===============================================================
cd /d "%~dp0"
py run_with_cloudflare.py
pause
