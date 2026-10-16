$ErrorActionPreference = 'Stop'
# Compatibility entry: all provisioning uses the same hidden launcher.
& (Join-Path $PSScriptRoot 'scripts\start-background.ps1') @args
exit $LASTEXITCODE
