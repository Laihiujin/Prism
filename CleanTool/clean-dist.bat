@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM =====================================================
REM SynapseAutomation Clean Distribution v5 Builder
REM Clean and prepare dist-v5 package
REM =====================================================

echo.
echo ========================================
echo  SynapseAutomation dist Clean Build
echo ========================================
echo.

REM 定义清理的目录和文件
set "BACKEND_DIR=syn_backend"
set "LOG_DIR=%BACKEND_DIR%\logs"
set "DB_DIR=%BACKEND_DIR%\db"
set "STORAGE_DIR=%BACKEND_DIR%\storage"
set "CACHE_DIR=%BACKEND_DIR%\.cache"
set "TEMP_DIR=%BACKEND_DIR%\temp"
set "FINGERPRINTS_DIR=%BACKEND_DIR%\fingerprints"

echo.
echo ========================================
echo  第1步: 清理后端日志和数据
echo ========================================
echo.

if exist "%LOG_DIR%" (
    echo [清理] 删除日志目录: %LOG_DIR%
    rmdir /s /q "%LOG_DIR%" 2>nul
    mkdir "%LOG_DIR%" 2>nul
    echo [创建] 空日志目录
)

if exist "%STORAGE_DIR%" (
    echo [清理] 删除存储目录: %STORAGE_DIR%
    rmdir /s /q "%STORAGE_DIR%" 2>nul
    mkdir "%STORAGE_DIR%" 2>nul
    echo [创建] 空存储目录
)

if exist "%CACHE_DIR%" (
    echo [清理] 删除缓存目录: %CACHE_DIR%
    rmdir /s /q "%CACHE_DIR%" 2>nul
    mkdir "%CACHE_DIR%" 2>nul
    echo [创建] 空缓存目录
)

if exist "%TEMP_DIR%" (
    echo [清理] 删除临时目录: %TEMP_DIR%
    rmdir /s /q "%TEMP_DIR%" 2>nul
    mkdir "%TEMP_DIR%" 2>nul
    echo [创建] 空临时目录
)

if exist "%FINGERPRINTS_DIR%" (
    echo [清理] 删除指纹目录: %FINGERPRINTS_DIR%
    rmdir /s /q "%FINGERPRINTS_DIR%" 2>nul
    echo [清理完成]
)

echo.
echo ========================================
echo  第2步: 清理账号 Cookie
echo ========================================
echo.

REM 清理 cookie 文件但保留结构
set "COOKIE_DIR=%BACKEND_DIR%\data\cookies"
if exist "%COOKIE_DIR%" (
    echo [清理] 删除 Cookie 目录: %COOKIE_DIR%
    rmdir /s /q "%COOKIE_DIR%" 2>nul
    mkdir "%COOKIE_DIR%" 2>nul
    echo [创建] 空 Cookie 目录
) else (
    echo [创建] Cookie 目录: %COOKIE_DIR%
    mkdir "%COOKIE_DIR%" 2>nul
)

echo.
echo ========================================
echo  第3步: 清理数据库
echo ========================================
echo.

REM 清理特定的数据库文件但保留结构
if exist "%DB_DIR%" (
    echo [清理] 清空数据库文件...

    if exist "%DB_DIR%\database.db" (
        del /f /q "%DB_DIR%\database.db" 2>nul
        echo [删除] database.db
    )

    if exist "%DB_DIR%\frontend_accounts_snapshot.json" (
        del /f /q "%DB_DIR%\frontend_accounts_snapshot.json" 2>nul
        echo [删除] frontend_accounts_snapshot.json
    )

    if exist "%DB_DIR%\*.db" (
        del /f /q "%DB_DIR%\*.db" 2>nul
        echo [删除] *.db 文件
    )
) else (
    echo [创建] DB 目录: %DB_DIR%
    mkdir "%DB_DIR%" 2>nul
)

echo.
echo ========================================
echo  第4步: 清理临时构建文件
echo ========================================
echo.

REM 清理 Python 缓存
echo [清理] Python 缓存文件...
for /r "%BACKEND_DIR%" %%d in (__pycache__) do (
    if exist "%%d" (
        rmdir /s /q "%%d" 2>nul
    )
)

for /r "%BACKEND_DIR%" %%f in (*.pyc) do (
    if exist "%%f" del /f /q "%%f" 2>nul
)

REM 清理 .pytest_cache
if exist "%BACKEND_DIR%\.pytest_cache" (
    rmdir /s /q "%BACKEND_DIR%\.pytest_cache" 2>nul
    echo [删除] .pytest_cache
)

echo.
echo ========================================
echo  第5步: 清理视频数据
echo ========================================
echo.

set "VIDEO_DIR=%BACKEND_DIR%\storage\videos"
if exist "%VIDEO_DIR%" (
    echo [清理] 删除视频文件: %VIDEO_DIR%
    rmdir /s /q "%VIDEO_DIR%" 2>nul
    mkdir "%VIDEO_DIR%" 2>nul
    echo [创建] 空视频目录
)

echo.
echo ========================================
echo  第6步: 保留默认配置
echo ========================================
echo.

echo [保留] 默认配置文件:
echo [保留] - config/ai_prompts_unified.yaml
echo [保留] - syn_backend/config/ 目录
echo [保留] - .env 环境变量文件
echo [保留] - API 密钥配置

if exist "%BACKEND_DIR%\config" (
    echo [状态] 配置目录存在 ✓
)

echo.
echo ========================================
echo  第7步: 验证清理结果
echo ========================================
echo.

echo [验证] 关键目录结构:
if exist "%LOG_DIR%" echo  ✓ %LOG_DIR%
if exist "%CACHE_DIR%" echo  ✓ %CACHE_DIR%
if exist "%TEMP_DIR%" echo  ✓ %TEMP_DIR%
if exist "%COOKIE_DIR%" echo  ✓ %COOKIE_DIR%
if exist "%DB_DIR%" echo  ✓ %DB_DIR%

echo.
echo ========================================
echo  清理完成！
echo ========================================
echo.
echo [状态] 已清理:
echo  - 日志文件
echo  - 视频数据
echo  - 账号 Cookie
echo  - 缓存数据
echo  - 临时文件
echo  - Python 缓存
echo.
echo [保留]:
echo  - 默认配置文件
echo  - 系统配置
echo  - API 密钥配置
echo.

pause
