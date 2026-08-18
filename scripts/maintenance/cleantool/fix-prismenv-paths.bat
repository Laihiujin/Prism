@echo off
chcp 65001 >nul
echo ============================================
echo   修复 synenv 虚拟环境路径问题
echo ============================================
echo.
echo 说明：当项目目录从一个盘符移动到另一个盘符时
echo       虚拟环境内的可执行文件路径会失效
echo       此脚本会重新安装 pip 和常用工具
echo.

set "PYTHON_EXE=%~dp0synenv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo ❌ 找不到 Python: %PYTHON_EXE%
    pause
    exit /b 1
)

echo [1] 测试 Python 环境...
"%PYTHON_EXE%" --version
if errorlevel 1 (
    echo ❌ Python 无法运行
    pause
    exit /b 1
)
echo ✅ Python 正常
echo.

echo [2] 重新安装 pip...
"%PYTHON_EXE%" -m pip install --upgrade --force-reinstall pip
if errorlevel 1 (
    echo ❌ pip 安装失败
    pause
    exit /b 1
)
echo ✅ pip 已修复
echo.

echo [3] 重新安装 pyinstaller...
"%PYTHON_EXE%" -m pip install --upgrade --force-reinstall pyinstaller
if errorlevel 1 (
    echo ⚠️ pyinstaller 安装失败，但可以继续
)
echo ✅ pyinstaller 已修复
echo.

echo [4] 验证工具...
echo    - pip 版本:
"%~dp0synenv\Scripts\pip.exe" --version
echo    - pyinstaller 版本:
"%~dp0synenv\Scripts\pyinstaller.exe" --version
echo.

echo ============================================
echo   ✅ 修复完成
echo ============================================
echo.
echo 提示：如果还有其他可执行文件无法运行
echo       可以使用：python -m 包名 的方式调用
echo       例如：python -m pip install xxx
echo.
pause
