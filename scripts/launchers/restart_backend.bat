@echo off
echo Stopping all processes on port 7000...

REM Kill all processes listening on port 7000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":7000" ^| findstr "LISTENING"') do (
    echo Killing PID %%a
    taskkill /F /PID %%a 2>nul
)

echo Waiting 3 seconds...
timeout /t 3 /nobreak >nul

echo Starting backend...
start_backend.bat
