@echo off
chcp 65001 >nul
echo ============================================
echo   Prism 启动和诊断
echo ============================================
echo.

set "APP_DIR=%~dp0..\dist-build\win-unpacked"
set "RES_DIR=%APP_DIR%\resources"

echo [1/4] 检查文件...
if not exist "%APP_DIR%\Prism.exe" (
    echo ❌ 程序不存在
    pause
    exit /b 1
)
echo ✅ 程序文件存在
echo.

echo [2/4] 清理旧日志...
del /q "%RES_DIR%\*.log" 2>nul
echo ✅ 日志已清理
echo.

echo [3/4] 启动程序...
start "" "%APP_DIR%\Prism.exe"
echo ✅ 程序已启动
echo.

echo [4/4] 等待服务启动 (15秒)...
echo.
timeout /t 15 /nobreak

echo.
echo ============================================
echo   查看日志文件
echo ============================================
echo.

if exist "%RES_DIR%\backend.log" (
    echo [Backend 日志] (最后 30 行):
    powershell -Command "Get-Content '%RES_DIR%\backend.log' -Tail 30"
    echo.
) else (
    echo ⚠️ backend.log 不存在 (后端可能未启动)
)

if exist "%RES_DIR%\automation-worker.log" (
    echo [Automation Worker 日志] (最后 15 行):
    powershell -Command "Get-Content '%RES_DIR%\automation-worker.log' -Tail 15"
    echo.
) else (
    echo ⚠️ automation-worker.log 不存在
)

if exist "%RES_DIR%\celery-worker.log" (
    echo [Celery Worker 日志] (最后 15 行):
    powershell -Command "Get-Content '%RES_DIR%\celery-worker.log' -Tail 15"
    echo.
) else (
    echo ⚠️ celery-worker.log 不存在
)

echo ============================================
echo   主进程日志
echo ============================================
if exist "%APPDATA%\prism-automation\logs\main.log" (
    echo [Electron Main Process] (最后 20 行):
    powershell -Command "Get-Content '$env:APPDATA\prism-automation\logs\main.log' -Tail 20"
) else (
    echo ⚠️ main.log 不存在
)

echo.
echo ============================================
echo   诊断完成
echo ============================================
echo.
echo 日志文件位置:
echo   - Backend: %RES_DIR%\backend.log
echo   - Worker: %RES_DIR%\automation-worker.log
echo   - Celery: %RES_DIR%\celery-worker.log
echo   - Main: %%APPDATA%%\prism-automation\logs\main.log
echo.
pause
