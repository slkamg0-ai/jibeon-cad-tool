@echo off
chcp 65001 > nul
echo ===============================================================
echo  NGII Map Studio - Vercel 클라우드 영구 배포
echo  (https://*.vercel.app 주소로 전 세계 어디서나 접속)
echo ===============================================================
cd /d "%~dp0"
echo.
echo [1/2] 정적 웹 에셋(public/) 동기화 중...
xcopy /E /I /Y "ngii_cad_studio\app\static\*" "public\" > nul
echo [2/2] Vercel 프로덕션 배포 진행 중...
npx.cmd vercel --prod --yes
echo.
echo ===============================================================
echo  배포가 완료되었습니다!
echo ===============================================================
pause
