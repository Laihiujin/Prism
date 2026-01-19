@echo off
chcp 65001 >nul
echo ============================================
echo   测试 Supervisor 路径和启动
echo ============================================
echo.

set "ROOT=%~dp0..\..\.."
set "RESOURCES=%ROOT%\desktop-electron\dist-build\win-unpacked\resources"

echo [1/5] 检查打包目录...
if not exist "%RESOURCES%" (
    echo ❌ 打包目录不存在: %RESOURCES%
    echo 请先运行: cd desktop-electron ^&^& npm run build:dir
    pause
    exit /b 1
)
echo ✅ 打包目录存在
echo.

echo [2/5] 检查关键路径...
echo 检查 synenv...
if exist "%RESOURCES%\synenv\Scripts\python.exe" (
    echo ✅ synenv\Scripts\python.exe 存在
) else (
    echo ❌ synenv\Scripts\python.exe 不存在
)

echo 检查 backend...
if exist "%RESOURCES%\backend" (
    echo ✅ backend 目录存在
    dir /B "%RESOURCES%\backend" | findstr "fastapi_app playwright_worker" && echo ✅ 后端模块存在 || echo ⚠️ 后端模块不完整
) else (
    echo ❌ backend 目录不存在
)

echo 检查 browsers...
if exist "%RESOURCES%\browsers\chromium" (
    echo ✅ browsers\chromium 存在
) else (
    echo ❌ browsers\chromium 不存在
)

echo 检查 redis...
if exist "%RESOURCES%\redis\redis-server.exe" (
    echo ✅ redis\redis-server.exe 存在
) else (
    echo ❌ redis\redis-server.exe 不存在
)

echo 检查 supervisor...
if exist "%RESOURCES%\supervisor\supervisor.exe" (
    echo ✅ supervisor\supervisor.exe 存在
    dir "%RESOURCES%\supervisor\supervisor.exe" | findstr /C:"supervisor.exe"
) else (
    echo ❌ supervisor\supervisor.exe 不存在
)
echo.

echo [3/5] 测试 Python 环境...
cd /d "%RESOURCES%"
if exist "synenv\Scripts\python.exe" (
    synenv\Scripts\python.exe --version
    echo ✅ Python 可执行
) else (
    echo ❌ Python 不可执行
)
echo.

echo [4/5] 查看目录结构...
echo.
echo synenv 大小:
du -sh synenv 2>nul || echo "(未安装 du 命令)"
echo backend 大小:
du -sh backend 2>nul || echo "(未安装 du 命令)"
echo.
echo Backend 子目录:
dir /B backend
echo.

echo [5/5] 测试 Supervisor (5秒测试)...
echo.
echo 启动 Supervisor (将在5秒后自动终止)...
start /B supervisor\supervisor.exe > supervisor_test.log 2>&1

timeout /t 5 /nobreak >nul

echo.
echo 查看 Supervisor 输出:
type supervisor_test.log
echo.

REM 停止测试进程
taskkill /F /IM supervisor.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1

echo.
echo ============================================
echo   测试完成
echo ============================================
echo.
echo 查看完整日志: %RESOURCES%\supervisor_test.log
echo.
pause
