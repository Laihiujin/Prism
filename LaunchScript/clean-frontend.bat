@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ============================================
::   清理前端构建缓存和进程
:: ============================================
echo.
echo ============================================
echo   清理前端构建缓存和进程
echo ============================================
echo.

set "FRONTEND_DIR=%~dp0syn_frontend_react"

echo [1/4] 停止可能占用文件的进程...
echo.

:: 停止 Node.js 进程
tasklist | find /I "node.exe" >nul
if %errorlevel% equ 0 (
    echo 发现 Node.js 进程，正在停止...
    taskkill /F /IM node.exe >nul 2>&1
    timeout /t 2 >nul
    echo OK: Node.js 进程已停止
) else (
    echo OK: 未发现 Node.js 进程
)

:: 停止 Next.js 相关进程
tasklist | find /I "next.exe" >nul
if %errorlevel% equ 0 (
    echo 发现 Next.js 进程，正在停止...
    taskkill /F /IM next.exe >nul 2>&1
    timeout /t 1 >nul
    echo OK: Next.js 进程已停止
) else (
    echo OK: 未发现 Next.js 进程
)

echo.
echo [2/4] 删除前端构建缓存...
echo.

cd /d "%FRONTEND_DIR%"

if exist ".next" (
    echo 正在删除 .next 目录...
    rd /s /q .next 2>nul
    if exist ".next" (
        echo WARNING: 无法完全删除 .next，可能有文件被占用
        timeout /t 2 >nul
        rd /s /q .next 2>nul
    )
    if not exist ".next" (
        echo OK: .next 已删除
    ) else (
        echo ERROR: .next 删除失败，请手动删除后重试
        pause
        exit /b 1
    )
) else (
    echo OK: .next 目录不存在
)

echo.
echo [3/4] 清理 Node.js 缓存...
echo.

if exist "node_modules\.cache" (
    echo 正在删除 node_modules\.cache...
    rd /s /q node_modules\.cache 2>nul
    echo OK: 缓存已清理
) else (
    echo OK: 无需清理
)

echo.
echo [4/4] 等待文件系统释放...
echo.
timeout /t 3 >nul
echo OK: 文件系统已准备就绪

echo.
echo ============================================
echo 清理完成！
echo ============================================
echo.
echo 现在可以重新运行构建脚本：
echo   .\build-inno.bat
echo.
pause
