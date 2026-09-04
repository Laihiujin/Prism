@echo off
chcp 65001 >nul

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set ROOT=%~dp0..\..
set BACKEND_DIR=%ROOT%\prism_backend

call conda activate prism
if errorlevel 1 (
    echo ERROR: Failed to activate conda environment prism
    pause
    exit /b 1
)
echo OK: Activated conda environment prism
set PY=python
echo.

set PLAYWRIGHT_BROWSERS_PATH=%ROOT%\browsers
if not defined PRISM_BACKEND_HOST set PRISM_BACKEND_HOST=127.0.0.1
if not defined PRISM_BACKEND_PORT set PRISM_BACKEND_PORT=7000
if not defined PRISM_BACKEND_URL set PRISM_BACKEND_URL=http://%PRISM_BACKEND_HOST%:%PRISM_BACKEND_PORT%
set MANUS_API_BASE_URL=%PRISM_BACKEND_URL%/api/v1

if not defined ENABLE_OCR_RESCUE set ENABLE_OCR_RESCUE=1
if not defined START_CELERY set START_CELERY=1
if not defined FORCE_CELERY set FORCE_CELERY=0

pushd %BACKEND_DIR%

echo Starting FastAPI Backend on port %PRISM_BACKEND_PORT%...
echo.

%PY% fastapi_app/run.py

popd
pause
