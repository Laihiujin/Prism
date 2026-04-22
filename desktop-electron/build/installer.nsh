!macro customInit
  ; Close running app to avoid file locks during install
  nsExec::ExecToLog 'taskkill /F /IM SynapseAutomation.exe'
!macroend
