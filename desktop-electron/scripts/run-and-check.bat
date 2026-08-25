@echo off
chcp 65001 >nul
echo ============================================
echo   启动打包程序并查看日志
echo ============================================
echo.

set "APP=%~dp0..\dist-build\win-unpacked\Prism.exe"
set "RES=%~dp0..\dist-build\win-unpacked\resources"

if not exist "%APP%" (
    echo ❌ 程序不存在: %APP%
    pause
    exit /b 1
)

echo ✅ 找到程序: %APP%
echo.
echo 🚀 启动程序 (10秒后自动查看日志)...
start "" "%APP%"

timeout /t 10 /nobreak >nul

echo.
echo ============================================
echo   查看启动日志
echo ============================================
echo.

echo [1] Supervisor 主日志:
type "%RES%\supervisor\supervisor.log" 2>nul | tail -50
echo.

echo [2] Backend 日志:
type "%RES%\supervisor\backend.log" 2>nul | tail -30
echo.

echo [3] Automation Worker 日志:
type "%RES%\supervisor\automation-worker.log" 2>nul | tail -20
echo.

echo [4] Celery Worker 日志:
type "%RES%\supervisor\celery-worker.log" 2>nul | tail -20
echo.

echo ============================================
echo   检查进程状态
echo ============================================
tasklist | findstr /I "python.exe supervisor.exe redis"
echo.

echo ============================================
echo   检查端口占用
echo ============================================
netstat -ano | findstr "7000 7001 6379"
echo.

pause
