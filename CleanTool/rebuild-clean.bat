@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ============================================
::   清理并重新构建（Inno Setup）
:: ============================================
echo.
echo ============================================
echo   清理并重新构建（Inno Setup）
echo ============================================
echo.

set "ROOT_DIR=%~dp0"
set "FRONTEND_DIR=%ROOT_DIR%syn_frontend_react"

echo WARNING: 此脚本将：
echo   1. 停止所有 Node.js 进程
echo   2. 删除前端构建缓存
echo   3. 重新构建安装程序
echo.

choice /C YN /M "是否继续"
if errorlevel 2 (
    echo 已取消
    pause
    exit /b 0
)

:: ============================================
:: 1. 停止进程
:: ============================================
echo.
echo [1/4] 停止相关进程...
echo.

taskkill /F /IM node.exe >nul 2>&1
taskkill /F /IM next.exe >nul 2>&1
taskkill /F /IM SynapseAutomation.exe >nul 2>&1

echo OK: 进程已停止
timeout /t 2 >nul

:: ============================================
:: 2. 清理前端缓存
:: ============================================
echo.
echo [2/4] 清理前端缓存...
echo.

cd /d "%FRONTEND_DIR%"

if exist ".next" (
    echo 删除 .next...
    rd /s /q .next 2>nul
    timeout /t 2 >nul

    if exist ".next" (
        echo WARNING: .next 仍然存在，尝试强制删除...

        :: 使用 PowerShell 强制删除
        powershell -Command "Remove-Item -Path '.next' -Recurse -Force -ErrorAction SilentlyContinue"
        timeout /t 2 >nul

        if exist ".next" (
            echo ERROR: 无法删除 .next
            echo 请确保：
            echo   1. 已关闭 VSCode
            echo   2. 没有文件管理器打开此目录
            echo   3. 杀毒软件未锁定文件
            pause
            exit /b 1
        )
    )

    echo OK: .next 已删除
) else (
    echo OK: .next 不存在
)

if exist "node_modules\.cache" (
    rd /s /q node_modules\.cache 2>nul
    echo OK: node_modules\.cache 已清理
)

:: ============================================
:: 3. 清理旧的构建输出
:: ============================================
echo.
echo [3/4] 清理旧的构建输出...
echo.

cd /d "%ROOT_DIR%desktop-electron"

if exist "dist-build\win-unpacked" (
    rd /s /q dist-build\win-unpacked 2>nul
    echo OK: dist-build\win-unpacked 已清理
)

:: ============================================
:: 4. 重新构建
:: ============================================
echo.
echo [4/4] 开始构建（使用 Inno Setup）...
echo.

timeout /t 3 >nul

cd /d "%ROOT_DIR%"

set SYNAPSE_AUTO_YES=1
set SYNAPSE_PACKAGE_TYPE=2

call build-package.bat

exit /b %ERRORLEVEL%
