@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "PROJECT_ROOT=%%~fI\"

set "REDIS_CLI=redis-cli"
if exist "%PROJECT_ROOT%syn_backend\Redis\redis-cli.exe" set "REDIS_CLI=%PROJECT_ROOT%syn_backend\Redis\redis-cli.exe"

echo ============================================
echo   SynapseAutomation Full Startup (synenv)
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
echo [2] Starting Celery Worker...
start "Celery Worker (synenv)" "%SCRIPT_DIR%start_celery_synenv.bat"
timeout /t 2 /nobreak >nul

echo.
echo [3] Starting Playwright Worker...
start "Playwright Worker" "%SCRIPT_DIR%start_worker_synenv.bat"
timeout /t 3 /nobreak >nul

echo.
echo [4] Starting FastAPI Backend...
start "FastAPI Backend" "%SCRIPT_DIR%start_backend_synenv.bat"
timeout /t 3 /nobreak >nul

echo.
echo [5] Starting Frontend...
start "React Frontend" "%SCRIPT_DIR%start_frontend.bat"

echo.
echo ============================================
echo   [OK] All services started
echo ============================================
echo.
echo Services:
echo   - Redis Server      (localhost:6379)
echo   - Celery Worker     (task queue)
echo   - Playwright Worker (localhost:7001)
echo   - FastAPI Backend   (http://localhost:7000)
echo   - React Frontend    (http://localhost:3000)
echo.
pause
