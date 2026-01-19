@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set FORKED_BY_MULTIPROCESSING=1

set "ROOT=%~dp0"
set "VENV_PATH=%ROOT%synenv"
set "PY=%VENV_PATH%\Scripts\python.exe"

set "REDIS_CLI=redis-cli"
if exist "%ROOT%syn_backend\Redis\redis-cli.exe" set "REDIS_CLI=%ROOT%syn_backend\Redis\redis-cli.exe"

echo ============================================
echo   SynapseAutomation Celery Worker (synenv)
echo ============================================
echo.

if not exist "%PY%" (
    echo [ERROR] Virtual environment not found at: %VENV_PATH%
    echo Please run: python -m venv synenv
    pause
    exit /b 1
)

call "%VENV_PATH%\Scripts\activate.bat" >nul 2>&1

echo [1/3] Checking Redis...
%REDIS_CLI% ping >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Redis not running. Start Redis first.
    pause
    exit /b 1
)
echo OK Redis running.

echo.
echo [2/3] Switching to backend directory...
cd /d "%ROOT%syn_backend"

echo.
echo [3/3] Starting Celery Worker...
echo Broker: Redis (from .env REDIS_URL)
echo.

REM Add syn_backend to PYTHONPATH so myUtils can be imported
set "PYTHONPATH=%ROOT%syn_backend;%PYTHONPATH%"

%PY% -m celery -A fastapi_app.tasks.celery_app worker ^
    --loglevel=info ^
    --pool=threads ^
    --concurrency=1000 ^
    --hostname=synapse-worker@%%h-%RANDOM%

pause
