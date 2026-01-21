@echo off
chcp 65001 >nul
echo ========================================
echo   Playwright Worker Startup (synenv)
echo ========================================
echo.

set "ROOT=%~dp0..\.."
set "BACKEND_DIR=%ROOT%\syn_backend"
set "VENV_PATH=%ROOT%\synenv"
set "PY=%VENV_PATH%\Scripts\python.exe"

REM Activate synenv virtual environment
if not exist "%PY%" (
    echo [ERROR] Virtual environment "synenv" not found at: %VENV_PATH%
    echo Please run: python -m venv synenv
    pause
    exit /b 1
)

call "%VENV_PATH%\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment 'synenv'
    pause
    exit /b 1
)
echo OK Activated virtual environment 'synenv'
set "PY=%VENV_PATH%\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
echo.

REM Bundle Playwright browsers inside this repo (important for packaging to exe)
REM 使用新的 browsers 文件夹结构（区分 firefox 和 chromium）
set "PLAYWRIGHT_BROWSERS_PATH=%ROOT%\browsers"
REM Enable OCR/Selenium helpers (can be overridden by existing env vars)
if not defined ENABLE_OCR_RESCUE set "ENABLE_OCR_RESCUE=1"
if not defined ENABLE_SELENIUM_RESCUE set "ENABLE_SELENIUM_RESCUE=1"
if not defined ENABLE_SELENIUM_DEBUG set "ENABLE_SELENIUM_DEBUG=1"
if not defined PLAYWRIGHT_AUTO_INSTALL set "PLAYWRIGHT_AUTO_INSTALL=0"

REM Kill existing Worker (more reliable than parsing netstat)
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 7001 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {} }"
timeout /t 2 /nobreak >nul

pushd "%BACKEND_DIR%"

echo Starting Playwright Worker...
echo   - Port: 7001
echo   - Health: http://localhost:7001/health
echo.

%PY% playwright_worker\worker.py
popd

pause
