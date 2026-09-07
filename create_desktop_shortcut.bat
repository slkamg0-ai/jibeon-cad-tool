@echo off
chcp 65001 > nul
echo ===============================================================
echo  NGII Map Studio - 바탕화면 실행 아이콘 바로가기 생성기
echo ===============================================================
py create_desktop_shortcut.py
echo.
echo 생성이 완료되었습니다. 아무 키나 누르면 창이 닫힙니다.
pause > nul
