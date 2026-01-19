@echo off
chcp 65001 >nul
echo ============================================
echo   SynapseAutomation Supervisor Build Prep
echo ============================================
echo.

set "ROOT=%~dp0..\.."
cd /d "%ROOT%"
if exist "syn_backend\Redis\redis-server.exe" set "SYNAPSE_REDIS_PATH=%ROOT%\syn_backend\Redis\redis-server.exe"

echo [1/6] Checking required folders...
if not exist "synenv" (
    echo [ERROR] synenv not found.
    echo Please run: python -m venv synenv
    pause
    exit /b 1
)
echo OK synenv exists.

if not exist "browsers" (
    echo [ERROR] browsers folder not found.
    echo Please run: .\scripts\launchers\setup_browser.bat
    pause
    exit /b 1
)
echo OK browsers exists.

if not exist "syn_backend" (
    echo [ERROR] syn_backend folder not found.
    pause
    exit /b 1
)
echo OK syn_backend exists.

echo.
echo [2/6] Preparing Redis...
if not exist "desktop-electron\resources\redis" (
    mkdir "desktop-electron\resources\redis"
)

REM Download Redis for Windows (if missing)
if not exist "desktop-electron\resources\redis\redis-server.exe" (
    echo Download Redis for Windows manually.
    echo Place it at: desktop-electron\resources\redis\
    echo URL: https://github.com/tporadowski/redis/releases
    echo.
    pause
) else (
    echo OK Redis ready.
)

echo.
echo [3/6] Installing desktop-electron dependencies...
cd desktop-electron
if not exist "node_modules" (
    echo Installing npm dependencies...
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed.
        pause
        exit /b 1
    )
) else (
    echo OK node_modules exists.
)
cd ..

echo.
echo [4/6] Building Supervisor EXE (PyInstaller)...
call synenv\Scripts\activate.bat

REM Check PyInstaller
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Build supervisor
if not exist "desktop-electron\resources\supervisor\supervisor.exe" (
    set "SUPERVISOR_SRC=desktop-electron\resources\supervisor\supervisor.py"
    if not exist "%SUPERVISOR_SRC%" (
        set "SUPERVISOR_SRC=desktop-electron\dist-build\win-unpacked\resources\supervisor\supervisor.py"
    )
    if not exist "%SUPERVISOR_SRC%" (
        echo [ERROR] supervisor.py not found in resources or dist.
        deactivate
        pause
        exit /b 1
    )
    if not exist "desktop-electron\resources\supervisor" (
        mkdir "desktop-electron\resources\supervisor"
    )
    echo Building supervisor.py...
    python -m PyInstaller --onefile ^
        --name supervisor ^
        --distpath "desktop-electron\resources\supervisor" ^
        --workpath "build\supervisor" ^
        --specpath "build" ^
        --console ^
        --noconfirm ^
        "%SUPERVISOR_SRC%"

    if errorlevel 1 (
        echo [WARN] Build failed; fallback is supervisor.py.
    ) else (
        echo OK Supervisor built.
    )
) else (
    echo OK supervisor.exe exists.
)

deactivate

echo.
echo [5/6] Cleaning Python cache...
for /r "%ROOT%\syn_backend" %%d in (__pycache__) do (
    if exist "%%d" (
        echo Cleaning: %%d
        rd /s /q "%%d" 2>nul
    )
)

REM Delete .pyc files
del /s /q "%ROOT%\syn_backend\*.pyc" 2>nul

echo OK cleanup done.

echo.
echo [6/6] Validating build prerequisites...
set "CHECK_OK=1"

if not exist "synenv\Scripts\python.exe" (
    echo [ERROR] synenv Python missing.
    set "CHECK_OK=0"
)

if not exist "browsers\chromium" (
    echo [ERROR] Chromium not found.
    set "CHECK_OK=0"
)

if not exist "syn_backend\fastapi_app\run.py" (
    echo [ERROR] Backend entry not found.
    set "CHECK_OK=0"
)

if "%CHECK_OK%"=="0" (
    echo.
    echo [ERROR] Build prerequisites failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo OK Build prep complete.
echo ============================================
echo.
echo Next:
echo   cd desktop-electron
echo   npm run build

echo.
echo Notes:
echo   1. Ensure Redis is in desktop-electron\resources\redis\
echo   2. Build may take 10-30 minutes
echo   3. Output is in desktop-electron\dist-build\
echo.
pause
