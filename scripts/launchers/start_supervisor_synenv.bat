@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ============================================
echo   Start Supervisor (port 7002)
echo ============================================
echo.

set "ROOT=%~dp0..\.."

call "%ROOT%\synenv\Scripts\activate.bat"

set "PY=%ROOT%\synenv\Scripts\python.exe"

set "SUPERVISOR_EXE=%ROOT%\desktop-electron\resources\supervisor\supervisor.exe"
set "SUPERVISOR_EXE_FALLBACK=%ROOT%\desktop-electron\dist\win-unpacked\resources\supervisor\supervisor.exe"
set "SUPERVISOR_PY=%ROOT%\desktop-electron\resources\supervisor\supervisor.py"
set "SUPERVISOR_PY_FALLBACK=%ROOT%\desktop-electron\dist\win-unpacked\resources\supervisor\supervisor.py"

cd /d "%ROOT%"

set PYTHONPATH=%ROOT%\syn_backend;%ROOT%\desktop-electron\resources\supervisor
set "SYNAPSE_HERMES_PYTHON=%PY%"

echo [Supervisor] Starting service manager...
echo [Supervisor] API Port: 7002
echo [Supervisor] Log: logs\supervisor.log
echo.

if exist "%ROOT%\syn_backend" if exist "%PY%" if exist "%SUPERVISOR_PY%" (
    "%PY%" "%SUPERVISOR_PY%"
) else if exist "%SUPERVISOR_EXE%" (
    "%SUPERVISOR_EXE%"
) else if exist "%SUPERVISOR_EXE_FALLBACK%" (
    "%SUPERVISOR_EXE_FALLBACK%"
) else (
    if exist "%SUPERVISOR_PY%" (
        "%PY%" "%SUPERVISOR_PY%"
    ) else if exist "%SUPERVISOR_PY_FALLBACK%" (
        "%PY%" "%SUPERVISOR_PY_FALLBACK%"
    ) else (
        echo [ERROR] supervisor not found in resources or dist.
        pause
        exit /b 1
    )
)

if errorlevel 1 (
    echo.
    echo [ERROR] Supervisor failed to start
    echo Please check supervisor.log
    pause
)
