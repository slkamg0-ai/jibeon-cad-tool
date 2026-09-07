@echo off
chcp 65001 > nul
echo ===============================================================
echo  NGII Map Studio - 통합 현황지적지형도 CAD 추출기 실행
echo ===============================================================
cd /d "%~dp0ngii_cad_studio"
py run.py
pause
