@echo off
chcp 65001 >nul 2>&1
echo.
echo ============================================
echo   编译 Supervisor
echo ============================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: 检查是否有 supervisor.py
if not exist "desktop-electron\resources\supervisor\supervisor.py" (
    echo ❌ 错误: 找不到 supervisor.py
    echo 路径: desktop-electron\resources\supervisor\supervisor.py
    pause
    exit /b 1
)

echo ✅ 找到 supervisor.py
echo.

:: 检查 PyInstaller
echo [1/3] 检查 PyInstaller...
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo ⚠️  PyInstaller 未安装
    echo.
    choice /C YN /M "是否现在安装 PyInstaller"
    if errorlevel 2 (
        echo ❌ 用户取消
        pause
        exit /b 1
    )
    echo.
    echo 正在安装 PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo ❌ 安装失败
        pause
        exit /b 1
    )
    echo ✅ PyInstaller 安装完成
) else (
    echo ✅ PyInstaller 已安装
    pyinstaller --version
)
echo.

:: 检查并停止运行中的 supervisor
echo [2/3] 检查运行中的 supervisor...
tasklist /FI "IMAGENAME eq supervisor.exe" 2>NUL | find /I /N "supervisor.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo ⚠️  检测到 supervisor.exe 正在运行
    echo 正在停止进程...
    taskkill /F /IM supervisor.exe >nul 2>&1
    timeout /t 2 >nul
    echo ✅ 进程已停止
) else (
    echo ✅ 没有运行中的 supervisor
)
echo.

:: 清理旧的编译文件
if exist "build\supervisor" (
    echo 清理旧的编译文件...
    rd /s /q "build\supervisor" 2>nul
    echo ✅ 清理完成
    echo.
)

:: 开始编译
echo [3/3] 开始编译 supervisor...
echo ⏱️  这可能需要 1-3 分钟...
echo.

pyinstaller build\supervisor.spec --clean

echo.
echo ============================================


set "SUPERVISOR_EXE="

if exist "build\supervisor\supervisor.exe" (
    set "SUPERVISOR_EXE=build\supervisor\supervisor.exe"
)

if not defined SUPERVISOR_EXE (
    if exist "dist\supervisor.exe" (
        echo INFO: supervisor.exe found in dist
        if not exist "build\supervisor" mkdir "build\supervisor"
        copy /Y "dist\supervisor.exe" "build\supervisor\supervisor.exe" >nul
        set "SUPERVISOR_EXE=build\supervisor\supervisor.exe"
    )
)

if defined SUPERVISOR_EXE (
    echo Build OK.
    echo ============================================
    echo.
    echo supervisor.exe generated
    echo Location: %SUPERVISOR_EXE%

    :: File info
    for %%F in ("%SUPERVISOR_EXE%") do (
        set /a FILE_SIZE_MB=%%~zF/1024/1024
        call echo Size: %%~zF bytes (~%%FILE_SIZE_MB%% MB)
    )

    :: Copy to Electron resources
    if not exist "desktop-electron\resources\supervisor" mkdir "desktop-electron\resources\supervisor"
    copy /Y "%SUPERVISOR_EXE%" "desktop-electron\resources\supervisor\supervisor.exe" >nul
    echo Copied to: desktop-electron\resources\supervisor\supervisor.exe

    echo.
    echo Next:
    echo   1. Test: build\supervisor\supervisor.exe
    echo   2. Package: build-package.bat
    echo.

) else (
    echo ❌ 编译失败
    echo ============================================
    echo.
    echo ❌ 错误: supervisor.exe 未生成
    echo.
    echo 请检查上面的错误信息
    echo.
    echo 常见问题:
    echo   1. supervisor.py 不存在或路径错误
    echo   2. 缺少依赖模块
    echo   3. PyInstaller 配置错误
    echo.
    echo 解决方案:
    echo   - 检查文件: desktop-electron\resources\supervisor\supervisor.py
    echo   - 安装依赖: pip install -r syn_backend\requirements.txt
    echo.
    pause
    exit /b 1
)

pause
