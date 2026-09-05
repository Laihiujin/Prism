@echo off
chcp 65001 >nul
setlocal EnableExtensions
set "ROOT=%~dp0"
cd /d "%ROOT%"
set "PM2_HOME=%ROOT%runtime-data\pm2"

set "PM2=%ROOT%node_modules\.bin\pm2.cmd"
if not exist "%PM2%" set "PM2=%ROOT%prism_frontend\node_modules\.bin\pm2.cmd"
if not exist "%PM2%" set "PM2=pm2"

echo [STOP] Stopping Prism PM2 stack ...
"%PM2%" delete all
echo.
echo [OK] Done. (数据与日志保留在 %PM2_HOME%)
exit /b 0
