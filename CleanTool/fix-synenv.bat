@echo off
chcp 65001 >nul 2>&1
echo.
echo ============================================
echo   修复 synenv 虚拟环境路径
echo ============================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: 检查 synenv 是否存在
if not exist "synenv" (
    echo ❌ synenv 虚拟环境不存在
    echo.
    choice /C YN /M "是否创建新的虚拟环境"
    if errorlevel 2 (
        echo 用户取消
        pause
        exit /b 1
    )

    echo.
    echo 正在创建虚拟环境...
    python -m venv synenv

    if errorlevel 1 (
        echo ❌ 创建失败
        pause
        exit /b 1
    )

    echo ✅ 虚拟环境创建完成
    echo.
    echo 正在安装依赖...
    call synenv\Scripts\activate.bat
    pip install -r syn_backend\requirements.txt
    pip install pyinstaller

    echo.
    echo ✅ 环境已就绪
    pause
    exit /b 0
)

:: 检查路径是否正确
echo [1/3] 检查虚拟环境路径...
findstr /C:"D:\Siuyechu" synenv\pyvenv.cfg >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    echo ⚠️  检测到路径错误（D:\ -> E:\）
    echo.
    echo 解决方案:
    echo   [1] 重新创建虚拟环境（推荐）
    echo   [2] 手动修复路径
    echo   [3] 取消
    echo.
    set /p FIX_CHOICE="请选择 (1/2/3): "

    if "!FIX_CHOICE!"=="1" (
        echo.
        echo [2/3] 删除旧的虚拟环境...
        rd /s /q synenv 2>nul
        timeout /t 2 >nul

        echo [3/3] 创建新的虚拟环境...
        python -m venv synenv

        if errorlevel 1 (
            echo ❌ 创建失败
            pause
            exit /b 1
        )

        echo ✅ 虚拟环境已重建
        echo.
        echo 正在安装依赖...
        call synenv\Scripts\activate.bat
        python -m pip install --upgrade pip
        pip install -r syn_backend\requirements.txt
        pip install pyinstaller

        echo.
        echo ============================================
        echo ✅ 环境修复完成！
        echo ============================================
        echo.
        echo 下一步:
        echo   1. 编译 supervisor: scripts\packaging\build-supervisor.bat
        echo   2. 运行打包: scripts\packaging\build-package.bat
        echo.
        pause
        exit /b 0

    ) else if "!FIX_CHOICE!"=="2" (
        echo.
        echo ⚠️  手动修复步骤:
        echo   1. 打开 synenv\pyvenv.cfg
        echo   2. 将 D:\Siuyechu 替换为 E:\Siuyechu
        echo   3. 保存文件
        echo.
        pause
        exit /b 0

    ) else (
        echo 用户取消
        pause
        exit /b 0
    )
) else (
    echo ✅ 虚拟环境路径正确
)

echo.
echo ============================================
echo ✅ 检查完成！
echo ============================================
pause
