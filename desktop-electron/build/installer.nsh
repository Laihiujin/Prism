!macro KillSynapseProcess imageName
  DetailPrint "Stopping ${imageName} if running..."
  nsExec::ExecToLog 'taskkill /IM ${imageName}'
  Sleep 800
  nsExec::ExecToLog 'taskkill /F /T /IM ${imageName}'
!macroend

!macro customInit
  ; Stop the packaged app and all managed child processes before install.
  !insertmacro KillSynapseProcess "SynapseAutomation.exe"
  !insertmacro KillSynapseProcess "supervisor.exe"
  !insertmacro KillSynapseProcess "backend.exe"
  !insertmacro KillSynapseProcess "playwright-worker.exe"
  !insertmacro KillSynapseProcess "celery-worker.exe"
  !insertmacro KillSynapseProcess "redis-server.exe"
  Sleep 1500
!macroend

!macro customInstall
  CreateShortCut "$DESKTOP\SynapseAutomation.lnk" "$INSTDIR\SynapseAutomation.exe"
!macroend

!macro customUnInstall
  Delete "$DESKTOP\SynapseAutomation.lnk"
!macroend
