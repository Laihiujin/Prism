@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ============================================
echo   Start Supervisor (port 7002)
echo ============================================
echo.

REM Activate synenv
call "%~dp0synenv\Scripts\activate.bat"

set "PY=%~dp0synenv\Scripts\python.exe"

REM Supervisor locations
set "SUPERVISOR_EXE=%~dp0desktop-electron\resources\supervisor\supervisor.exe"
set "SUPERVISOR_EXE_FALLBACK=%~dp0desktop-electron\dist\win-unpacked\resources\supervisor\supervisor.exe"
set "SUPERVISOR_PY=%~dp0desktop-electron\resources\supervisor\supervisor.py"
set "SUPERVISOR_PY_FALLBACK=%~dp0desktop-electron\dist\win-unpacked\resources\supervisor\supervisor.py"

REM Set working directory to repo root
cd /d "%~dp0"

REM Set Python path (backend + supervisor resources)
set PYTHONPATH=%~dp0syn_backend;%~dp0desktop-electron\resources\supervisor

echo [Supervisor] Starting service manager...
echo [Supervisor] API Port: 7002
echo [Supervisor] Log: logs\supervisor.log
echo.

REM Prefer running supervisor.py when repo syn_backend/synenv exist.
if exist "%~dp0syn_backend" if exist "%PY%" if exist "%SUPERVISOR_PY%" (
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
