@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"

rem ============================================================
rem  Prism 一键部署（Windows）—— 一步到位
rem  检测 Python，没有就用 winget 自动装（最多弹一次管理员授权），
rem  再调跨平台 bootstrap 子命令。
rem
rem  用法:
rem     start.bat            一键部署（装齐依赖 + PM2 启动）
rem     start.bat start      快速启动（环境已就绪）
rem     start.bat stop       停止（pm2 delete all，保留数据）
rem     start.bat status     查看进程状态
rem ============================================================

rem ---- 1) 确保 Python 3.11+ 可用 ----------
set "PYEXE="
python -c "import sys" >nul 2>&1 && set "PYEXE=python"
if not defined PYEXE py -c "import sys" >nul 2>&1 && set "PYEXE=py"
if not defined PYEXE goto :ensure_python
goto :run

:ensure_python
echo [INFO] 未找到 Python。尝试 winget 自动安装（会弹一次管理员授权）...
winget install -e --id Python.Python.3.11 --scope machine --accept-source-agreements --accept-package-agreements >nul 2>&1
if errorlevel 1 (
  echo [WARN] winget 不可用/失败，尝试 choco ...
  choco install python --yes >nul 2>&1
)
if errorlevel 1 (
  echo [ERROR] Python 安装失败。请以管理员身份重新运行本脚本；或到 https://www.python.org/downloads/
  echo         安装 Python 3.11+ 后，再运行 start.bat。
  pause
  exit /b 1
)
rem winget 装的 Python 不刷新当前会话 PATH，这里手动定位
for %%P in ("C:\Program Files\Python311\python.exe" "%LOCALAPPDATA%\Programs\Python\Python311\python.exe") do (
  if exist "%%~P" set "PYEXE=%%~P"
)
if not defined PYEXE set "PYEXE=python"

:run
"%PYEXE%" "%ROOT%bootstrap.py" %*
exit /b %ERRORLEVEL%
