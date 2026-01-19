@echo off
chcp 65001 >nul
echo ============================================
echo   测试打包后的 SynapseAutomation
echo ============================================
echo.

set "APP_DIR=%~dp0..\dist-build\win-unpacked"

if not exist "%APP_DIR%\SynapseAutomation.exe" (
    echo ❌ 打包程序未找到: %APP_DIR%\SynapseAutomation.exe
    echo.
    echo 请先运行打包:
    echo   npm run build:dir
    pause
    exit /b 1
)

echo ✅ 找到打包程序
echo.
echo 📦 程序位置: %APP_DIR%
echo 📊 程序大小:
dir "%APP_DIR%\SynapseAutomation.exe" | findstr "SynapseAutomation.exe"
echo.
echo 📁 资源清单:
dir /B "%APP_DIR%\resources"
echo.
echo 🚀 启动程序...
echo.
echo 注意:
echo   - 首次启动可能需要几分钟
echo   - 查看日志: %%APPDATA%%\SynapseAutomation\logs\main.log
echo   - 按 Ctrl+C 停止
echo.
pause

cd /d "%APP_DIR%"
start "" "SynapseAutomation.exe"

echo.
echo ✅ 程序已启动
echo.
echo 下一步:
echo   1. 等待主窗口出现
echo   2. 检查前端是否加载 (localhost:3000)
echo   3. 查看日志确认后端服务启动
echo.
pause
