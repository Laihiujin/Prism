@echo off
echo ========================================
echo 重启后端服务
echo ========================================
echo.

REM 查找并终止后端进程
echo [1/3] 正在停止后端进程...
taskkill /F /IM uvicorn.exe 2>nul
taskkill /F /FI "WINDOWTITLE eq fastapi*" 2>nul
timeout /t 2 /nobreak >nul

echo [2/3] 等待进程完全停止...
timeout /t 3 /nobreak >nul

echo [3/3] 启动后端服务...
cd /d "%~dp0..\..\syn_backend"
start "FastAPI Backend" cmd /k "python -m uvicorn fastapi_app.run:app --host 0.0.0.0 --port 7000 --reload"

echo.
echo ========================================
echo 后端重启完成！
echo 请等待 5-10 秒后访问 http://localhost:3000/settings
echo ========================================
pause
