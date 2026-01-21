@echo off
chcp 65001 >nul
echo ============================================
echo   SynapseAutomation Dev Quick Start
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

if not exist "..\synenv" (
    echo [ERROR] synenv not found
    echo Create: python -m venv synenv
    pause
    exit /b 1
)

echo [OK] Environment check passed
echo.

REM Dev mode: do not auto-start services
set "SYNAPSE_START_SERVICES=0"

echo Starting Electron (dev mode)...
echo.
echo NOTE: Dev mode does not auto-start backend services.
echo Start them manually:
echo    1. Backend: ..\scripts\launchers\start_backend_synenv.bat
echo    2. Worker:  ..\scripts\launchers\start_worker.bat
echo    3. Celery:  ..\start_celery_worker_synenv.bat
echo    4. Frontend: cd ..\syn_frontend_react ^&^& npm run dev
echo.

npm run dev

pause
