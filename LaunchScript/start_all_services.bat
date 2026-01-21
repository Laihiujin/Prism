@echo off
chcp 65001 >nul
REM Set UTF-8 encoding environment
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set "REDIS_CLI=redis-cli"
if exist "%~dp0syn_backend\Redis\redis-cli.exe" set "REDIS_CLI=%~dp0syn_backend\Redis\redis-cli.exe"

echo ============================================
echo   SynapseAutomation 全服务启动
echo ============================================
echo.

REM 
echo [1] 检查 Redis 服务...
%REDIS_CLI% ping >nul 2>&1
if errorlevel 1 (
    echo ⚠️ Redis 未运行，正在启动...
    start "Redis Server" redis-server
    timeout /t 3 /nobreak >nul

    REM 再次检查
    %REDIS_CLI% ping >nul 2>&1
    if errorlevel 1 (
        echo ❌ Redis 启动失败，请手动运行: redis-server
        pause
        exit /b 1
    )
    echo ✅ Redis 已启动
) else (
    echo ✅ Redis 运行正常
)

echo.
echo [2] 启动 Celery Worker（发布任务队列）...
start "Celery Worker" "%~dp0start_celery_worker.bat"
timeout /t 2 /nobreak >nul

echo.
echo [3] 启动 Playwright Worker（浏览器自动化，端口7001）...
start "Playwright Worker" "%~dp0scripts\launchers\start_worker.bat"
timeout /t 3 /nobreak >nul

echo.
echo [4] 启动 FastAPI Backend（后端API，端口7000）...
start "FastAPI Backend" "%~dp0scripts\launchers\start_backend.bat"
timeout /t 3 /nobreak >nul

echo.
echo [5] 启动 Frontend（前端界面，端口3000）...
start "React Frontend" "%~dp0scripts\launchers\start_frontend.bat"

echo.
echo ============================================
echo   ✅ 所有服务已启动
echo ============================================
echo.
echo 服务列表:
echo   - Redis Server        (localhost:6379)
echo   - Celery Worker       (任务队列)
echo   - Playwright Worker   (localhost:7001)
echo   - FastAPI Backend     (http://localhost:7000)
echo   - React Frontend      (http://localhost:3000)
echo.
echo 提示:
echo   - 各服务会在独立窗口中运行
echo   - 关闭窗口即可停止对应服务
echo   - 查看日志请切换到对应窗口
echo.
pause
