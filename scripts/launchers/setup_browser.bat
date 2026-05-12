@echo off
setlocal
chcp 65001 >nul

echo ==========================================
echo   Synapse Browser Setup
echo ==========================================
echo.

set "ROOT=%~dp0..\.."
set "PYTHON="

if exist "%ROOT%\synenv\Scripts\python.exe" (
    set "PYTHON=%ROOT%\synenv\Scripts\python.exe"
) else (
    call conda activate syn
    if errorlevel 1 (
        echo [ERROR] Failed to activate conda environment "syn"
        echo Run:
        echo   start.bat
        echo or create the conda environment manually.
        if not defined SYNAPSE_NO_PAUSE pause
        exit /b 1
    )
    set "PYTHON=python"
)

echo [1/4] Python runtime ready: %PYTHON%
echo.

echo [2/4] Installing Python requirements...
%PYTHON% -m pip install -r "%ROOT%\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Failed to install requirements.txt
    if not defined SYNAPSE_NO_PAUSE pause
    exit /b 1
)
echo.

echo [3/4] Installing Hibbiki Chromium...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\packaging\install_hibbiki_chromium.ps1" -ProjectRoot "%ROOT%" -Clean
if errorlevel 1 (
    echo [ERROR] Failed to install Chromium
    if not defined SYNAPSE_NO_PAUSE pause
    exit /b 1
)
echo.

echo [4/4] Installing Firefox via Patchright...
set "PLAYWRIGHT_BROWSERS_PATH=%ROOT%\browsers"
%PYTHON% -m patchright install firefox
if errorlevel 1 (
    echo [ERROR] Failed to install Firefox
    if not defined SYNAPSE_NO_PAUSE pause
    exit /b 1
)
echo.

echo Browser setup complete.
echo Open the settings page to switch runtime or verify browser assets.
if not defined SYNAPSE_NO_PAUSE pause
