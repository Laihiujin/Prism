cd /d E:\Siuyechu\Prism\desktop-electron

set APP_VERSION=1.1.0
set APP_BUILD_NUM=1
set SOURCE_DIR=%CD%\dist-out\v1\win-unpacked
set OUTPUT_DIR=%CD%\dist-out\v1
set OUTPUT_DIR_INNO=%OUTPUT_DIR%
set ICON_FILE=%CD%\icon.ico

"C:\Program Files (x86)\Inno Setup 6\Compil32.exe" installer.iss
pause
