@echo off
echo ========================================
echo Starting Redis Server
echo ========================================

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_ROOT=%%~fI\"

cd /d "%PROJECT_ROOT%syn_backend\Redis"

if not exist redis-server.exe (
    echo ERROR: redis-server.exe not found!
    pause
    exit /b 1
)

echo Starting Redis on port 6379...
start "Redis Server" cmd /k "redis-server.exe"

echo.
echo Redis Server is starting in a new window...
echo.
pause
