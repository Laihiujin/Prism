@echo off
chcp 65001 >nul
setlocal EnableExtensions
set "ROOT=%~dp0"
cd /d "%ROOT%"

rem ============================================================
rem  Prism Windows 一键启动 (bootstrap + PM2)
rem  用法: start.bat
rem  先运行 bootstrap.py 做环境准备（幂等），再交给 start-pm2.bat 用 PM2 启动整套服务。
rem ============================================================

rem ---- resolve a system python to run bootstrap.py ----
set "PY=py"
py -3.11 -c "import sys" >nul 2>&1
if not errorlevel 1 goto have_py
set "PY=python"
python -c "import sys" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found. Install Python 3.11+ and ensure py/python is in PATH.
  exit /b 1
)
:have_py

echo [BOOTSTRAP] bootstrap.py (idempotent environment prepare)...
"%PY%" "%ROOT%bootstrap.py" --no-browsers
if errorlevel 1 (
  echo [ERROR] bootstrap failed. See output above.
  exit /b 1
)

rem ---- verify prismenv interpreter ----
if not exist "%ROOT%prismenv\Scripts\python.exe" (
  echo [ERROR] prismenv interpreter missing: "%ROOT%prismenv\Scripts\python.exe"
  echo         Run bootstrap first: python "%ROOT%bootstrap.py"
  exit /b 1
)

rem ---- hand off to PM2 ----
call "%ROOT%start-pm2.bat"
exit /b %ERRORLEVEL%
