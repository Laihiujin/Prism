@echo off
chcp 65001 >nul

REM Set UTF-8 encoding environment
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set "ROOT=%~dp0..\.."
set "BACKEND_DIR=%ROOT%\syn_backend"

echo ========================================
echo   Synapse Celery Worker (Windows)
echo ========================================
echo.

REM Activate conda environment (syn)
call conda activate syn
if errorlevel 1 (
    echo [ERROR] Failed to activate conda environment 'syn'
    echo Please run: conda create -n syn python=3.11
    pause
    exit /b 1
)
echo OK Activated conda environment 'syn'
set "PY=python"
echo.

pushd "%BACKEND_DIR%"
echo Starting Celery worker...
echo Press Ctrl+C to stop the worker.
echo.

REM Add syn_backend to PYTHONPATH so myUtils can be imported
set "PYTHONPATH=%BACKEND_DIR%;%PYTHONPATH%"

%PY% -m celery -A fastapi_app.tasks.celery_app.celery_app worker -l info --hostname=synapse-worker@%%h-%RANDOM%
set "RC=%ERRORLEVEL%"
popd

if not "%RC%"=="0" (
    echo.
    echo [ERROR] Celery worker exited with code %RC%
    pause
    exit /b %RC%
)
