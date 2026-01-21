@echo off
chcp 65001 >nul
REM Set UTF-8 encoding environment
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set "REDIS_CLI=redis-cli"
if exist "%~dp0syn_backend\Redis\redis-cli.exe" set "REDIS_CLI=%~dp0syn_backend\Redis\redis-cli.exe"
if exist "%~dp0syn_backend\Redis\redis-server.exe" set "SYNAPSE_REDIS_PATH=%~dp0syn_backend\Redis\redis-server.exe"

echo ============================================
echo   SynapseAutomation - Supervisor 模式启动
echo ============================================
echo.
echo 说明: 本模式使用 Supervisor 统一管理所有后端服务
echo   - Supervisor API: http://127.0.0.1:7002
echo   - 后端服务由 Supervisor 自动启动和管理
echo   - 适用于生产环境或需要远程控制服务的场景
echo.

REM 检查 Redis
echo [1] 检查 Redis 服务...
%REDIS_CLI% ping >nul 2>&1
if errorlevel 1 (
    echo ⚠️ Redis 未运行，正在启动...
    REM 使用本地 Redis（如果存在）
    if exist "%~dp0syn_backend\Redis\redis-server.exe" (
        start "Redis Server" "%~dp0syn_backend\Redis\redis-server.exe"
    ) else (
        start "Redis Server" redis-server
    )
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
echo [2] 启动 Supervisor（端口7002）...
echo     Supervisor 将自动启动以下服务:
echo       - Playwright Worker (端口7001)
echo       - FastAPI Backend (端口7000)
echo       - Celery Worker (任务队列)
echo.
start "Supervisor" "%~dp0start_supervisor_synenv.bat"
timeout /t 3 /nobreak >nul

echo.
echo [3] 启动 Frontend（前端界面，端口3000）...
start "React Frontend" "%~dp0scripts\launchers\start_frontend.bat"

echo.
echo ============================================
echo   ✅ Supervisor 模式已启动
echo ============================================
echo.
echo 服务列表:
echo   - Redis Server        (localhost:6379)
echo   - Supervisor API      (http://localhost:7002)
echo   - Playwright Worker   (localhost:7001) - 由 Supervisor 管理
echo   - FastAPI Backend     (http://localhost:7000) - 由 Supervisor 管理
echo   - Celery Worker       (任务队列) - 由 Supervisor 管理
echo   - React Frontend      (http://localhost:3000)
echo.
echo 提示:
echo   - Supervisor 窗口显示所有服务状态
echo   - 可通过 http://127.0.0.1:7002/api/status 查看服务状态
echo   - 可通过 API 远程控制服务启动/停止/重启
echo   - 服务日志保存在 logs 目录:
echo       * logs\supervisor.log
echo       * logs\backend.log
echo       * logs\playwright-worker.log
echo       * logs\celery-worker.log
echo.
pause
