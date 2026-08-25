@echo off
chcp 65001 >nul
echo ============================================
echo   Prism 一键测试脚�?
echo ============================================
echo.

set "ROOT=%~dp0.."
cd /d "%ROOT%"

echo [测试 1/5] 检�?prismenv Python...
if not exist "..\prismenv\Scripts\python.exe" (
    echo �?失败: prismenv Python 不存�?
    pause
    exit /b 1
)

call ..\prismenv\Scripts\activate.bat
python --version
echo �?通过
echo.

echo [测试 2/5] 检查后端依�?..
python -c "import fastapi, uvicorn, celery, playwright" 2>nul
if errorlevel 1 (
    echo �?失败: 后端依赖不完�?
    echo 请运�? pip install -r ..\prism_backend\requirements.txt
    pause
    exit /b 1
)
echo �?通过
echo.

echo [测试 3/5] 检�?Playwright 浏览�?..
set "PLAYWRIGHT_BROWSERS_PATH=%ROOT%\..\browsers"
if not exist "%PLAYWRIGHT_BROWSERS_PATH%\chromium" (
    echo �?失败: Chromium 浏览器未找到
    echo 请运�? .\scripts\launchers\setup_browser.bat
    pause
    exit /b 1
)
echo �?通过
echo.

echo [测试 4/5] 测试后端启动 (10秒测�?...
cd ..\prism_backend
start /B python fastapi_app\run.py > test_backend.log 2>&1
timeout /t 5 /nobreak >nul

REM 检查端�?7000
powershell -Command "Test-NetConnection -ComputerName localhost -Port 7000 -InformationLevel Quiet" >nul 2>&1
if errorlevel 1 (
    echo �?失败: 后端未在端口 7000 启动
    echo 查看日志: prism_backend\test_backend.log
    taskkill /F /IM python.exe >nul 2>&1
    pause
    exit /b 1
)
echo �?通过

REM 停止测试进程
taskkill /F /IM python.exe >nul 2>&1
cd ..\desktop-electron
echo.

echo [测试 5/5] 检�?Electron 依赖...
if not exist "node_modules" (
    echo �?失败: node_modules 未找�?
    echo 请运�? npm install
    pause
    exit /b 1
)
echo �?通过
echo.

echo ============================================
echo �?所有测试通过!
echo ============================================
echo.
echo 可以开始打�?
echo   1. 运行准备脚本: .\scripts\prepare-supervisor-build.bat
echo   2. 开始打�? npm run build
echo.
pause
