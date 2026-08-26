@echo off
chcp 65001 >nul
echo ============================================
echo   Prism Dev Quick Start
echo ============================================
echo.

set "ROOT=%~dp0.."
cd /d "%ROOT%"

REM Check environment
if not exist "node_modules" (
    echo [ERROR] node_modules not found
    echo Run: npm install
    pause
    exit /b 1
)

if not exist "..\prismenv" (
    echo [ERROR] prismenv not found
    echo Create: python -m venv prismenv
    pause
    exit /b 1
)

echo [OK] Environment check passed
echo.

REM Dev mode: do not auto-start services
set "PRISM_START_SERVICES=0"

echo Starting Electron (dev mode)...
echo.
echo NOTE: Dev mode does not auto-start backend services.
echo Start them manually:
echo    1. Backend: ..\scripts\launchers\start_backend_prismenv.bat
echo    2. Worker:  ..\scripts\launchers\start_worker.bat
echo    3. Celery:  ..\scripts\launchers\start_celery_prismenv.bat
echo    4. Frontend: cd ..\prism_frontend ^&^& npm run dev
echo.

npm run dev

pause
