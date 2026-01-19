@echo off
chcp 65001 >nul
echo ================================
echo 清理 dist-new 和 dist-test 目录
echo ================================
echo.

echo 正在关闭可能占用文件的进程...
taskkill /F /IM electron.exe 2>nul
taskkill /F /IM python.exe 2>nul
taskkill /F /IM celery.exe 2>nul
taskkill /F /IM node.exe 2>nul
timeout /t 2 /nobreak >nul

echo.
echo 正在删除 dist-new 目录...
if exist "desktop-electron\dist-new" (
    rmdir /S /Q "desktop-electron\dist-new"
    if exist "desktop-electron\dist-new" (
        echo [警告] dist-new 部分文件仍被占用，跳过...
    ) else (
        echo [成功] dist-new 已删除
    )
) else (
    echo [信息] dist-new 目录不存在
)

echo.
echo 正在删除 dist-test 目录...
if exist "desktop-electron\dist-test" (
    rmdir /S /Q "desktop-electron\dist-test"
    if exist "desktop-electron\dist-test" (
        echo [警告] dist-test 部分文件仍被占用，跳过...
    ) else (
        echo [成功] dist-test 已删除
    )
) else (
    echo [信息] dist-test 目录不存在
)

echo.
echo 清理完成！
pause
