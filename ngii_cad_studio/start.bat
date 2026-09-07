@echo off
chcp 65001 > nul
title NGII Map Studio - 수치지형도 맞춤 추출기
echo ========================================================
echo  NGII Map Studio - 국토정보플랫폼 수치지형도 맞춤 추출기
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/2] 파이썬 및 의존성 라이브러리 점검 중...
py -m pip install -r requirements.txt --quiet

echo.
echo [2/2] 서버 시작 및 웹 브라우저 실행 중...
echo.
py run.py

pause
