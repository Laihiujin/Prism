@echo off
chcp 65001 >nul
echo =========================================
echo  重启 Celery Worker（应用新配置）
echo =========================================
echo.

echo [1/3] 停止现有 Celery 进程...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq Celery*" 2>nul
timeout /t 2 /nobreak >nul

echo [2/3] 清理任务队列...
echo 提示：如果需要保留任务队列，请跳过此步骤
echo.

echo [3/3] 启动新的 Celery Worker...
echo 请手动运行以下命令启动 Celery：
echo.
echo   cd syn_backend
echo   celery -A fastapi_app.celery_app worker --loglevel=info --pool=solo
echo.
echo =========================================
echo  配置已更新，请重启 Celery Worker
echo =========================================
pause
