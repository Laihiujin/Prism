@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ============================================
echo   Start Supervisor (port 7002)
echo ============================================
echo.

REM Activate synenv
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_ROOT=%%~fI\"

call "%PROJECT_ROOT%synenv\Scripts\activate.bat"

set "PY=%PROJECT_ROOT%synenv\Scripts\python.exe"

REM Supervisor locations
set "SUPERVISOR_EXE=%PROJECT_ROOT%desktop-electron\resources\supervisor\supervisor.exe"
set "SUPERVISOR_EXE_FALLBACK=%PROJECT_ROOT%desktop-electron\dist\win-unpacked\resources\supervisor\supervisor.exe"
set "SUPERVISOR_PY=%PROJECT_ROOT%desktop-electron\resources\supervisor\supervisor.py"
set "SUPERVISOR_PY_FALLBACK=%PROJECT_ROOT%desktop-electron\dist\win-unpacked\resources\supervisor\supervisor.py"

REM Set working directory to repo root
cd /d "%PROJECT_ROOT%"

REM Set Python path (backend + supervisor resources)
set PYTHONPATH=%PROJECT_ROOT%syn_backend;%PROJECT_ROOT%desktop-electron\resources\supervisor

echo [Supervisor] Starting service manager...
echo [Supervisor] API Port: 7002
echo [Supervisor] Log: logs\supervisor.log
echo.

REM Prefer running supervisor.py when repo syn_backend/synenv exist.
if exist "%PROJECT_ROOT%syn_backend" if exist "%PY%" if exist "%SUPERVISOR_PY%" (
    %PY% "%SUPERVISOR_PY%"
) else if exist "%SUPERVISOR_EXE%" (
    "%SUPERVISOR_EXE%"
) else if exist "%SUPERVISOR_EXE_FALLBACK%" (
    "%SUPERVISOR_EXE_FALLBACK%"
) else (
    if exist "%SUPERVISOR_PY%" (
        %PY% "%SUPERVISOR_PY%"
    ) else if exist "%SUPERVISOR_PY_FALLBACK%" (
        %PY% "%SUPERVISOR_PY_FALLBACK%"
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
