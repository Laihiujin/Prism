@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

set "ROOT_DIR=%~dp0..\..\.."
cd /d "%ROOT_DIR%"

:: ============================================
::   SynapseAutomation 项目清理脚本
:: ============================================
echo.
echo ============================================
echo   SynapseAutomation 项目清理脚本
echo ============================================
echo.
echo 此脚本将清理以下内容：
echo   1. 日志文件 (*.log, dump.rdb)
echo   2. 临时文件 (temp/, nul, _nul)
echo   3. 归档修复文档到 docs/fixes/
echo   4. 归档旧脚本到 scripts/archived/
echo   5. 归档维护脚本到 scripts/maintenance/
echo.

choice /C YN /M "是否继续清理"
if errorlevel 2 (
    echo.
    echo 清理已取消
    pause
    exit /b 0
)

:: ============================================
:: 1. 删除日志文件
:: ============================================
echo.
echo [1/6] 清理日志文件...
set "CLEANED=0"

if exist "*.log" (
    del /q *.log 2>nul
    if !errorlevel! equ 0 (
        echo   - 已删除: *.log
        set /a CLEANED+=1
    )
)

if exist "dump.rdb" (
    del /q dump.rdb 2>nul
    if !errorlevel! equ 0 (
        echo   - 已删除: dump.rdb
        set /a CLEANED+=1
    )
)

if !CLEANED! equ 0 (
    echo   - 无需清理
)

:: ============================================
:: 2. 删除临时文件
:: ============================================
echo.
echo [2/6] 清理临时文件...
set "CLEANED=0"

if exist "temp" (
    rd /s /q temp 2>nul
    if !errorlevel! equ 0 (
        echo   - 已删除: temp/
        set /a CLEANED+=1
    )
)

if exist "nul" (
    del /q nul 2>nul
    if !errorlevel! equ 0 (
        echo   - 已删除: nul
        set /a CLEANED+=1
    )
)

if exist "_nul" (
    del /q _nul 2>nul
    if !errorlevel! equ 0 (
        echo   - 已删除: _nul
        set /a CLEANED+=1
    )
)

if exist "__init__.py" (
    del /q __init__.py 2>nul
    if !errorlevel! equ 0 (
        echo   - 已删除: __init__.py
        set /a CLEANED+=1
    )
)

if exist "python-3.11.9-embed-amd64.zip" (
    echo   - 发现: python-3.11.9-embed-amd64.zip (约 30MB)
    choice /C YN /M "是否删除"
    if !errorlevel! equ 1 (
        del /q python-3.11.9-embed-amd64.zip 2>nul
        echo   - 已删除: python-3.11.9-embed-amd64.zip
        set /a CLEANED+=1
    )
)

if !CLEANED! equ 0 (
    echo   - 无需清理
)

:: ============================================
:: 3. 归档修复文档
:: ============================================
echo.
echo [3/6] 归档修复文档...
set "ARCHIVED=0"

if not exist "docs\fixes" mkdir "docs\fixes" 2>nul

for %%F in (AGENT_API_DATA_FORMAT_FIX.md FIX_SUMMARY.md PATH_FIX_SUMMARY.md) do (
    if exist "%%F" (
        move /y "%%F" "docs\fixes\" >nul 2>&1
        if !errorlevel! equ 0 (
            echo   - 已归档: %%F
            set /a ARCHIVED+=1
        )
    )
)

if !ARCHIVED! equ 0 (
    echo   - 无需归档
)

:: ============================================
:: 4. 归档旧启动脚本
:: ============================================
echo.
echo [4/6] 归档旧启动脚本...
set "ARCHIVED=0"

if not exist "scripts\archived" mkdir "scripts\archived" 2>nul

for %%F in (
    start_all_services_synenv.bat
    start_all_services.bat
    start_celery_worker_synenv.bat
    start_celery_worker.bat
    start_supervisor_synenv.bat
) do (
    if exist "%%F" (
        move /y "%%F" "scripts\archived\" >nul 2>&1
        if !errorlevel! equ 0 (
            echo   - 已归档: %%F
            set /a ARCHIVED+=1
        )
    )
)

if !ARCHIVED! equ 0 (
    echo   - 无需归档
)

:: ============================================
:: 5. 归档维护和诊断脚本
:: ============================================
echo.
echo [5/6] 归档维护和诊断脚本...
set "ARCHIVED=0"

if not exist "scripts\maintenance" mkdir "scripts\maintenance" 2>nul

for %%F in (
    diagnose-supervisor.bat
    fix_agent_tools.py
    manual_fix_instructions.py
) do (
    if exist "%%F" (
        move /y "%%F" "scripts\maintenance\" >nul 2>&1
        if !errorlevel! equ 0 (
            echo   - 已归档: %%F
            set /a ARCHIVED+=1
        )
    )
)

if !ARCHIVED! equ 0 (
    echo   - 无需归档
)

:: ============================================
:: 6. 清理 syn_backend 日志
:: ============================================
echo.
echo [6/6] 清理后端日志 (可选)...

if exist "syn_backend\logs\*.log" (
    choice /C YN /M "是否清理 syn_backend/logs/*.log"
    if !errorlevel! equ 1 (
        del /q syn_backend\logs\*.log 2>nul
        if !errorlevel! equ 0 (
            echo   - 已清理: syn_backend/logs/*.log
        )
    )
) else (
    echo   - 无日志文件
)

:: ============================================
:: 完成
:: ============================================
echo.
echo ============================================
echo 清理完成！
echo ============================================
echo.
echo 已清理的目录结构：
echo.
echo 根目录 (E:\Siuyechu\SynapseAutomation\)
echo   ├── docs\fixes\                  归档的修复文档
echo   └── scripts\
echo       ├── archived\                归档的旧脚本
echo       └── maintenance\             归档的维护脚本
echo.
echo 建议查看 CLEANUP_GUIDE.md 了解详细信息
echo.
pause
