@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   强制关闭所有 SynapseAutomation 进程
echo ============================================
echo.

echo [1/6] 关闭 SynapseAutomation.exe...
taskkill /F /IM SynapseAutomation.exe >nul 2>&1
if %errorlevel%==0 (
    echo ✓ SynapseAutomation.exe 已关闭
) else (
    echo - SynapseAutomation.exe 未运行
)

echo [2/6] 关闭 supervisor.exe...
taskkill /F /IM supervisor.exe >nul 2>&1
if %errorlevel%==0 (
    echo ✓ supervisor.exe 已关闭
) else (
    echo - supervisor.exe 未运行
)

echo [3/6] 关闭 python.exe...
taskkill /F /IM python.exe >nul 2>&1
if %errorlevel%==0 (
    echo ✓ python.exe 已关闭
) else (
    echo - python.exe 未运行
)

echo [4/6] 关闭 node.exe...
taskkill /F /IM node.exe >nul 2>&1
if %errorlevel%==0 (
    echo ✓ node.exe 已关闭
) else (
    echo - node.exe 未运行
)

echo [5/6] 关闭 redis-server.exe...
taskkill /F /IM redis-server.exe >nul 2>&1
if %errorlevel%==0 (
    echo ✓ redis-server.exe 已关闭
) else (
    echo - redis-server.exe 未运行
)

echo [6/6] 关闭 chrome.exe / chromium.exe...
taskkill /F /IM chrome.exe >nul 2>&1
taskkill /F /IM chromium.exe >nul 2>&1
echo ✓ 浏览器进程已关闭

echo.
echo ============================================
echo   所有进程已关闭
echo ============================================
echo.
pause
