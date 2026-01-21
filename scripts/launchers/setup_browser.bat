@echo off
chcp 65001 >nul
echo ==========================================
echo   Synapse 浏览器环境快速设置
echo ==========================================
echo

set "ROOT=%~dp0..\.."
set "BACKEND_DIR=%ROOT%\syn_backend"

REM Activate conda environment (syn)
call conda activate syn
if errorlevel 1 (
    echo [ERROR] Failed to activate conda environment 'syn'
    echo Please run: conda create -n syn python=3.11
    pause
    exit /b 1
)
echo [1/4] OK Activated conda environment 'syn'
echo.

REM Set Playwright browser path to local directory
REM Playwright 会自动在 browsers 目录下查找对应版本的浏览器
set "PLAYWRIGHT_BROWSERS_PATH=%ROOT%\browsers"
echo [CONFIG] Playwright browser path: %PLAYWRIGHT_BROWSERS_PATH%
echo.

REM 2. 检查 Playwright
echo [2/4] 检查 Playwright...
python -c "import playwright" >nul 2>&1
if errorlevel 1 (
    echo ! Playwright 未安装，正在安装...
    pip install playwright
    if errorlevel 1 (
        echo [ERROR] Playwright 安装失败
        pause
        exit /b 1
    )
) else (
    echo ✓ Playwright 已安装
)
echo.

REM 3. 安装 Playwright 浏览器到本地目录
echo [3/4] 安装 Playwright Chromium 到本地目录...
echo 浏览器将安装到: %PLAYWRIGHT_BROWSERS_PATH%
echo 这可能需要几分钟时间...
echo.
REM 必须在同一个命令中设置环境变量并执行安装
cmd /c "set PLAYWRIGHT_BROWSERS_PATH=%PLAYWRIGHT_BROWSERS_PATH% && playwright install chromium"
if errorlevel 1 (
    echo [WARNING] Chromium 安装可能失败，但会尝试继续...
)
echo.

REM 4. 验证安装
echo [4/4] 验证浏览器安装...
pushd "%BACKEND_DIR%"
python -c "import sys; print(f'Python版本: {sys.version}')"
python -c "import playwright; print(f'Playwright版本: {playwright.__version__}')"
echo.
echo 检查浏览器文件:
if exist "%PLAYWRIGHT_BROWSERS_PATH%\chromium-*" (
    echo ✓ Chromium 浏览器已安装到本地目录
) else (
    echo ! 警告: 未在本地目录找到 Chromium 浏览器
    echo   可能安装在系统默认位置
)
popd
echo.

echo ==========================================
echo   设置完成！
echo ==========================================
echo.
echo 浏览器路径: %PLAYWRIGHT_BROWSERS_PATH%
echo.
echo 下一步:
echo 1. 启动后端服务: .\scripts\launchers\start_backend.bat
echo 2. 启动Worker服务: .\scripts\launchers\start_worker.bat
echo.
pause
