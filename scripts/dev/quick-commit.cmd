@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0quick-commit.ps1" %*
endlocal
