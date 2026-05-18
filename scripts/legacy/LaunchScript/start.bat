@echo off
setlocal

set "ROOT=%~dp0..\..\..\"
call "%ROOT%start.bat" %*
exit /b %ERRORLEVEL%
