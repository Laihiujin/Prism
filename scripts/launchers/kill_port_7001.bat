@echo off
chcp 65001 >nul
set "PORT=7001"
echo Killing all processes listening on port %PORT%...

for /l %%i in (1,1,6) do (
  powershell -NoProfile -Command "$pids=(Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue).OwningProcess | Sort-Object -Unique; foreach($pid in $pids){ try{ Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue }catch{}; try{ taskkill /F /T /PID $pid ^| Out-Null }catch{} }"
  timeout /t 1 /nobreak >nul
  powershell -NoProfile -Command "if(-not (Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue)){ exit 0 } else { exit 1 }"
  if not errorlevel 1 goto :done
)

echo [WARN] Port %PORT% is still in use. Showing listeners:
netstat -ano | findstr ":%PORT%" | findstr "LISTENING"
:done
echo Done.
pause
