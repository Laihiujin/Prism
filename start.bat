@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "ROOT=%~dp0"
set "MODE=%~1"
set "LAUNCHERS=%ROOT%scripts\launchers"
set "SYNENV_DIR=%ROOT%synenv"
set "SYNENV_PY=%SYNENV_DIR%\Scripts\python.exe"
set "REQ_FILE=%ROOT%requirements.txt"
set "REQ_STAMP=%SYNENV_DIR%\.requirements-ready"

if /I "%MODE%"=="help" goto usage
if /I "%MODE%"=="/?" goto usage
if /I "%MODE%"=="-h" goto usage
if /I "%MODE%"=="--help" goto usage

if /I not "%MODE%"=="conda" (
    call :ensure_synenv
    if errorlevel 1 exit /b %ERRORLEVEL%
)

if /I "%MODE%"=="synenv" (
    echo [INFO] Using synenv launcher from repo root.
    call "%LAUNCHERS%\start_stack_synenv.bat"
    exit /b %ERRORLEVEL%
)

if /I "%MODE%"=="conda" (
    echo [INFO] Using conda launcher from repo root.
    call "%LAUNCHERS%\start_stack_conda.bat"
    exit /b %ERRORLEVEL%
)

if /I "%MODE%"=="supervisor" (
    echo [INFO] Using supervisor launcher from repo root.
    call "%LAUNCHERS%\start_stack_supervisor.bat"
    exit /b %ERRORLEVEL%
)

if "%MODE%"=="" (
    echo [INFO] synenv ready. Starting full stack in synenv mode.
    call "%LAUNCHERS%\start_stack_synenv.bat"
    exit /b %ERRORLEVEL%
)

echo [ERROR] Unknown startup mode: %MODE%
echo.
goto usage_error

:ensure_synenv
if exist "%SYNENV_PY%" goto ensure_requirements

echo [BOOTSTRAP] synenv not found. Resolving system Python...
call :resolve_bootstrap_python
if not defined BOOTSTRAP_PY (
    echo [ERROR] No usable Python interpreter found.
    echo Install Python 3.11+ or ensure `py` / `python` is available in PATH.
    exit /b 1
)

echo [BOOTSTRAP] Creating synenv with:
echo   %BOOTSTRAP_PY%
"%BOOTSTRAP_PY%" -m venv "%SYNENV_DIR%"
if errorlevel 1 (
    echo [ERROR] Failed to create synenv.
    exit /b 1
)

:ensure_requirements
set "NEED_INSTALL=1"
if exist "%REQ_STAMP%" (
    for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$req = Get-Item '%REQ_FILE%'; $stamp = Get-Item '%REQ_STAMP%'; if ($req.LastWriteTimeUtc -le $stamp.LastWriteTimeUtc) { '0' } else { '1' }"`) do set "NEED_INSTALL=%%I"
)

if "%NEED_INSTALL%"=="0" (
    echo [BOOTSTRAP] Python dependencies already up to date.
    exit /b 0
)

echo [BOOTSTRAP] Installing Python dependencies from requirements.txt...
"%SYNENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip in synenv.
    exit /b 1
)

"%SYNENV_PY%" -m pip install -r "%REQ_FILE%"
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies.
    exit /b 1
)

powershell -NoProfile -Command "Set-Content -Path '%REQ_STAMP%' -Value (Get-Date).ToString('o') -Encoding ascii"
echo [BOOTSTRAP] Python dependencies ready.
exit /b 0

:resolve_bootstrap_python
set "BOOTSTRAP_PY="
py -3.11 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    for /f "usebackq delims=" %%I in (`py -3.11 -c "import sys; print(sys.executable)"`) do if not defined BOOTSTRAP_PY set "BOOTSTRAP_PY=%%I"
)
if defined BOOTSTRAP_PY exit /b 0

py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    for /f "usebackq delims=" %%I in (`py -3 -c "import sys; print(sys.executable)"`) do if not defined BOOTSTRAP_PY set "BOOTSTRAP_PY=%%I"
)
if defined BOOTSTRAP_PY exit /b 0

python -c "import sys" >nul 2>&1
if not errorlevel 1 (
    for /f "usebackq delims=" %%I in (`python -c "import sys; print(sys.executable)"`) do if not defined BOOTSTRAP_PY set "BOOTSTRAP_PY=%%I"
)
exit /b 0

:usage
echo SynapseAutomation root launcher
echo.
echo Usage:
echo   start.bat
echo   start.bat synenv
echo   start.bat conda
echo   start.bat supervisor
echo.
echo Modes:
echo   start.bat            Ensure synenv and requirements, then start full stack in synenv mode.
echo   start.bat synenv     Ensure synenv and start Redis, Celery, Playwright Worker, FastAPI, Frontend.
echo   start.bat conda      Start the same stack through the conda launcher.
echo   start.bat supervisor Ensure synenv and start Redis, Supervisor, and Frontend.
exit /b 0

:usage_error
call :usage
exit /b 1
