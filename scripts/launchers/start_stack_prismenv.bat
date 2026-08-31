@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "PROJECT_ROOT=%%~fI\"

set "REDIS_CLI=redis-cli"
if exist "%PROJECT_ROOT%prism_backend\Redis\redis-cli.exe" set "REDIS_CLI=%PROJECT_ROOT%prism_backend\Redis\redis-cli.exe"

echo ============================================
echo   Prism Full Startup (prismenv)
echo ============================================
echo.

REM 清理残留后端/Worker，避免端口占用导致绑定失败（[Errno 48] address already in use）
if exist "%SCRIPT_DIR%kill_port_7000.bat" call "%SCRIPT_DIR%kill_port_7000.bat"
if exist "%SCRIPT_DIR%kill_port_7001.bat" call "%SCRIPT_DIR%kill_port_7001.bat"
timeout /t 1 /nobreak >nul

echo [1] Checking Redis...
%REDIS_CLI% ping >nul 2>&1
if errorlevel 1 (
    echo [INFO] Redis is not running. Starting now...
    if exist "%PROJECT_ROOT%prism_backend\Redis\redis-server.exe" (
        start "Redis Server" "%PROJECT_ROOT%prism_backend\Redis\redis-server.exe"
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
start "Celery Worker (prismenv)" "%SCRIPT_DIR%start_celery_prismenv.bat"
timeout /t 2 /nobreak >nul

echo.
echo [3] Starting Automation Worker...
start "Automation Worker" "%SCRIPT_DIR%start_worker_prismenv.bat"
timeout /t 3 /nobreak >nul

echo.
echo [4] Starting FastAPI Backend...
start "FastAPI Backend" "%SCRIPT_DIR%start_backend_prismenv.bat"
timeout /t 3 /nobreak >nul

echo.
echo [5] Starting Frontend...
start "React Frontend" "%SCRIPT_DIR%start_frontend.bat"

echo.
echo [6] Starting Persona API (8787)...
set "PERSONA_PY=%PROJECT_ROOT%prismenv\Scripts\python.exe"
if not exist "%PERSONA_PY%" set "PERSONA_PY=python"
start "Persona API" cmd /c "cd /d "%PROJECT_ROOT%tools\persona-studio" && "%PERSONA_PY%" -m persona --data-dir data serve"

echo.
echo [7] Starting Persona Dashboard (5175)...
start "Persona Dashboard" cmd /c "cd /d "%PROJECT_ROOT%tools\persona-studio\dashboard" && npm run dev"

echo.
echo ============================================
echo   [OK] All services started
echo ============================================
echo.
echo Services:
echo   - Redis Server      (localhost:6379)
echo   - Celery Worker     (task queue)
echo   - Automation Worker (localhost:7001)
echo   - FastAPI Backend   (http://localhost:7000)
echo   - React Frontend    (http://localhost:3000)
echo   - Persona API       (http://localhost:8787)
echo   - Persona Dashboard (http://localhost:5175)
echo   - Hermes (由后端自动托管) (http://localhost:9119)
echo.
pause
