@echo off
chcp 65001 >nul

REM Set UTF-8 encoding environment
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set "ROOT=%~dp0..\.."
set "BACKEND_DIR=%ROOT%\syn_backend"
set "VENV_PATH=%ROOT%\synenv"
set "PY=%VENV_PATH%\Scripts\python.exe"
if not defined BACKEND_PORT set "BACKEND_PORT=7000"
if not defined SYN_BACKEND_PORT set "SYN_BACKEND_PORT=%BACKEND_PORT%"
if not defined SYN_BACKEND_URL set "SYN_BACKEND_URL=http://127.0.0.1:%BACKEND_PORT%"
if not defined PORT set "PORT=%BACKEND_PORT%"

echo ========================================
echo   Synapse Backend Startup (synenv)
echo ========================================
echo.

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
echo.

for /f "usebackq tokens=*" %%A in (`powershell -NoProfile -Command "$conn = Get-NetTCPConnection -LocalPort %BACKEND_PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if ($conn) { $conn.OwningProcess }"`) do set "PORT_OWNER=%%A"
if defined PORT_OWNER (
    echo [ERROR] Port %BACKEND_PORT% is already in use by PID %PORT_OWNER%.
    echo         Set BACKEND_PORT to a free port or stop that process first.
    pause
    exit /b 1
)

REM Bundle Playwright browsers inside this repo (important for packaging to exe)
REM Playwright 会自动在 browsers 目录下查找对应版本的浏览器
set "PLAYWRIGHT_BROWSERS_PATH=%ROOT%\browsers"
if not defined MANUS_API_BASE_URL set "MANUS_API_BASE_URL=%SYN_BACKEND_URL%/api/v1"
if not defined AGENT_API_BASE_URL set "AGENT_API_BASE_URL=%MANUS_API_BASE_URL%"
REM Enable OCR/Selenium helpers (can be overridden by existing env vars)
if not defined ENABLE_OCR_RESCUE set "ENABLE_OCR_RESCUE=1"
if not defined ENABLE_SELENIUM_RESCUE set "ENABLE_SELENIUM_RESCUE=1"
if not defined ENABLE_SELENIUM_DEBUG set "ENABLE_SELENIUM_DEBUG=1"
REM Disable Playwright auto-install in synenv to avoid startup hangs
if not defined PLAYWRIGHT_AUTO_INSTALL set "PLAYWRIGHT_AUTO_INSTALL=0"
if not defined START_CELERY set "START_CELERY=1"
if not defined FORCE_CELERY set "FORCE_CELERY=0"
echo [CONFIG] Playwright path: %PLAYWRIGHT_BROWSERS_PATH%
echo [CONFIG] OCR rescue: %ENABLE_OCR_RESCUE%  Selenium rescue: %ENABLE_SELENIUM_RESCUE%  Selenium debug: %ENABLE_SELENIUM_DEBUG%
echo.

pushd "%BACKEND_DIR%"

echo [1/7] Checking Python environment...
%PY% --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python cannot run
    popd
    pause
    exit /b 1
)
echo OK Python environment normal
echo.

echo [2/7] Ensuring Playwright Chromium...
REM Skip Playwright check in synenv mode to avoid startup failures
echo [SKIP] Playwright check disabled for synenv environment
echo.

echo [3/7] Checking environment configuration...
if not exist ".env" (
    echo [WARNING] .env file not found
    if exist ".env.example" (
        echo Creating .env from .env.example...
        copy .env.example .env >nul
        echo OK Created .env file
    )
) else (
    echo OK Environment configuration file exists
)
echo.

echo [4/7] Checking database files...
if not exist "db\database.db" (
    echo [WARNING] Main database file not found
)
if not exist "db\cookie_store.db" (
    echo [WARNING] Cookie database file not found
)
echo.



REM Celery will be started by main launcher, skip here
set "START_CELERY=0"

echo [5/7] Checking Redis connectivity...
set "REDIS_CHECK=FAIL"
for /f "usebackq tokens=*" %%A in (`powershell -NoProfile -Command "try { $r = Test-NetConnection -ComputerName localhost -Port 6379 -WarningAction SilentlyContinue; if ($r.TcpTestSucceeded) { 'OK' } else { 'FAIL' } } catch { 'FAIL' }"`) do set "REDIS_CHECK=%%A"
if /I "%REDIS_CHECK%"=="OK" (
    echo OK Redis reachable on localhost:6379
) else (
    echo [WARNING] Redis not reachable on localhost:6379
    if "%FORCE_CELERY%"=="1" (
        echo [FORCE] FORCE_CELERY=1, will start Celery anyway
    ) else (
        set "START_CELERY=0"
    )
)
echo.

echo [6/7] Starting Celery Worker...
if "%START_CELERY%"=="1" (
    start "Celery Worker" %PY% -m celery -A fastapi_app.tasks.celery_app.celery_app worker -l info --hostname=synapse-worker@%%h-%RANDOM%
    echo OK Celery worker launched
) else (
    echo [SKIP] START_CELERY=%START_CELERY%
)
echo.

echo ========================================
echo   [7/7] Starting FastAPI Service (Port: %BACKEND_PORT%)
echo ========================================
echo.
echo Access URLs:
echo   - API: %SYN_BACKEND_URL%/api/v1
echo   - API Docs: %SYN_BACKEND_URL%/api/docs
echo   - ReDoc: %SYN_BACKEND_URL%/api/redoc
echo   - Health Check: %SYN_BACKEND_URL%/health
echo.
echo Press Ctrl+C to stop service
echo ========================================
echo.

%PY% fastapi_app/run.py
set "RC=%ERRORLEVEL%"
popd

if not "%RC%"=="0" (
    echo.
    echo [ERROR] Service startup failed
    pause
    exit /b 1
)

pause
