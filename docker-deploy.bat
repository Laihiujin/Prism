@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "runtime-data" mkdir "runtime-data"
if not exist "runtime-data\\app" mkdir "runtime-data\\app"
if not exist "runtime-data\\redis" mkdir "runtime-data\\redis"

echo [INFO] Building and starting SynapseAutomation Docker stack...
docker compose up -d --build
if errorlevel 1 exit /b %ERRORLEVEL%

echo [INFO] Waiting for backend health...
powershell -NoProfile -Command "$deadline=(Get-Date).AddMinutes(3); do { try { $r=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:7000/health -TimeoutSec 5; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Seconds 2 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
  echo [ERROR] Backend health check timed out.
  exit /b 1
)

echo [INFO] Waiting for frontend health...
powershell -NoProfile -Command "$deadline=(Get-Date).AddMinutes(3); do { try { $r=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3000 -TimeoutSec 5; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } } catch {}; Start-Sleep -Seconds 2 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
  echo [ERROR] Frontend health check timed out.
  exit /b 1
)

echo.
echo [OK] SynapseAutomation Docker services are ready.
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:7000
echo Docs:     http://localhost:7000/api/docs
echo.
docker compose ps

echo.
echo [INFO] Launching Electron desktop...
start "" cmd /c call "\"%~dp0launch-electron-desktop.bat\""
