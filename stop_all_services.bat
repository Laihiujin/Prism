@echo off
chcp 65001 >nul

set "REDIS_CLI=redis-cli"
if exist "%~dp0syn_backend\Redis\redis-cli.exe" set "REDIS_CLI=%~dp0syn_backend\Redis\redis-cli.exe"

echo ============================================
echo   停止所有 SynapseAutomation 服务
echo ============================================
echo.

echo [1/5] 停止 Celery Worker...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'celery.*worker' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo ✅ Celery Worker 已停止

echo.
echo [2/5] 停止 Playwright Worker (端口7001)...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 7001 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {} }"
echo ✅ Playwright Worker 已停止

echo.
echo [3/5] 停止 FastAPI Backend (端口7000)...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 7000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {} }"
echo ✅ FastAPI Backend 已停止

echo.
echo [4/5] 停止 React Frontend (端口3000)...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {} }"
echo ✅ React Frontend 已停止

echo.
echo [5/5] 停止 Redis Server (可选)...
set /p STOP_REDIS="是否停止 Redis Server？(Y/N): "
if /i "%STOP_REDIS%"=="Y" (
    %REDIS_CLI% shutdown >nul 2>&1
    echo ✅ Redis Server 已停止
) else (
    echo ⏭️ Redis Server 继续运行
)

echo.
echo ============================================
echo   ✅ 所有服务已停止
echo ============================================
echo.
pause
