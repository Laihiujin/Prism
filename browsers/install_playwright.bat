@echo off
setlocal
chcp 65001 >nul

set "ROOT=%~dp0.."
set "BACKEND_DIR=%ROOT%\syn_backend"
pushd "%ROOT%"

echo ==========================================
echo   Synapse Playwright Browser Setup
echo ==========================================
echo.

if not exist "synenv\Scripts\python.exe" (
    echo [ERROR] Missing venv python: %ROOT%\synenv\Scripts\python.exe
    echo Please create the venv first:
    echo   python -m venv synenv
    echo   synenv\Scripts\activate
    echo   pip install -r requirements.txt
    popd
    if not defined SYNAPSE_NO_PAUSE pause
    exit /b 1
)

call synenv\Scripts\activate
if errorlevel 1 (
    echo [ERROR] Failed to activate synenv
    popd
    if not defined SYNAPSE_NO_PAUSE pause
    exit /b 1
)

echo [1/3] Checking Python browser runtime...
python -c "import playwright" >nul 2>&1
if not errorlevel 1 (
    echo   Removing conflicting playwright runtime...
    python -m pip uninstall -y playwright
    if errorlevel 1 (
        echo [ERROR] Failed to remove conflicting playwright runtime
        popd
        if not defined SYNAPSE_NO_PAUSE pause
        exit /b 1
    )
)

python -c "import patchright" >nul 2>&1
if errorlevel 1 (
    echo   Installing patchright 1.59.1...
    python -m pip install patchright==1.59.1
    if errorlevel 1 (
        echo [ERROR] Failed to install patchright
        popd
        if not defined SYNAPSE_NO_PAUSE pause
        exit /b 1
    )
)
python -c "import importlib.metadata; version = importlib.metadata.version('patchright'); assert version == '1.59.1', version" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Patchright runtime version check failed
    popd
    if not defined SYNAPSE_NO_PAUSE pause
    exit /b 1
)
echo   OK
echo.

echo [2/3] Installing Hibbiki Chromium into browsers\chromium...
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\packaging\install_hibbiki_chromium.ps1" -ProjectRoot "%ROOT%"
if errorlevel 1 (
    echo [ERROR] Failed to install Hibbiki Chromium
    popd
    if not defined SYNAPSE_NO_PAUSE pause
    exit /b 1
)
echo.

echo [3/3] Verifying resolved browser path...
python -c "import sys; sys.path.insert(0, r'%BACKEND_DIR%'); from config.conf import LOCAL_CHROME_PATH; print('LOCAL_CHROME_PATH=' + str(LOCAL_CHROME_PATH))"
set "VERIFY_EXIT=%ERRORLEVEL%"
if not "%VERIFY_EXIT%"=="0" (
    echo [ERROR] Failed to resolve LOCAL_CHROME_PATH
    popd
    if not defined SYNAPSE_NO_PAUSE pause
    exit /b 1
)
echo.

echo Setup complete.
popd
if not defined SYNAPSE_NO_PAUSE pause
