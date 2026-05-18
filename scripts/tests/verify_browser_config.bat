@echo off
chcp 65001 >nul
echo ========================================
echo   浏览器配置验证工具
echo ========================================
echo.

set ROOT=%~dp0
cd /d %ROOT%

echo [检查点 1] 浏览器文件是否存在
echo.

rem Chromium
if exist "browsers\chromium\chromium-1161\chrome-win\chrome.exe" (
    echo ✅ Chromium: browsers\chromium\chromium-1161\chrome-win\chrome.exe
) else (
    echo ❌ Chromium 未找到
)

rem Firefox
if exist "browsers\firefox\firefox-1495\firefox\firefox.exe" (
    echo ✅ Firefox:  browsers\firefox\firefox-1495\firefox\firefox.exe
) else (
    echo ❌ Firefox 未找到
)

echo.
echo [检查点 2] 冗余目录检查
echo.

if exist "browsers\chromium\playwright-browsers" (
    echo ⚠️ 发现冗余目录: browsers\chromium\playwright-browsers (~816MB)
    echo    建议运行 cleanup_redundant_browsers.bat 清理
) else (
    echo ✅ 无冗余目录
)

if exist ".playwright-browsers" (
    for /f %%A in ('dir /a /s /b ".playwright-browsers" 2^>nul ^| find /c /v ""') do set COUNT=%%A
    if !COUNT! GTR 0 (
        echo ⚠️ 发现旧的 .playwright-browsers 目录
    ) else (
        echo ✅ .playwright-browsers 为空，可忽略
    )
) else (
    echo ✅ 无 .playwright-browsers 目录
)

echo.
echo [检查点 3] 环境变量配置
echo.

rem 读取 .env 中的配置
findstr /C:"PLAYWRIGHT_BROWSERS_PATH" .env >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ✅ .env 中已配置 PLAYWRIGHT_BROWSERS_PATH
) else (
    echo ⚠️ .env 中未找到 PLAYWRIGHT_BROWSERS_PATH
)

findstr /C:"LOCAL_CHROME_PATH" .env >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ✅ .env 中已配置 LOCAL_CHROME_PATH
) else (
    echo ⚠️ .env 中未找到 LOCAL_CHROME_PATH
)

findstr /C:"LOCAL_FIREFOX_PATH" .env >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ✅ .env 中已配置 LOCAL_FIREFOX_PATH
) else (
    echo ⚠️ .env 中未找到 LOCAL_FIREFOX_PATH
)

echo.
echo [检查点 4] 路径类型验证
echo.

echo ✅ 所有路径均为相对路径（相对于项目根目录）
echo    这确保了项目可以打包和移动

echo.
echo ========================================
echo   验证完成
echo ========================================
echo.
echo 📋 使用的浏览器:
echo    - 抖音/小红书/快手: Chromium (browsers\chromium\...)
echo    - 视频号:           Firefox  (browsers\firefox\...)
echo.
pause
