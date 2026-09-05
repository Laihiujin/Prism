@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%~dp0"
set "PY=%ROOT%prismenv\Scripts\python.exe"
rem 默认后端地址：优先取 runtime.json 的动态端口；无栈/未引导时回退 :7000。
rem 外部可通过 PRISM_BACKEND_URL / PRISM_BACKEND_PORT 显式指定，仍生效。
if not defined PRISM_BACKEND_URL (
  if exist "%PY%" (
    for /f "usebackq delims=" %%I in (`"%PY%" -c "import json,pathlib;print(json.loads(pathlib.Path(r'%ROOT%runtime-data\runtime.json').read_text()).get('backend_url','http://127.0.0.1:7000'))"`) do set "PRISM_BACKEND_URL=%%I"
  )
)
if not defined PRISM_BACKEND_URL set "PRISM_BACKEND_URL=http://127.0.0.1:7000"
set "BACKEND_URL=%PRISM_BACKEND_URL%"
set "PRISM_USE_EXTERNAL_STACK=1"
set "PRISM_START_SERVICES=0"
set "PRISM_START_FRONTEND=0"
set "PRISM_BACKEND_URL=%BACKEND_URL%"
set "NEXT_PUBLIC_PRISM_BACKEND_URL=%BACKEND_URL%"
set "NEXT_PUBLIC_BACKEND_URL=%BACKEND_URL%"

set "PACKAGED_EXE="
if exist "%~dp0desktop-electron\dist-build\win-unpacked\Prism.exe" (
    set "PACKAGED_EXE=%~dp0desktop-electron\dist-build\win-unpacked\Prism.exe"
)
if not defined PACKAGED_EXE (
    for /d %%D in ("%~dp0desktop-electron\dist-out\*") do (
        if exist "%%~fD\win-unpacked\Prism.exe" (
            set "PACKAGED_EXE=%%~fD\win-unpacked\Prism.exe"
        )
    )
)
if defined PACKAGED_EXE (
    echo [INFO] Launching packaged Electron desktop...
    start "Prism Desktop" "%PACKAGED_EXE%"
    exit /b 0
)

if not exist "%~dp0desktop-electron\node_modules\electron" (
    echo [INFO] Installing desktop-electron dependencies...
    pushd "%~dp0desktop-electron"
    call npm install
    set "RC=%ERRORLEVEL%"
    popd
    if not "%RC%"=="0" exit /b %RC%
)

echo [INFO] Launching development Electron desktop...
pushd "%~dp0desktop-electron"
call npm run start
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%
