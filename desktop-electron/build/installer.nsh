!macro KillPrismProcess imageName
  DetailPrint "Stopping ${imageName} if running..."
  nsExec::ExecToLog 'taskkill /IM ${imageName}'
  Sleep 800
  nsExec::ExecToLog 'taskkill /F /T /IM ${imageName}'
!macroend

!macro customInit
  ; Stop the packaged app and all managed child processes before install.
  !insertmacro KillPrismProcess "Prism.exe"
  !insertmacro KillPrismProcess "supervisor.exe"
  !insertmacro KillPrismProcess "backend.exe"
  !insertmacro KillPrismProcess "automation-worker.exe"
  !insertmacro KillPrismProcess "celery-worker.exe"
  !insertmacro KillPrismProcess "redis-server.exe"
  Sleep 1500
!macroend

!macro customInstall
  CreateShortCut "$DESKTOP\Prism.lnk" "$INSTDIR\Prism.exe"
!macroend

!macro customUnInstall
  Delete "$DESKTOP\Prism.lnk"
!macroend
