@echo off

REM Set UTF-8 encoding environment
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8 
chcp 65001 >nul

echo ========================================
echo   Synapse 前端启动脚本
echo ========================================
echo.

set "ROOT=%~dp0..\.."
set "FRONTEND_DIR=%ROOT%\\syn_frontend_react"
if not defined BACKEND_PORT set "BACKEND_PORT=7000"
if not defined SYN_BACKEND_URL set "SYN_BACKEND_URL=http://127.0.0.1:%BACKEND_PORT%"
pushd "%FRONTEND_DIR%"

REM 检查并停止占用的进程
echo
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    echo [警告]  3000 被进程 %%a 占用，正在尝试关闭...
    taskkill /F /PID %%a >nul 2>&1
)

REM 检查 node_modules
if not exist "node_modules" (
    echo [安装] 未找到 node_modules，正在安装依赖...
    call npm install
    if errorlevel 1 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
)

REM 清理缓存
echo [清理] 清理 Next.js 缓存...
if exist ".next" (
    rd /s /q ".next" 2>nul
)

REM 设置环境变量
echo [配置] 设置环境变量...
set NEXT_PUBLIC_BACKEND_URL=%SYN_BACKEND_URL%
set NEXT_PUBLIC_API_URL=%SYN_BACKEND_URL%
set NEXT_PUBLIC_SYN_BACKEND_URL=%SYN_BACKEND_URL%
set PORT=3000

REM 启动开发服务器
echo [启动] 启动前端开发服务器 ( %PORT%)...
echo.
echo 访问地址: http://localhost:%PORT%
echo AI 助手: http://localhost:%PORT%/ai-agent
echo.

call npm run dev

popd
pause
