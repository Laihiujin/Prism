@echo off
chcp 65001 >nul

set "ROOT=%~dp0..\.."

set "REDIS_CLI=redis-cli"
if exist "%ROOT%\syn_backend\Redis\redis-cli.exe" set "REDIS_CLI=%ROOT%\syn_backend\Redis\redis-cli.exe"

echo ============================================
echo   Stop All SynapseAutomation Services
echo ============================================
echo.

echo [1/8] Stopping Supervisor API (port 7002)...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 7002 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { cmd /c taskkill /F /T /PID $_ >nul 2>&1 }; Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'supervisor\.py|supervisor\.exe' } | Select-Object -ExpandProperty ProcessId -Unique | ForEach-Object { cmd /c taskkill /F /T /PID $_ >nul 2>&1 }"
echo [OK] Supervisor stopped.

echo.
echo [2/8] Stopping Hermes Gateway...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'hermes_cli\.main.*gateway|hermes_cli\\main\.py.*gateway' } | Select-Object -ExpandProperty ProcessId -Unique | ForEach-Object { cmd /c taskkill /F /T /PID $_ >nul 2>&1 }"
echo [OK] Hermes Gateway stopped.

echo.
echo [3/8] Stopping Hermes Dashboard (port 9119)...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 9119 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { cmd /c taskkill /F /T /PID $_ >nul 2>&1 }"
echo [OK] Hermes Dashboard stopped.

echo.
echo [4/8] Stopping Hermes WebUI (port 9131)...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 9131 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { cmd /c taskkill /F /T /PID $_ >nul 2>&1 }"
echo [OK] Hermes WebUI stopped.

echo.
echo [5/8] Stopping Celery Worker...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'celery.*worker' } | Select-Object -ExpandProperty ProcessId -Unique | ForEach-Object { cmd /c taskkill /F /T /PID $_ >nul 2>&1 }"
echo [OK] Celery Worker stopped.

echo.
echo [6/8] Stopping Playwright Worker (port 7001)...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 7001 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { cmd /c taskkill /F /T /PID $_ >nul 2>&1 }"
echo [OK] Playwright Worker stopped.

echo.
echo [7/8] Stopping FastAPI Backend (port 7000)...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 7000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { cmd /c taskkill /F /T /PID $_ >nul 2>&1 }"
echo [OK] FastAPI Backend stopped.

echo.
echo [8/8] Stopping React Frontend (port 3000)...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { cmd /c taskkill /F /T /PID $_ >nul 2>&1 }"
echo [OK] React Frontend stopped.

echo.
echo [5/5] Stop Redis Server (optional)...
set /p STOP_REDIS="Stop Redis Server too? (Y/N): "
if /i "%STOP_REDIS%"=="Y" (
    %REDIS_CLI% shutdown >nul 2>&1
    echo [OK] Redis Server stopped.
) else (
    echo [SKIP] Redis Server left running.
)

echo.
echo ============================================
echo   [OK] All services stopped
echo ============================================
echo.
pause
