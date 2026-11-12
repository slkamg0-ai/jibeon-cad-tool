@echo off
cd /d "%~dp0"
echo ===============================================================
echo  NGII Map Studio - Vercel production deploy
echo  (permanent https://*.vercel.app address)
echo ===============================================================
echo.
echo [1/2] Copying static assets to public\ ...
xcopy /E /I /Y "ngii_cad_studio\app\static\*" "public\" > nul
echo [2/2] Deploying to Vercel ...
call npx.cmd vercel --prod --yes
echo.
echo ===============================================================
echo  Deploy finished.
echo ===============================================================
pause
