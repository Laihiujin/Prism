@echo off
chcp 65001 >nul 2>&1
echo.
echo ============================================
echo   Supervisor 编译诊断工具
echo ============================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo [1/5] 检查 Python 版本...
python --version
echo.

echo [2/5] 检查 PyInstaller...
pyinstaller --version
if errorlevel 1 (
    echo ❌ PyInstaller 未安装
    echo 请运行: pip install pyinstaller
    pause
    exit /b 1
)
echo.

echo [3/5] 检查必需文件...
echo.

set "MISSING_FILES=0"

if not exist "desktop-electron\resources\supervisor\supervisor.py" (
    echo ❌ 缺失: desktop-electron\resources\supervisor\supervisor.py
    set "MISSING_FILES=1"
) else (
    echo ✅ 找到: desktop-electron\resources\supervisor\supervisor.py
)

if not exist "desktop-electron\resources\supervisor\api_server.py" (
    echo ❌ 缺失: desktop-electron\resources\supervisor\api_server.py
    set "MISSING_FILES=1"
) else (
    echo ✅ 找到: desktop-electron\resources\supervisor\api_server.py
)

if not exist "build\supervisor.spec" (
    echo ❌ 缺失: build\supervisor.spec
    set "MISSING_FILES=1"
) else (
    echo ✅ 找到: build\supervisor.spec
)

echo.
if "%MISSING_FILES%"=="1" (
    echo ❌ 发现缺失文件，请先确保所有文件存在
    pause
    exit /b 1
)

echo [4/5] 检查 Python 依赖...
echo.

echo 检查 psutil (可选，但推荐安装)...
python -c "import psutil; print('✅ psutil 已安装:', psutil.__version__)" 2>nul
if errorlevel 1 (
    echo ⚠️  psutil 未安装 (可选依赖)
    echo    建议安装: pip install psutil
    echo.
)

echo [5/5] 测试导入 supervisor 模块...
pushd desktop-electron\resources\supervisor
python -c "import supervisor; print('✅ supervisor.py 可以被正常导入')" 2>nul
if errorlevel 1 (
    echo ❌ supervisor.py 导入失败
    echo 请检查代码语法或依赖
    popd
    pause
    exit /b 1
)

python -c "import api_server; print('✅ api_server.py 可以被正常导入')" 2>nul
if errorlevel 1 (
    echo ❌ api_server.py 导入失败
    echo 请检查代码语法或依赖
    popd
    pause
    exit /b 1
)
popd

echo.
echo ============================================
echo ✅ 诊断完成
echo ============================================
echo.
echo 所有检查通过，可以尝试编译。
echo.
echo 建议操作:
echo   1. 确保安装 psutil: pip install psutil
echo   2. 运行编译脚本: build-supervisor.bat
echo.

pause
