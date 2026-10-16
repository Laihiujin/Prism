@echo off
cd /d "%~dp0.."
call npm run build:dir
exit /b %ERRORLEVEL%
