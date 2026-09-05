@echo off
chcp 65001 >nul
setlocal EnableExtensions
set "ROOT=%~dp0"
cd /d "%ROOT%"

set "PLAYWRIGHT_BROWSERS_PATH=%ROOT%browsers"
set "PLAYWRIGHT_AUTO_INSTALL=0"

rem ============================================================
rem  Prism Windows 一键启动（bootstrap + PM2）
rem  用法: start.bat
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

rem ============================================================
rem  PM2 托管所有进程
rem ============================================================
set "PM2_HOME=%ROOT%runtime-data\pm2"
if not exist "%PM2_HOME%" mkdir "%PM2_HOME%" 2>nul
if not exist "%ROOT%logs" mkdir "%ROOT%logs" 2>nul

rem ---- resolve pm2 (root node_modules first, then prism_frontend, then PATH) ----
set "PM2=%ROOT%node_modules\.bin\pm2.cmd"
if not exist "%PM2%" set "PM2=%ROOT%prism_frontend\node_modules\.bin\pm2.cmd"
if not exist "%PM2%" set "PM2=pm2"

rem ---- clear the previous managed stack before probing ports ----
"%PM2%" delete all >nul 2>&1

rem ---- resolve one backend endpoint (dynamic port) ----
"%ROOT%prismenv\Scripts\python.exe" "%ROOT%scripts\prism_runtime.py" prepare >nul
if errorlevel 1 (
  echo [ERROR] prismenv missing or prepare failed. Run bootstrap first.
  exit /b 1
)

echo ============================================
echo   Prism 启动 (PM2)
echo ============================================
"%PM2%" start ecosystem.config.js --only prism-redis,prism-backend --update-env
if errorlevel 1 goto fail

rem ---- health-check backend, on failure re-pick the port and retry once ----
"%ROOT%prismenv\Scripts\python.exe" "%ROOT%scripts\prism_runtime.py" health --timeout 60
if errorlevel 1 (
  echo [WARN] backend failed to bind the selected port; re-selecting and retrying...
  "%PM2%" delete prism-backend >nul 2>&1
  "%ROOT%prismenv\Scripts\python.exe" "%ROOT%scripts\prism_runtime.py" prepare >nul
  "%PM2%" start ecosystem.config.js --only prism-backend --update-env
  "%ROOT%prismenv\Scripts\python.exe" "%ROOT%scripts\prism_runtime.py" health --timeout 60
  if errorlevel 1 goto fail
)

"%PM2%" start ecosystem.config.js --only prism-worker,prism-celery,prism-frontend,persona-api,persona-proxy,persona-dashboard,hermes-dashboard,hermes-webui,deepseek-harness --update-env
if errorlevel 1 goto fail

echo.
"%PM2%" list
echo.
echo 访问:
echo   前端        http://localhost:3000
echo   Worker      http://127.0.0.1:7001/health
echo   Persona API http://127.0.0.1:8787
echo.
echo 常用: set PM2_HOME=%PM2_HOME% %PM2% logs / restart all / stop all
exit /b 0

:fail
echo [ERROR] Prism 启动失败，请检查上方 pm2 输出与 %PM2_HOME%\logs
exit /b 1
