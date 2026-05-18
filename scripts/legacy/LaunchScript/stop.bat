@echo off
setlocal

set "ROOT=%~dp0..\..\..\"
call "%ROOT%stop.bat" %*
exit /b %ERRORLEVEL%
