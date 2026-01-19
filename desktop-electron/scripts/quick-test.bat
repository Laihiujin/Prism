@echo off
chcp 65001 >nul
echo ============================================
echo   快速测试打包后的程序启动
echo ============================================
echo.

set "APP_DIR=%~dp0..\dist-build\win-unpacked"
set "RES_DIR=%APP_DIR%\resources"

cd /d "%RES_DIR%"

echo [测试 1/3] 检查关键文件...
echo.
if exist "synenv\Scripts\python.exe" (
    echo ✅ Python: synenv\Scripts\python.exe
) else (
    echo ❌ Python 不存在
    pause
    exit /b 1
)

if exist "backend\fastapi_app\run.py" (
    echo ✅ Backend: backend\fastapi_app\run.py
) else (
    echo ❌ Backend 不存在
    pause
    exit /b 1
)

if exist "supervisor\supervisor.exe" (
    echo ✅ Supervisor: supervisor\supervisor.exe
    dir supervisor\supervisor.exe | findstr "supervisor"
) else (
    echo ❌ Supervisor 不存在
    pause
    exit /b 1
)
echo.

echo [测试 2/3] 手动测试 Python 启动后端...
echo.
echo 测试命令: synenv\Scripts\python.exe backend\fastapi_app\run.py
echo.
echo 将在 5 秒后启动,然后自动停止...
timeout /t 2 /nobreak >nul

start /B synenv\Scripts\python.exe backend\fastapi_app\run.py > test_backend.log 2>&1

timeout /t 5 /nobreak >nul

echo.
echo 查看后端输出 (前 30 行):
type test_backend.log | more

REM 停止测试
taskkill /F /IM python.exe >nul 2>&1

echo.
echo [测试 3/3] 测试 Supervisor...
echo.
echo 启动 Supervisor (5秒测试)...
start /B supervisor\supervisor.exe > test_supervisor.log 2>&1

timeout /t 5 /nobreak >nul

echo.
echo 查看 Supervisor 输出:
type test_supervisor.log
echo.

if exist "supervisor\supervisor.log" (
    echo.
    echo Supervisor 内部日志:
    type supervisor\supervisor.log | more
)

REM 清理
taskkill /F /IM supervisor.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM redis-server.exe >nul 2>&1

echo.
echo ============================================
echo   测试完成
echo ============================================
echo.
echo 日志文件:
echo   - %RES_DIR%\test_backend.log
echo   - %RES_DIR%\test_supervisor.log
echo   - %RES_DIR%\supervisor\supervisor.log
echo.
pause
