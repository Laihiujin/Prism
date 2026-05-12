@echo off
setlocal

set "ROOT=%~dp0"
set "TARGET=%ROOT%scripts\launchers\stop_stack.bat"

if not exist "%TARGET%" (
    echo [ERROR] Launcher not found: %TARGET%
    exit /b 1
)

call "%TARGET%"
exit /b %ERRORLEVEL%
