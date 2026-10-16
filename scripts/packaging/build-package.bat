@echo off
cd /d "%~dp0..\..\desktop-electron"
call npm run build
exit /b %ERRORLEVEL%
