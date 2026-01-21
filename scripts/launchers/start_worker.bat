@echo off
chcp 65001 >nul

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

pushd %BACKEND_DIR%

echo Starting Playwright Worker on port 7001...
echo.

%PY% playwright_worker\worker.py
popd

pause
