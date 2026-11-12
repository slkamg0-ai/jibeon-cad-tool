@echo off
echo ===============================================================
echo  NGII Map Studio - Web CAD Studio (cadastral + topo map)
echo ===============================================================
cd /d "%~dp0ngii_cad_studio"
echo [1/2] Installing dependencies (first run may take a minute) ...
py -m pip install -r requirements.txt --quiet
echo.
echo [2/2] Starting server ...
py run.py
pause
