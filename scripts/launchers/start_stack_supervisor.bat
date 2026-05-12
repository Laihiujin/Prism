@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "PROJECT_ROOT=%%~fI\"

set "REDIS_CLI=redis-cli"
if exist "%PROJECT_ROOT%syn_backend\Redis\redis-cli.exe" set "REDIS_CLI=%PROJECT_ROOT%syn_backend\Redis\redis-cli.exe"
if exist "%PROJECT_ROOT%syn_backend\Redis\redis-server.exe" set "SYNAPSE_REDIS_PATH=%PROJECT_ROOT%syn_backend\Redis\redis-server.exe"

echo ============================================
echo   SynapseAutomation Supervisor Startup
echo ============================================
echo.

echo [1] Checking Redis...
%REDIS_CLI% ping >nul 2>&1
if errorlevel 1 (
    echo [INFO] Redis is not running. Starting now...
    if exist "%PROJECT_ROOT%syn_backend\Redis\redis-server.exe" (
        start "Redis Server" "%PROJECT_ROOT%syn_backend\Redis\redis-server.exe"
    ) else (
        start "Redis Server" redis-server
    )
    timeout /t 3 /nobreak >nul

    %REDIS_CLI% ping >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Redis startup failed. Run redis-server manually.
        pause
        exit /b 1
    )
    echo [OK] Redis started.
) else (
    echo [OK] Redis already running.
)

echo.
echo [2] Starting Supervisor...
start "Supervisor" "%SCRIPT_DIR%start_supervisor_synenv.bat"
timeout /t 3 /nobreak >nul

echo.
echo [3] Starting Frontend...
start "React Frontend" "%SCRIPT_DIR%start_frontend.bat"

echo.
echo ============================================
echo   [OK] Supervisor mode started
echo ============================================
echo.
echo Services:
echo   - Redis Server      (localhost:6379)
echo   - Supervisor API    (http://localhost:7002)
echo   - Playwright Worker (localhost:7001, via Supervisor)
echo   - FastAPI Backend   (http://localhost:7000, via Supervisor)
echo   - Celery Worker     (task queue, via Supervisor)
echo   - React Frontend    (http://localhost:3000)
echo.
pause
