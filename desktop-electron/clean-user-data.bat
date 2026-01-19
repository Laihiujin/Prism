@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo Clean User Data from Packaged Output
echo ============================================
echo.

set "TARGET_DIR=%~dp0dist-out\v1\win-unpacked\resources\syn_backend"

if not exist "%TARGET_DIR%" (
    echo ERROR: Target directory not found: %TARGET_DIR%
    pause
    exit /b 1
)

echo Target: %TARGET_DIR%
echo.
echo Cleaning user data directories...
echo.

:: Remove browser profiles (cookies, cache, etc.)
if exist "%TARGET_DIR%\browser_profiles" (
    echo [1/9] Removing browser_profiles...
    rd /s /q "%TARGET_DIR%\browser_profiles" 2>nul
    echo   OK
) else (
    echo [1/9] browser_profiles - not found
)

:: Remove cookies
if exist "%TARGET_DIR%\data\cookies" (
    echo [2/9] Removing data\cookies...
    rd /s /q "%TARGET_DIR%\data\cookies" 2>nul
    echo   OK
) else (
    echo [2/9] data\cookies - not found
)

:: Remove cookiesFile
if exist "%TARGET_DIR%\cookiesFile" (
    echo [3/9] Removing cookiesFile...
    rd /s /q "%TARGET_DIR%\cookiesFile" 2>nul
    echo   OK
) else (
    echo [3/9] cookiesFile - not found
)

:: Remove fingerprints
if exist "%TARGET_DIR%\fingerprints" (
    echo [4/9] Removing fingerprints...
    rd /s /q "%TARGET_DIR%\fingerprints" 2>nul
    echo   OK
) else (
    echo [4/9] fingerprints - not found
)

:: Remove videoFile
if exist "%TARGET_DIR%\videoFile" (
    echo [5/9] Removing videoFile...
    rd /s /q "%TARGET_DIR%\videoFile" 2>nul
    echo   OK
) else (
    echo [5/9] videoFile - not found
)

:: Remove logs
if exist "%TARGET_DIR%\logs" (
    echo [6/9] Removing logs...
    rd /s /q "%TARGET_DIR%\logs" 2>nul
    echo   OK
) else (
    echo [6/9] logs - not found
)

:: Remove backups
if exist "%TARGET_DIR%\backups" (
    echo [7/9] Removing backups...
    rd /s /q "%TARGET_DIR%\backups" 2>nul
    echo   OK
) else (
    echo [7/9] backups - not found
)

:: Remove database files
echo [8/9] Removing database files...
del /q "%TARGET_DIR%\db\*.db" 2>nul
del /q "%TARGET_DIR%\db\*.db-*" 2>nul
del /q "%TARGET_DIR%\db\*.sqlite" 2>nul
del /q "%TARGET_DIR%\db\*.sqlite-*" 2>nul
del /q "%TARGET_DIR%\db\frontend_accounts_snapshot.json" 2>nul
echo   OK

:: Remove Python cache
echo [9/9] Removing Python cache...
for /d /r "%TARGET_DIR%" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q "%TARGET_DIR%\*.pyc" 2>nul
del /s /q "%TARGET_DIR%\*.pyo" 2>nul
echo   OK

echo.
echo ============================================
echo Cleanup complete!
echo ============================================
pause
