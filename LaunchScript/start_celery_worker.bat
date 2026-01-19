@echo off
chcp 65001 >nul

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set FORKED_BY_MULTIPROCESSING=1

set ROOT=%~dp0
set BACKEND_DIR=%ROOT%syn_backend

set "REDIS_CLI=redis-cli"
if exist "%ROOT%syn_backend\Redis\redis-cli.exe" set "REDIS_CLI=%ROOT%syn_backend\Redis\redis-cli.exe"

echo ============================================
echo   Celery Worker Startup
echo ============================================
echo.

call conda activate syn
if errorlevel 1 (
    echo ERROR: Cannot activate conda environment syn
    pause
    exit /b 1
)
echo OK: Activated environment syn
echo.

%REDIS_CLI% ping >nul 2>&1
if errorlevel 1 (
    echo ERROR: Redis not running
    echo Please start Redis first: redis-server
    pause
    exit /b 1
)
echo OK: Redis is running
echo.

cd /d %BACKEND_DIR%

echo Starting Celery Worker with 1000 concurrency (threads pool)...
echo.

REM Add syn_backend to PYTHONPATH so myUtils can be imported
set "PYTHONPATH=%BACKEND_DIR%;%PYTHONPATH%"

python -m celery -A fastapi_app.tasks.celery_app worker --loglevel=info --pool=threads --concurrency=1000 --hostname=synapse-worker@%%h-%RANDOM%

pause
