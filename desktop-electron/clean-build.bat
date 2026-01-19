@echo off
chcp 65001 >nul 2>&1
echo.
echo ============================================
echo   清理打包目录
echo ============================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%desktop-electron"
set "ELECTRON_DIST=dist-build"

echo 正在清理打包临时文件...
echo.

:: 停止可能运行的进程
tasklist /FI "IMAGENAME eq SynapseAutomation.exe" 2>NUL | find /I /N "SynapseAutomation.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo 停止 SynapseAutomation.exe...
    taskkill /F /IM SynapseAutomation.exe >nul 2>&1
    timeout /t 2 >nul
)

:: Stop packaged services that may lock dist-build/dist-out files
powershell -Command "Get-Process | Where-Object { $_.Path -and ( $_.Path -like '*\dist-build\win-unpacked\resources\synenv\*' -or $_.Path -like '*\dist\win-unpacked\resources\synenv\*' -or $_.Path -like '*\dist-out\*\win-unpacked\resources\synenv\*' -or $_.Path -like '*\dist-build\win-unpacked\resources\syn_backend\*' -or $_.Path -like '*\dist\win-unpacked\resources\syn_backend\*' -or $_.Path -like '*\dist-out\*\win-unpacked\resources\syn_backend\*' ) } | Stop-Process -Force" >nul 2>&1

:: 清理 %ELECTRON_DIST% 目录
if exist "%ELECTRON_DIST%" (
    echo [清理] %ELECTRON_DIST% 目录...
    rd /s /q "%ELECTRON_DIST%" 2>nul
    if exist "%ELECTRON_DIST%" (
        echo ⚠️  部分文件无法删除，可能被占用
        timeout /t 2 >nul
        rd /s /q "%ELECTRON_DIST%" 2>nul
    )
    echo ✅ %ELECTRON_DIST% 目录已清理
)

:: 清理 node_modules/.cache
if exist "node_modules\.cache" (
    echo [清理] node_modules\.cache...
    rd /s /q "node_modules\.cache" 2>nul
    echo ✅ 缓存已清理
)

echo.
echo ============================================
echo ✅ 清理完成！
echo ============================================
echo.
echo 现在可以运行 build-package.bat 进行打包
echo.
pause
