@echo off
chcp 65001 >nul
echo ============================================
echo   SynapseAutomation 启动和诊断
echo ============================================
echo.

set "APP_DIR=%~dp0..\dist-build\win-unpacked"
set "RES_DIR=%APP_DIR%\resources"
set "SUP_DIR=%RES_DIR%\supervisor"

echo [1/6] 检查文件...
if not exist "%APP_DIR%\SynapseAutomation.exe" (
    echo ❌ 程序不存在
    pause
    exit /b 1
)
echo ✅ 程序文件存在
echo.

echo [2/6] 清理旧日志...
del /q "%SUP_DIR%\*.log" 2>nul
echo ✅ 日志已清理
echo.

echo [3/6] 启动程序...
start "" "%APP_DIR%\SynapseAutomation.exe"
echo ✅ 程序已启动
echo.

echo [4/6] 等待服务启动 (15秒)...
echo.
timeout /t 15 /nobreak

echo [5/6] 检查进程状态...
echo.
echo Python 进程:
tasklist | findstr /I "python.exe" | findstr /V "findstr"
echo.
echo Supervisor 进程:
tasklist | findstr /I "supervisor.exe" | findstr /V "findstr"
echo.
echo Redis 进程:
tasklist | findstr /I "redis-server.exe" | findstr /V "findstr"
echo.

echo [6/6] 检查端口占用...
echo.
echo 端口 7000 (Backend):
netstat -ano | findstr ":7000 "
echo.
echo 端口 6379 (Redis):
netstat -ano | findstr ":6379 "
echo.

echo ============================================
echo   查看日志文件
echo ============================================
echo.

if exist "%SUP_DIR%\supervisor.log" (
    echo [Supervisor 主日志] (最后 20 行):
    powershell -Command "Get-Content '%SUP_DIR%\supervisor.log' -Tail 20"
    echo.
) else (
    echo ⚠️ supervisor.log 不存在
)

if exist "%SUP_DIR%\backend.log" (
    echo [Backend 日志] (最后 30 行):
    powershell -Command "Get-Content '%SUP_DIR%\backend.log' -Tail 30"
    echo.
) else (
    echo ⚠️ backend.log 不存在 (后端可能未启动)
)

if exist "%SUP_DIR%\playwright-worker.log" (
    echo [Playwright Worker 日志] (最后 15 行):
    powershell -Command "Get-Content '%SUP_DIR%\playwright-worker.log' -Tail 15"
    echo.
) else (
    echo ⚠️ playwright-worker.log 不存在
)

if exist "%SUP_DIR%\celery-worker.log" (
    echo [Celery Worker 日志] (最后 15 行):
    powershell -Command "Get-Content '%SUP_DIR%\celery-worker.log' -Tail 15"
    echo.
) else (
    echo ⚠️ celery-worker.log 不存在
)

echo ============================================
echo   主进程日志
echo ============================================
if exist "%APPDATA%\synapse-automation\logs\main.log" (
    echo [Electron Main Process] (最后 20 行):
    powershell -Command "Get-Content '$env:APPDATA\synapse-automation\logs\main.log' -Tail 20"
) else (
    echo ⚠️ main.log 不存在
)

echo.
echo ============================================
echo   诊断完成
echo ============================================
echo.
echo 日志文件位置:
echo   - Supervisor: %SUP_DIR%\supervisor.log
echo   - Backend: %SUP_DIR%\backend.log
echo   - Worker: %SUP_DIR%\playwright-worker.log
echo   - Celery: %SUP_DIR%\celery-worker.log
echo   - Main: %%APPDATA%%\synapse-automation\logs\main.log
echo.
pause
