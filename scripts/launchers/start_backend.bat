@echo off
chcp 65001 >nul

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set ROOT=%~dp0..\..
set BACKEND_DIR=%ROOT%\syn_backend

call conda activate syn
if errorlevel 1 (
    echo ERROR: Failed to activate conda environment syn
    pause
    exit /b 1
)
echo OK: Activated conda environment syn
set PY=python
echo.

set PLAYWRIGHT_BROWSERS_PATH=%ROOT%\browsers
set MANUS_API_BASE_URL=http://localhost:7000/api/v1

if not defined ENABLE_OCR_RESCUE set ENABLE_OCR_RESCUE=1
if not defined START_CELERY set START_CELERY=1
if not defined FORCE_CELERY set FORCE_CELERY=0

pushd %BACKEND_DIR%

echo Starting FastAPI Backend on port 7000...
echo.

%PY% fastapi_app/run.py

popd
pause
