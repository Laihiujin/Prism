@echo off
chcp 65001 >nul
echo ============================================
echo   SynapseAutomation 打包准备脚本
echo ============================================
echo.

set "ROOT=%~dp0.."
cd /d "%ROOT%"

echo [步骤 1/3] 构建前端 (Next.js standalone)...
echo.
cd ..\syn_frontend_react

REM 检查 node_modules
if not exist "node_modules" (
    echo ❌ node_modules 未找到
    echo 请先运行: npm install
    pause
    exit /b 1
)

echo 🔨 构建 Next.js 应用为 standalone 模式...
call npm run build
if errorlevel 1 (
    echo ❌ 前端构建失败
    pause
    exit /b 1
)

echo.
echo ✅ 前端构建完成
echo.

echo [步骤 2/3] 验证前端输出...
if not exist ".next\standalone\server.js" (
    echo ❌ 前端 server.js 未生成
    echo 请检查 next.config.ts 中是否设置了 output: "standalone"
    pause
    exit /b 1
)
echo ✅ 前端 standalone 输出验证通过
echo.

echo [步骤 3/3] 构建 Supervisor...
cd ..\build
if exist "build-supervisor.bat" (
    echo 🔨 构建 Supervisor...
    call build-supervisor.bat
    if errorlevel 1 (
        echo ⚠️ Supervisor 构建失败，但继续打包流程
    )
) else (
    echo ⚠️ 未找到 Supervisor 构建脚本
)
echo.

cd ..\desktop-electron
echo ============================================
echo ✅ 所有准备工作完成!
echo ============================================
echo.
echo 现在可以开始打包:
echo   npm run build        (完整打包 + 安装程序)
echo   npm run build:dir    (仅打包，不生成安装程序)
echo.
pause
