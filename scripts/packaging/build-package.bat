@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ============================================
::   SynapseAutomation Package Script
:: ============================================
echo.
echo ============================================
echo   SynapseAutomation Package Script
echo ============================================
echo.

set "AUTO_YES=%SYNAPSE_AUTO_YES%"
set "AUTO_PACKAGE_TYPE=%SYNAPSE_PACKAGE_TYPE%"
set "PF86="
set "PF64="
for %%I in ("%ProgramFiles(x86)%") do set "PF86=%%~sI"
for %%I in ("%ProgramFiles%") do set "PF64=%%~sI"

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "PROJECT_ROOT=%%~fI\"
set "PROJECT_ROOT_ARG=%PROJECT_ROOT%"
if "%PROJECT_ROOT_ARG:~-1%"=="\" set "PROJECT_ROOT_ARG=%PROJECT_ROOT_ARG:~0,-1%"
cd /d "%PROJECT_ROOT%desktop-electron"
set "ELECTRON_DIST=dist-build"

:: ============================================
:: 0. Sanitize release workspace
:: ============================================
echo [0/7] Sanitize release workspace...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%scripts\release\prepare-release.ps1" -ProjectRoot "%PROJECT_ROOT_ARG%"
if errorlevel 1 (
    echo ERROR: release workspace sanitization failed
    pause
    exit /b 1
)
echo OK: release workspace sanitized
echo.

:: ============================================
:: 0.25 Prepare packaged synenv and Hermes runtime
:: ============================================
echo [0.25/7] Prepare packaged synenv and Hermes runtime...
echo.
if not exist "%PROJECT_ROOT%synenv\Scripts\python.exe" (
    python -m venv "%PROJECT_ROOT%synenv"
    if errorlevel 1 (
        echo ERROR: failed to create synenv virtual environment
        pause
        exit /b 1
    )
)

"%PROJECT_ROOT%synenv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: failed to upgrade pip in synenv
    pause
    exit /b 1
)

"%PROJECT_ROOT%synenv\Scripts\python.exe" -m pip install -r "%PROJECT_ROOT%requirements.txt"
if errorlevel 1 (
    echo ERROR: failed to install packaging requirements into synenv
    pause
    exit /b 1
)

"%PROJECT_ROOT%synenv\Scripts\python.exe" -m pip uninstall -y patchright
if errorlevel 1 (
    echo ERROR: failed to remove stale patchright package from synenv
    pause
    exit /b 1
)

"%PROJECT_ROOT%synenv\Scripts\python.exe" -m pip install pyinstaller psutil playwright patchright==1.59.1
if errorlevel 1 (
    echo ERROR: failed to install packaged runtime dependencies into synenv
    pause
    exit /b 1
)

"%PROJECT_ROOT%synenv\Scripts\python.exe" -c "import importlib.metadata; version = importlib.metadata.version('patchright'); assert version == '1.59.1', version"
if errorlevel 1 (
    echo ERROR: packaged synenv resolved an unexpected patchright version
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%scripts\hermes\setup-local-hermes.ps1" -Branch main -WebUIVersion v0.51.50
if errorlevel 1 (
    echo ERROR: failed to prepare embedded Hermes runtime
    pause
    exit /b 1
)

if not exist "%PROJECT_ROOT%synenv\Scripts\python.exe" (
    echo ERROR: embedded runtime missing python: %PROJECT_ROOT%synenv\Scripts\python.exe
    pause
    exit /b 1
)
if not exist "%PROJECT_ROOT%synenv\_python\python.exe" (
    echo ERROR: embedded runtime missing base python home: %PROJECT_ROOT%synenv\_python\python.exe
    pause
    exit /b 1
)
if not exist "%PROJECT_ROOT%synenv\.hermes-runtime-ready" (
    echo ERROR: embedded runtime readiness marker missing: %PROJECT_ROOT%synenv\.hermes-runtime-ready
    pause
    exit /b 1
)
if not exist "%PROJECT_ROOT%tools\hermes-agent\run_agent.py" (
    echo ERROR: embedded Hermes agent missing: %PROJECT_ROOT%tools\hermes-agent\run_agent.py
    pause
    exit /b 1
)
if not exist "%PROJECT_ROOT%tools\hermes-webui\server.py" (
    echo ERROR: embedded Hermes WebUI missing: %PROJECT_ROOT%tools\hermes-webui\server.py
    pause
    exit /b 1
)
echo OK: packaged synenv and Hermes runtime ready
echo.

:: ============================================
:: 0.5 Build packaged backend services
:: ============================================
echo [0.5/7] Build packaged backend services...
echo.
if exist "%PROJECT_ROOT%synenv\Scripts\python.exe" (
    set "PACKAGING_PYTHON=%PROJECT_ROOT%synenv\Scripts\python.exe"
)
if not defined PACKAGING_TARGETS set "PACKAGING_TARGETS=backend,celery-worker,playwright-worker"
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%scripts\packaging\build_services.ps1"
if errorlevel 1 (
    echo ERROR: packaged backend service build failed
    pause
    exit /b 1
)
echo OK: packaged backend services built
echo.

:: ============================================
:: 1. Check and stop running process
:: ============================================
echo [1/7] Check and stop running process...
echo.
tasklist /FI "IMAGENAME eq SynapseAutomation.exe" 2>NUL | find /I /N "SynapseAutomation.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo WARNING: SynapseAutomation.exe is running
    if /I "%AUTO_YES%"=="1" (
        echo Auto mode: stopping process
    ) else (
        choice /C YN /M "Stop the process to continue"
        if errorlevel 2 (
            echo ERROR: packaging canceled by user
            pause
            exit /b 1
        )
    )
    echo Stopping process...
    taskkill /F /IM SynapseAutomation.exe >nul 2>&1
    timeout /t 2 >nul
    echo OK: process stopped
) else (
    echo OK: no running process found
)
echo.

:: Stop packaged services that may lock dist-build/dist-out files
powershell -Command "Get-Process | Where-Object { $_.Path -and ( $_.Path -like '*\dist-build\win-unpacked\resources\services\*' -or $_.Path -like '*\dist\win-unpacked\resources\services\*' -or $_.Path -like '*\dist-out\*\win-unpacked\resources\services\*' -or $_.Path -like '*\dist-build\win-unpacked\resources\syn_backend\*' -or $_.Path -like '*\dist\win-unpacked\resources\syn_backend\*' -or $_.Path -like '*\dist-out\*\win-unpacked\resources\syn_backend\*' ) } | Stop-Process -Force" >nul 2>&1

:: ============================================
:: 2. Check Supervisor
:: ============================================
echo [2/7] Check Supervisor status...
echo.

set "SUPERVISOR_PATH="
set "SUPERVISOR_FOUND=0"

:: Location 1: build\supervisor\supervisor.exe (standard)
if exist "%PROJECT_ROOT%build\supervisor\supervisor.exe" (
    set "SUPERVISOR_PATH=%PROJECT_ROOT%build\supervisor\supervisor.exe"
    set "SUPERVISOR_FOUND=1"
)

:: Location 2: dist\supervisor.exe (PyInstaller output)
if "%SUPERVISOR_FOUND%"=="0" (
    if exist "%PROJECT_ROOT%dist\supervisor.exe" (
        set "SUPERVISOR_PATH=%PROJECT_ROOT%dist\supervisor.exe"
        set "SUPERVISOR_FOUND=1"
        echo INFO: supervisor.exe found in dist
        echo Copying to standard location...
        if not exist "%PROJECT_ROOT%build\supervisor" mkdir "%PROJECT_ROOT%build\supervisor"
        copy /Y "%PROJECT_ROOT%dist\supervisor.exe" "%PROJECT_ROOT%build\supervisor\supervisor.exe" >nul
        set "SUPERVISOR_PATH=%PROJECT_ROOT%build\supervisor\supervisor.exe"
    )
)

if "%SUPERVISOR_FOUND%"=="0" (
    echo WARNING: Supervisor not found
    echo.
    echo Checked locations:
    echo   - %PROJECT_ROOT%build\supervisor\supervisor.exe
    echo   - %PROJECT_ROOT%dist\supervisor.exe
    echo.
    if /I "%AUTO_YES%"=="1" (
        echo Auto mode: continue without Supervisor
    ) else (
        choice /C YN /M "Supervisor not built. Continue anyway (not recommended)"
        if errorlevel 2 (
            echo ERROR: packaging canceled by user
            pause
            exit /b 1
        )
    )
    echo WARNING: continuing without Supervisor...
) else (
    echo OK: Supervisor ready
    echo Path: %SUPERVISOR_PATH%

    tasklist /FI "IMAGENAME eq supervisor.exe" 2>NUL | find /I /N "supervisor.exe">NUL
    if "%ERRORLEVEL%"=="0" (
        echo INFO: Supervisor is running
        taskkill /F /IM supervisor.exe >nul 2>&1
        timeout /t 1 >nul
        echo OK: Supervisor stopped
    )
)
echo.

:: ============================================
:: 3. Read and update version info
:: ============================================
echo [3/7] Read version info...
echo.

set "VERSION_FILE=%PROJECT_ROOT%scripts\packaging\build-version.json"
if not exist "%VERSION_FILE%" (
    echo Creating version file...
    echo {"version": "2.2.0", "buildNumber": 2, "lastBuildDate": ""} > "%VERSION_FILE%"
)

for /f "tokens=2 delims=:, " %%a in ('findstr "version" "%VERSION_FILE%"') do (
    set "CURRENT_VERSION=%%~a"
)
for /f "tokens=2 delims=:, " %%a in ('findstr "buildNumber" "%VERSION_FILE%"') do (
    set "BUILD_NUM=%%~a"
)

echo Current version: %CURRENT_VERSION%
echo Build number: v%BUILD_NUM%
set "FULL_VERSION=%CURRENT_VERSION%.%BUILD_NUM%"
echo Full version: %FULL_VERSION%
echo.

:: ============================================
:: 4. Clean old build output
:: ============================================
echo [4/7] Clean old build output...
echo.

if exist "%ELECTRON_DIST%\win-unpacked" (
    echo Cleaning %ELECTRON_DIST%\win-unpacked...
    rd /s /q "%ELECTRON_DIST%\win-unpacked" 2>nul
    timeout /t 1 >nul
)

if exist "%ELECTRON_DIST%\*.exe" (
    echo Removing old installers...
    del /q "%ELECTRON_DIST%\*.exe" 2>nul
)

echo OK: cleanup complete
echo.

:: ============================================
:: 5. Check icon file
:: ============================================
echo [5/7] Check icon file...
echo.

if not exist "icon.ico" (
    echo WARNING: icon.ico not found
    echo Using default icon
    echo.
) else (
    echo OK: icon.ico ready
    for %%F in ("icon.ico") do (
        echo File: %%~nxF
        echo Size: %%~zF bytes
    )
    echo.
)

:: ============================================
:: 6. Build frontend (Next.js standalone)
:: ============================================
echo [6/7] Building frontend (Next.js standalone)...
echo.

set "FRONTEND_DIR=%PROJECT_ROOT%syn_frontend_react"
if not exist "%FRONTEND_DIR%\package.json" (
    echo ERROR: frontend directory not found: %FRONTEND_DIR%
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\node_modules" (
    echo ERROR: frontend node_modules missing. Run: cd %FRONTEND_DIR% ^&^& npm install
    pause
    exit /b 1
)

pushd "%FRONTEND_DIR%"
call npm run build
if errorlevel 1 (
    echo ERROR: frontend build failed
    popd
    pause
    exit /b 1
)
if not exist ".next\standalone\server.js" (
    echo ERROR: frontend standalone output missing: .next\standalone\server.js
    popd
    pause
    exit /b 1
)
popd

echo OK: frontend build complete
echo.

:: ============================================
:: 7. Packaging
:: ============================================
echo [7/7] Packaging
echo.

:: ============================================
:: Stage 1: build win-unpacked directory
:: ============================================
echo.
echo Start packaging...
echo ============================================
echo.
echo Building win-unpacked directory...
echo This may take 5-10 minutes. Please wait...
echo.

setlocal DisableDelayedExpansion
set "EB_CLI=%CD%\node_modules\electron-builder\cli.js"
if exist "%EB_CLI%" (
    powershell -NoProfile -Command "Set-Location -LiteralPath '%CD%'; node '%EB_CLI%' --win --x64 --dir --config.extraMetadata.version=%CURRENT_VERSION% --config.buildVersion=%FULL_VERSION%"
) else (
    powershell -NoProfile -Command "Set-Location -LiteralPath '%CD%'; npm run build:dir -- --config.extraMetadata.version=%CURRENT_VERSION% --config.buildVersion=%FULL_VERSION%"
)
set "BUILD_DIR_RC=%ERRORLEVEL%"
endlocal & set "BUILD_DIR_RC=%BUILD_DIR_RC%"

if not "%BUILD_DIR_RC%"=="0" (
    echo.
    echo ERROR: packaging failed
    echo Check the error output above
    pause
    exit /b 1
)

set "UNPACKED_RES=%ELECTRON_DIST%\win-unpacked\resources"
if exist "%UNPACKED_RES%" (
    if not exist "%UNPACKED_RES%\synenv\Scripts\python.exe" (
        if exist "%PROJECT_ROOT%synenv\Scripts\python.exe" (
            echo Copying synenv into win-unpacked resources...
            xcopy /E /I /Y "%PROJECT_ROOT%synenv" "%UNPACKED_RES%\synenv\" >nul
        ) else (
            echo WARNING: synenv source missing: %PROJECT_ROOT%synenv
        )
    )
    if not exist "%UNPACKED_RES%\synenv\_python\python.exe" (
        if exist "%PROJECT_ROOT%synenv\_python\python.exe" (
            echo Copying synenv base python home into win-unpacked resources...
            xcopy /E /I /Y "%PROJECT_ROOT%synenv\_python" "%UNPACKED_RES%\synenv\_python\" >nul
        ) else (
            echo ERROR: synenv base python home missing: %PROJECT_ROOT%synenv\_python\python.exe
            pause
            exit /b 1
        )
    )
    if not exist "%UNPACKED_RES%\browsers" (
        if exist "%PROJECT_ROOT%browsers" (
            echo Copying browsers into win-unpacked resources...
            xcopy /E /I /Y "%PROJECT_ROOT%browsers" "%UNPACKED_RES%\browsers\" >nul
        ) else (
            echo WARNING: browsers source missing: %PROJECT_ROOT%browsers
        )
    )
    if not exist "%UNPACKED_RES%\services" (
        if exist "%PROJECT_ROOT%dist\services" (
            echo Copying packaged services into win-unpacked resources...
            xcopy /E /I /Y "%PROJECT_ROOT%dist\services" "%UNPACKED_RES%\services\" >nul
        ) else (
            echo WARNING: packaged services missing: %PROJECT_ROOT%dist\services
        )
    )

    if exist "%PROJECT_ROOT%syn_backend" (
        echo Updating syn_backend in win-unpacked resources...
        if exist "%UNPACKED_RES%\syn_backend" (
            echo   - Removing old syn_backend...
            rd /s /q "%UNPACKED_RES%\syn_backend" 2>nul
        )
        echo   - Copying latest syn_backend ^(excluding user data^)...
        robocopy "%PROJECT_ROOT%syn_backend" "%UNPACKED_RES%\syn_backend" /E /NFL /NDL /NJH /NJS /XD "__pycache__" ".pytest_cache" "tests" "logs" "backups" "browser_profiles" "videoFile" "cookiesFile" "fingerprints" /XF "*.pyc" "*.pyo" "test_*" "*.db" "*.db-*" "*.sqlite" "*.sqlite-*" "frontend_accounts_snapshot.json" >nul
        if errorlevel 8 (
            echo ERROR: failed to copy syn_backend
            pause
            exit /b 1
        )
        echo   OK: syn_backend updated successfully
    ) else (
        echo WARNING: syn_backend source missing: %PROJECT_ROOT%syn_backend
    )

    if not exist "%UNPACKED_RES%\tools\hermes-agent\run_agent.py" (
        if exist "%PROJECT_ROOT%tools\hermes-agent\run_agent.py" (
            echo Copying Hermes agent into win-unpacked resources...
            xcopy /E /I /Y "%PROJECT_ROOT%tools\hermes-agent" "%UNPACKED_RES%\tools\hermes-agent\" >nul
        ) else (
            echo WARNING: Hermes agent source missing: %PROJECT_ROOT%tools\hermes-agent
        )
    )

    if not exist "%UNPACKED_RES%\tools\hermes-webui\server.py" (
        if exist "%PROJECT_ROOT%tools\hermes-webui\server.py" (
            echo Copying Hermes WebUI into win-unpacked resources...
            xcopy /E /I /Y "%PROJECT_ROOT%tools\hermes-webui" "%UNPACKED_RES%\tools\hermes-webui\" >nul
        ) else (
            echo WARNING: Hermes WebUI source missing: %PROJECT_ROOT%tools\hermes-webui
        )
    )
) else (
    echo WARNING: %UNPACKED_RES% not found; skip resource sync.
)

if exist "%UNPACKED_RES%" (
    if not exist "%UNPACKED_RES%\synenv\Scripts\python.exe" (
        echo ERROR: win-unpacked missing synenv python: %UNPACKED_RES%\synenv\Scripts\python.exe
        pause
        exit /b 1
    )
    if not exist "%UNPACKED_RES%\synenv\_python\python.exe" (
        echo ERROR: win-unpacked missing synenv base python home: %UNPACKED_RES%\synenv\_python\python.exe
        pause
        exit /b 1
    )
)

:: ============================================
:: Move to versioned output directory
:: ============================================
echo.
echo Organizing output...

:: Wait for file handles to be released
timeout /t 2 /nobreak >nul

if not exist "dist-out" mkdir "dist-out"
set "OUTPUT_DIR=dist-out\v%BUILD_NUM%"
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

if exist "%ELECTRON_DIST%\win-unpacked" (
    echo Moving win-unpacked to %OUTPUT_DIR%...

    :: Remove old output if exists
    if exist "%OUTPUT_DIR%\win-unpacked" (
        echo Removing old output...
        rd /s /q "%OUTPUT_DIR%\win-unpacked" 2>nul
        timeout /t 1 /nobreak >nul
    )

    :: Try to move first (faster)
    move "%ELECTRON_DIST%\win-unpacked" "%OUTPUT_DIR%\win-unpacked" >nul 2>&1
    if errorlevel 1 (
        echo WARNING: move failed, using robocopy instead...
        robocopy "%ELECTRON_DIST%\win-unpacked" "%OUTPUT_DIR%\win-unpacked" /E /MOVE /NFL /NDL /NJH /NJS /R:3 /W:2 >nul
        if errorlevel 8 (
            echo ERROR: robocopy failed
            pause
            exit /b 1
        )
    )
    echo OK: win-unpacked moved
)

echo.
echo ============================================
echo OK: stage 1 complete
echo ============================================
echo.
echo Output directory: %OUTPUT_DIR%\win-unpacked
echo.
echo Please test:
echo   1. Run: %OUTPUT_DIR%\win-unpacked\SynapseAutomation.exe
echo   2. Check Supervisor starts
echo   3. Check backend service status
echo   4. Check frontend access
echo.
echo ============================================
echo.

:: ============================================
:: Select packaging type
:: ============================================
echo.
echo Choose packaging type:
echo   [1] NSIS installer
echo   [2] Inno Setup installer
echo   [3] Directory only
if defined AUTO_PACKAGE_TYPE (
    set "PACKAGE_TYPE=%AUTO_PACKAGE_TYPE%"
) else if /I "%AUTO_YES%"=="1" (
    set "PACKAGE_TYPE=2"
) else (
    set /p "PACKAGE_TYPE=Choose ^(1/2/3, default=2^): "
    if "!PACKAGE_TYPE!"=="" set "PACKAGE_TYPE=2"
)
set "PACKAGE_TYPE=!PACKAGE_TYPE: =!"
if "!PACKAGE_TYPE!"=="" set "PACKAGE_TYPE=2"

if "!PACKAGE_TYPE!"=="3" goto :DONE

if "!PACKAGE_TYPE!"=="1" goto :BUILD_NSIS_INSTALLER

if "!PACKAGE_TYPE!"=="2" (
    echo.
    echo ============================================
    echo Stage 2: build installer ^(Inno Setup^)
    echo ============================================
    echo.

    cd /d "%PROJECT_ROOT%desktop-electron"
    set "APP_VERSION=%CURRENT_VERSION%"
    set "APP_BUILD_NUM=%BUILD_NUM%"
    set "SOURCE_DIR=!CD!\!OUTPUT_DIR!\win-unpacked"
    set "OUTPUT_DIR=!CD!\!OUTPUT_DIR!"
    set "OUTPUT_DIR_INNO=!OUTPUT_DIR!"
    set "ICON_FILE=!CD!\icon.ico"

    if not exist "!SOURCE_DIR!" (
        echo ERROR: Source directory not found: !SOURCE_DIR!
        pause
        exit /b 1
    )

    if not exist "!SOURCE_DIR!\resources\syn_backend" (
        if exist "!PROJECT_ROOT!syn_backend" (
            echo INFO: syn_backend missing in output; copying...
            robocopy "!PROJECT_ROOT!syn_backend" "!SOURCE_DIR!\resources\syn_backend" /E /NFL /NDL /NJH /NJS /XD "__pycache__" ".pytest_cache" "tests" "logs" "backups" "browser_profiles" "videoFile" "cookiesFile" "fingerprints" /XF "*.pyc" "*.pyo" "test_*" "*.db" "*.db-*" "*.sqlite" "*.sqlite-*" "frontend_accounts_snapshot.json" >nul
            if errorlevel 8 (
                echo ERROR: failed to copy syn_backend
                pause
                exit /b 1
            )
        ) else (
            echo WARNING: syn_backend source missing: !PROJECT_ROOT!syn_backend
        )
    )

    set "INNO_ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    set "INNO_COMPIL32=C:\Program Files (x86)\Inno Setup 6\Compil32.exe"
    if exist "!INNO_ISCC!" (
        "!INNO_ISCC!" installer.iss
    ) else if exist "!INNO_COMPIL32!" (
        "!INNO_COMPIL32!" /cc installer.iss
    ) else (
        echo WARNING: Inno Setup not found, falling back to NSIS installer...
        goto :BUILD_NSIS_INSTALLER
    )
    if errorlevel 1 (
        echo ERROR: Inno Setup compilation failed
        pause
        exit /b 1
    )
    goto :DONE
)

:BUILD_NSIS_INSTALLER
echo.
echo ============================================
echo Stage 2: build installer ^(NSIS^)
echo ============================================
echo.
set "EB_CLI=%CD%\node_modules\electron-builder\cli.js"
if exist "!EB_CLI!" (
    powershell -NoProfile -Command "Set-Location -LiteralPath '%CD%'; node '!EB_CLI!' --win --x64 --config.extraMetadata.version=%CURRENT_VERSION% --config.buildVersion=%FULL_VERSION%"
) else (
    powershell -NoProfile -Command "Set-Location -LiteralPath '%CD%'; npm run build -- --config.extraMetadata.version=%CURRENT_VERSION% --config.buildVersion=%FULL_VERSION%"
)
if errorlevel 1 (
    echo ERROR: npm run build failed
    pause
    exit /b 1
)
if exist "%ELECTRON_DIST%\*.exe" (
    move "%ELECTRON_DIST%\*.exe" "%OUTPUT_DIR%\" >nul
    if errorlevel 1 (
        echo ERROR: failed to move NSIS installer
        pause
        exit /b 1
    )
) else (
    echo ERROR: NSIS installer not found in %ELECTRON_DIST%
    pause
    exit /b 1
)
goto :DONE

echo ERROR: invalid packaging type: !PACKAGE_TYPE!
pause
exit /b 1

:DONE
echo.
echo ============================================
echo OK: packaging complete
echo ============================================
echo Output directory: %OUTPUT_DIR%
echo.
if /I "%AUTO_YES%"=="1" goto :EOF
pause
goto :EOF
