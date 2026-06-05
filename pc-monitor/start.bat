@echo off
title PC Monitor Dashboard
cd /d "%~dp0"
echo.
echo ==================================================
echo   PC Monitor Dashboard
echo   http://localhost:8765
echo ==================================================
echo.
echo Starting server...
start "" "http://localhost:8765"
python backend\main.py
pause
