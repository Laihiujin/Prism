@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0..\.."
set "STOPPER=%ROOT%\scripts\launchers\stop_celery.bat"
set "STARTER=%ROOT%\scripts\launchers\start_celery_synenv.bat"

if exist "%STOPPER%" (
    call "%STOPPER%"
)

if not exist "%STARTER%" (
    echo [ERROR] Launcher not found: %STARTER%
    exit /b 1
)

call "%STARTER%"
exit /b %ERRORLEVEL%
