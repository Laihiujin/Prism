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
echo [2/5] Stopping Celery Worker...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'celery.*worker' } | Select-Object -ExpandProperty ProcessId -Unique | ForEach-Object { cmd /c taskkill /F /T /PID $_ >nul 2>&1 }"
echo [OK] Celery Worker stopped.

echo.
echo [3/5] Stopping Playwright Worker (port 7001)...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 7001 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { cmd /c taskkill /F /T /PID $_ >nul 2>&1 }"
echo [OK] Playwright Worker stopped.

echo.
echo [4/5] Stopping FastAPI Backend (port 7000)...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 7000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { cmd /c taskkill /F /T /PID $_ >nul 2>&1 }"
echo [OK] FastAPI Backend stopped.

echo.
echo [5/5] Stopping React Frontend (port 3000)...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { cmd /c taskkill /F /T /PID $_ >nul 2>&1 }"
echo [OK] React Frontend stopped.

echo.
echo [Optional] Stop Redis Server too?...
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
