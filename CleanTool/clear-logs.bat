@echo off
chcp 65001 >nul
REM Set UTF-8 encoding environment
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
REM 清理 Supervisor 日志文件脚本
echo ========================================
echo   SynapseAutomation 日志清理工具
echo ========================================
echo.

set LOG_DIR=dist\win-unpacked\resources\supervisor

if not exist "%LOG_DIR%" (
    echo [ERROR] 找不到日志目录: %LOG_DIR%
    pause
    exit /b 1
)

echo [INFO] 日志目录: %LOG_DIR%
echo.

REM 显示当前日志文件大小
echo [INFO] 当前日志文件大小:
powershell -Command "Get-ChildItem '%LOG_DIR%\*.log' | Select-Object Name, @{Name='Size(MB)';Expression={[math]::Round($_.Length/1MB,2)}} | Format-Table -AutoSize"
echo.

REM 询问用户确认
set /p CONFIRM="确定要清空所有日志文件吗？(y/n): "
if /i not "%CONFIRM%"=="y" (
    echo [INFO] 取消清理
    pause
    exit /b 0
)

echo.
echo [INFO] 正在清空日志文件...

REM 清空所有日志文件
powershell -Command "Get-ChildItem '%LOG_DIR%\*.log' | ForEach-Object { Clear-Content $_.FullName -Force; Write-Host '[CLEARED]' $_.Name }"

echo.
echo [SUCCESS] 所有日志文件已清空
echo.

REM 显示清理后的大小
echo [INFO] 清理后的日志文件大小:
powershell -Command "Get-ChildItem '%LOG_DIR%\*.log' | Select-Object Name, @{Name='Size(MB)';Expression={[math]::Round($_.Length/1MB,2)}} | Format-Table -AutoSize"

echo.
echo [DONE] 日志清理完成！
pause
