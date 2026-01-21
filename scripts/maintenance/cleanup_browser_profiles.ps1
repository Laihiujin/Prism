param(
  [switch]$Apply,
  [switch]$Aggressive,
  [switch]$IncludeServiceWorkerCache,
  [string]$Root = ""
)

function Get-PathSizeBytes([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) { return 0 }
  $item = Get-Item -LiteralPath $Path -Force
  if ($item.PSIsContainer) {
    $sum = (Get-ChildItem -LiteralPath $Path -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    if ($null -eq $sum) { return 0 }
    return [int64]$sum
  }
  return [int64]$item.Length
}

if ([string]::IsNullOrWhiteSpace($Root)) {
  $Root = (Resolve-Path (Join-Path $PSScriptRoot "..\\..\\syn_backend\\browser_profiles")).Path
}

if (-not (Test-Path -LiteralPath $Root)) {
  Write-Host "[cleanup] browser_profiles not found: $Root"
  exit 1
}

$profileLevelDirs = @(
  "Crashpad",
  "GrShaderCache",
  "ShaderCache",
  "GraphiteDawnCache",
  "DawnGraphiteCache",
  "DawnWebGPUCache"
)

$defaultLevelDirs = @(
  "Cache",
  "Code Cache",
  "GPUCache",
  "DawnGraphiteCache",
  "DawnWebGPUCache"
)

$aggressiveDirs = @(
  "screen_ai",
  "component_crx_cache",
  "WasmTtsEngine",
  "WidevineCdm",
  "optimization_guide_model_store",
  "Safe Browsing",
  "segmentation_platform"
)

$aggressiveFiles = @(
  "BrowserMetrics-spare.pma"
)

Write-Host "[cleanup] root: $Root"
Write-Host "[cleanup] mode: $(if ($Apply) { 'APPLY' } else { 'DRY-RUN' })"
Write-Host "[cleanup] aggressive: $(if ($Aggressive) { 'ON' } else { 'OFF' })"
Write-Host "[cleanup] include_service_worker_cache: $(if ($IncludeServiceWorkerCache) { 'ON' } else { 'OFF' })"
Write-Host ""
Write-Host "[cleanup] run this when all browsers are closed to avoid file locks."
Write-Host ""

$totalBytes = 0
$totalTargets = 0

$accounts = Get-ChildItem -LiteralPath $Root -Force -Directory
foreach ($acct in $accounts) {
  Write-Host "== $($acct.Name) =="
  $targets = @()

  foreach ($dir in $profileLevelDirs) {
    $targets += (Join-Path $acct.FullName $dir)
  }

  foreach ($dir in $defaultLevelDirs) {
    $targets += (Join-Path $acct.FullName (Join-Path "Default" $dir))
  }

  if ($IncludeServiceWorkerCache) {
    $targets += (Join-Path $acct.FullName (Join-Path "Default" "Service Worker\\CacheStorage"))
  }

  if ($Aggressive) {
    foreach ($dir in $aggressiveDirs) {
      $targets += (Join-Path $acct.FullName $dir)
    }
    foreach ($file in $aggressiveFiles) {
      $targets += (Join-Path $acct.FullName $file)
    }
  }

  $hadTarget = $false
  foreach ($target in $targets) {
    if (-not (Test-Path -LiteralPath $target)) { continue }
    $hadTarget = $true
    $bytes = Get-PathSizeBytes $target
    $totalBytes += $bytes
    $totalTargets++

    $sizeMb = [Math]::Round(($bytes / 1MB), 2)
    Write-Host ("  {0} ({1} MB)" -f $target, $sizeMb)

    if ($Apply) {
      Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction SilentlyContinue
    }
  }

  if (-not $hadTarget) {
    Write-Host "  (no targets found)"
  }

  Write-Host ""
}

Write-Host ("[cleanup] targets: {0}" -f $totalTargets)
Write-Host ("[cleanup] total size: {0:N2} MB" -f ($totalBytes / 1MB))
if (-not $Apply) {
  Write-Host "[cleanup] dry-run complete."
  Write-Host "[cleanup] re-run with -Apply to actually delete."
}
