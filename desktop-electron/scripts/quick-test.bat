@echo off
chcp 65001 >nul
echo ============================================
echo   快速测试打包后的程序启动
echo ============================================
echo.

set "APP_DIR=%~dp0..\dist-build\win-unpacked"
set "RES_DIR=%APP_DIR%\resources"

cd /d "%RES_DIR%"

echo [测试 1/2] 检查关键文件...
echo.
if exist "prismenv\Scripts\python.exe" (
    echo ✅ Python: prismenv\Scripts\python.exe
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
echo.

echo [测试 2/2] 手动测试 Python 启动后端...
echo.
echo 测试命令: prismenv\Scripts\python.exe backend\fastapi_app\run.py
echo.
echo 将在 5 秒后启动,然后自动停止...
timeout /t 2 /nobreak >nul

start /B prismenv\Scripts\python.exe backend\fastapi_app\run.py > test_backend.log 2>&1

timeout /t 5 /nobreak >nul

echo.
echo 查看后端输出 (前 30 行):
type test_backend.log | more

REM 停止测试
taskkill /F /IM python.exe >nul 2>&1

echo.
echo ============================================
echo   测试完成
echo ============================================
echo.
echo 日志文件:
echo   - %RES_DIR%\test_backend.log
echo.
pause
