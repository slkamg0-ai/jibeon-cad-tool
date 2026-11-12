@echo off
title NGII Map Studio
echo ========================================================
echo  NGII Map Studio - NGII topo map extractor
echo ========================================================
echo.
cd /d "%~dp0"
echo [1/2] Checking Python dependencies ...
py -m pip install -r requirements.txt --quiet
echo.
echo [2/2] Starting server and opening browser ...
echo.
py run.py
pause
