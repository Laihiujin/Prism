@echo off
chcp 65001 >nul

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

pushd %BACKEND_DIR%

echo Starting Automation Worker on port 7001...
echo.

%PY% automation_worker\worker.py
popd

pause
