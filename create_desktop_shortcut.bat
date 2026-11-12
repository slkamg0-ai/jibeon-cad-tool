@echo off
cd /d "%~dp0"
echo ===============================================================
echo  NGII Map Studio - Create desktop shortcut
echo ===============================================================
py create_desktop_shortcut.py
echo.
echo Done. Press any key to close this window.
pause > nul
