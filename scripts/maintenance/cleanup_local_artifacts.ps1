param(
  [switch]$Apply
)

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path

$Targets = @(
  "syn_frontend_react\\.next",
  "syn_frontend_react\\out",
  "syn_frontend_react\\node_modules",
  "node_modules",
  "temp",
  "logs",
  "syn_backend\\logs",
  "syn_backend\\venv",
  "synenv",
  "syn_backend\\syn_backend",
  "syn_backend\\config\\syn_backend"
)

Write-Host "[cleanup] root: $RootDir"
Write-Host "[cleanup] mode: $(if ($Apply) { 'APPLY' } else { 'DRY-RUN' })"
Write-Host ""

foreach ($rel in $Targets) {
  $path = Join-Path $RootDir $rel
  if (-not (Test-Path $path)) { continue }

  $size = ""
  try {
    $bytes = (Get-ChildItem -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    if ($bytes -gt 0) { $size = "{0:N2} MB" -f ($bytes / 1MB) } else { $size = "?" }
  } catch {
    $size = "?"
  }

  Write-Host "[cleanup] target: $rel ($size)"
  if ($Apply) {
    Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "[cleanup] removed: $rel"
  }
  Write-Host ""
}

if (-not $Apply) {
  Write-Host "[cleanup] dry-run complete."
  Write-Host "[cleanup] re-run with -Apply to actually delete."
}
