# Inno Setup 修复摘要

## 问题描述

在 [build-package.bat](build-package.bat) 中选择了 Inno Setup (选项 2)，但依然生成 NSIS 安装程序。

## 问题分析

通过诊断发现以下问题：

1. **环境变量冲突** - 在原始代码 line 427-429：
   ```batch
   set "SOURCE_DIR=%CD%\%OUTPUT_DIR%\win-unpacked"
   set "OUTPUT_DIR=%CD%\%OUTPUT_DIR%"
   set "OUTPUT_DIR_INNO=%OUTPUT_DIR%"
   ```
   `OUTPUT_DIR` 被重新赋值后，导致路径错误和混乱

2. **错误处理不足** - Inno Setup 编译失败时没有详细的错误信息

3. **日志输出不清晰** - 无法明确知道：
   - 是否真的运行了 Inno Setup
   - 生成的安装程序是什么类型
   - 预期的输出文件在哪里

4. **文件验证缺失** - 没有验证：
   - 源目录是否存在
   - 编译是否成功
   - 输出文件是否符合预期

## 修复内容

### 1. 修复环境变量处理 ([build-package.bat:447-472](build-package.bat:447-472))

```batch
:: Save OUTPUT_DIR before modifying it
set "INNO_OUTPUT_DIR=%OUTPUT_DIR%"
set "INNO_SOURCE_DIR=%CD%\%OUTPUT_DIR%\win-unpacked"

:: Verify source directory exists
if not exist "!INNO_SOURCE_DIR!" (
    echo ERROR: Source directory not found: !INNO_SOURCE_DIR!
    pause
    exit /b 1
)

:: Set environment variables for Inno Setup
set "APP_VERSION=%CURRENT_VERSION%"
set "APP_BUILD_NUM=%BUILD_NUM%"
set "SOURCE_DIR=!INNO_SOURCE_DIR!"
set "OUTPUT_DIR=%CD%\!INNO_OUTPUT_DIR!"
set "OUTPUT_DIR_INNO=%CD%\!INNO_OUTPUT_DIR!"
set "ICON_FILE=%CD%\icon.ico"
```

**改进**：
- 使用独立的变量 `INNO_OUTPUT_DIR` 和 `INNO_SOURCE_DIR` 避免冲突
- 在设置环境变量前验证源目录存在

### 2. 添加详细配置信息输出 ([build-package.bat:458-464](build-package.bat:458-464))

```batch
echo Inno Setup configuration:
echo   Version: %CURRENT_VERSION%
echo   Build: v%BUILD_NUM%
echo   Source: !INNO_SOURCE_DIR!
echo   Output: %CD%\!INNO_OUTPUT_DIR!
echo   Icon: %CD%\icon.ico
echo.
```

**改进**：显示所有关键配置参数，便于调试

### 3. 改进错误处理 ([build-package.bat:483-489](build-package.bat:483-489))

```batch
if errorlevel 1 (
    echo.
    echo ERROR: Inno Setup compilation failed
    echo Check the error messages above
    pause
    exit /b 1
)
```

**改进**：明确显示编译失败并提示检查错误信息

### 4. 验证输出文件 ([build-package.bat:491-507](build-package.bat:491-507))

```batch
:: Verify Inno Setup output
set "EXPECTED_INSTALLER=!INNO_OUTPUT_DIR!\SynapseAutomation-Setup-v%BUILD_NUM%.exe"
if exist "!EXPECTED_INSTALLER!" (
    echo.
    echo OK: Inno Setup installer generated successfully
    echo File: SynapseAutomation-Setup-v%BUILD_NUM%.exe
    for %%F in ("!EXPECTED_INSTALLER!") do (
        echo Size: %%~zF bytes
    )
) else (
    echo.
    echo ERROR: Expected installer not found: !EXPECTED_INSTALLER!
    echo Listing files in !INNO_OUTPUT_DIR!:
    dir "!INNO_OUTPUT_DIR!\*.exe" /B 2>nul
    pause
    exit /b 1
)
```

**改进**：
- 验证预期的安装程序文件是否存在
- 如果不存在，列出实际生成的文件
- 显示文件大小以确认生成成功

### 5. 改进 NSIS 处理 ([build-package.bat:363-392](build-package.bat:363-392))

```batch
if "%PACKAGE_TYPE%"=="1" (
    echo ============================================
    echo Using NSIS installer
    echo ============================================
    echo.
    call npm run build

    if errorlevel 1 (
        echo ERROR: npm run build failed
        pause
        exit /b 1
    )

    if exist "%ELECTRON_DIST%\*.exe" (
        echo Moving NSIS installer...
        move "%ELECTRON_DIST%\*.exe" "%OUTPUT_DIR%\" >nul
        if errorlevel 1 (
            echo ERROR: failed to move NSIS installer
            pause
            exit /b 1
        )
        echo OK: NSIS installer generated
        for %%F in ("%OUTPUT_DIR%\*.exe") do (
            echo File: %%~nxF (%%~zF bytes)
        )
    ) else (
        echo ERROR: NSIS installer not found in %ELECTRON_DIST%
        pause
        exit /b 1
    )
)
```

**改进**：
- 添加清晰的标题显示使用 NSIS
- 添加错误检查
- 显示生成的文件信息

### 6. 改进最终输出摘要 ([build-package.bat:532-575](build-package.bat:532-575))

```batch
echo ============================================
echo OK: packaging complete
echo ============================================
echo.
echo Build type:
if "%PACKAGE_TYPE%"=="1" echo   NSIS installer
if "%PACKAGE_TYPE%"=="2" echo   Inno Setup installer
if "%PACKAGE_TYPE%"=="3" echo   Directory only
echo.
echo Output directory: %OUTPUT_DIR%
echo.
echo Generated files:
echo.
if exist "%OUTPUT_DIR%\win-unpacked" (
    echo   [+] win-unpacked directory
    echo       Path: %OUTPUT_DIR%\win-unpacked\SynapseAutomation.exe
)
if exist "%OUTPUT_DIR%\*.exe" (
    echo.
    echo   [+] Installer executable:
    for %%F in ("%OUTPUT_DIR%\*.exe") do (
        echo       File: %%~nxF
        echo       Size: %%~zF bytes
        if "%PACKAGE_TYPE%"=="1" echo       Type: NSIS installer
        if "%PACKAGE_TYPE%"=="2" echo       Type: Inno Setup installer
    )
)
```

**改进**：
- 明确显示构建类型（NSIS / Inno Setup / Directory only）
- 列出生成的文件及其类型
- 提供清晰的下一步测试指引

## 测试步骤

要验证修复，请运行以下测试：

### 1. 清理旧的构建输出

```batch
cd desktop-electron
rd /s /q dist-build 2>nul
rd /s /q dist-out 2>nul
```

### 2. 运行 Inno Setup 构建

```batch
cd ..
.\build-package.bat
```

在提示时选择 **选项 2 (Inno Setup installer)**

### 3. 验证输出

构建完成后，检查：

1. **查看输出目录**：
   ```batch
   cd desktop-electron\dist-out\v2
   dir
   ```

2. **验证安装程序类型**：
   ```batch
   file "SynapseAutomation-Setup-v2.exe"
   ```

   应该显示 "Inno Setup" 而不是 "Nullsoft Installer"

3. **检查文件大小**：
   Inno Setup 生成的安装程序通常比 NSIS 生成的文件大小不同

## 预期结果

修复后，当选择 Inno Setup 时：

- ✅ 脚本会显示 "Using Inno Setup installer"
- ✅ 显示详细的配置信息（版本、源路径、输出路径）
- ✅ 运行 ISCC.exe 编译 installer.iss
- ✅ 验证输出文件存在
- ✅ 最终摘要明确显示 "Type: Inno Setup installer"
- ✅ 生成的文件名为 `SynapseAutomation-Setup-vX.exe`
- ✅ 文件类型为 Inno Setup 安装程序（非 NSIS）

## 附加说明

### 文件命名差异

- **NSIS**: `SynapseAutomation Setup X.X.X.exe`
- **Inno Setup**: `SynapseAutomation-Setup-vX.exe` (X 是 build number)

### Inno Setup 安装位置

脚本会自动检测以下位置的 Inno Setup：
1. `%INNO_PATH%` 环境变量
2. `%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe`
3. `%ProgramFiles(x86)%\Inno Setup 6\Compil32.exe`
4. `%ProgramFiles%\Inno Setup 6\ISCC.exe`
5. `%ProgramFiles%\Inno Setup 6\Compil32.exe`

如果未安装，请从 https://jrsoftware.org/isdl.php 下载安装。

## 相关文件

- [build-package.bat](build-package.bat) - 主构建脚本
- [installer.iss](desktop-electron/installer.iss) - Inno Setup 配置
- [package.json](desktop-electron/package.json) - electron-builder 配置

## 日期

2026-01-15
