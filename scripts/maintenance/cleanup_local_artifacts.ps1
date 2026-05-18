param(
  [switch]$Apply,
  [switch]$IncludeNodeModules,
  [switch]$IncludeVirtualEnv,
  [switch]$IncludeBrowserDownloads,
  [switch]$IncludePackagingCache
)

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path

function New-CleanupTarget {
  param(
    [string]$Path,
    [string]$Group,
    [string]$Note
  )

  [pscustomobject]@{
    Path  = $Path
    Group = $Group
    Note  = $Note
  }
}

$targets = @(
  (New-CleanupTarget ".tmp-channels-debug" "safe" "temporary channel debug data")
  (New-CleanupTarget ".tmp-hibbiki" "safe" "temporary browser download cache")
  (New-CleanupTarget "dist" "safe" "root packaging output")
  (New-CleanupTarget "logs" "safe" "root logs")
  (New-CleanupTarget "tmp" "safe" "scratch runtime files")
  (New-CleanupTarget "tmp-runtime-data" "safe" "temporary runtime data")
  (New-CleanupTarget "gcm-diagnose.log" "safe" "one-off Git Credential Manager diagnostics")
  (New-CleanupTarget "syn_backend\\logs" "safe" "backend logs")
  (New-CleanupTarget "syn_frontend_react\\.next" "safe" "Next.js build cache")
  (New-CleanupTarget "syn_frontend_react\\out" "safe" "frontend export output")
  (New-CleanupTarget "desktop-electron\\dist-build" "safe" "Electron build output")
  (New-CleanupTarget "desktop-electron\\out" "safe" "Electron packager output")
)

if ($IncludePackagingCache) {
  $targets += New-CleanupTarget "build\\supervisor" "optional" "PyInstaller intermediate cache"
}

if ($IncludeNodeModules) {
  $targets += New-CleanupTarget "node_modules" "optional" "root node modules"
  $targets += New-CleanupTarget "syn_frontend_react\\node_modules" "optional" "frontend node modules"
}

if ($IncludeVirtualEnv) {
  $targets += New-CleanupTarget "synenv" "optional" "shared Python environment"
}

if ($IncludeBrowserDownloads) {
  $targets += New-CleanupTarget "browsers\\chromium" "optional" "downloaded Chromium payloads"
  $targets += New-CleanupTarget "browsers\\chromium_headless_shell-1200" "optional" "downloaded Chromium headless shell"
  $targets += New-CleanupTarget "browsers\\ffmpeg-1011" "optional" "downloaded browser ffmpeg payload"
  $targets += New-CleanupTarget "browsers\\firefox-1497" "optional" "downloaded Firefox payload"
  $targets += New-CleanupTarget "browsers\\winldd-1007" "optional" "downloaded browser dependency payload"
}

function Get-TargetSizeBytes {
  param([string]$LiteralPath)

  $item = Get-Item -LiteralPath $LiteralPath -Force -ErrorAction SilentlyContinue
  if (-not $item) {
    return 0
  }

  if (-not $item.PSIsContainer) {
    return [int64]$item.Length
  }

  $sum = (Get-ChildItem -LiteralPath $LiteralPath -Recurse -Force -ErrorAction SilentlyContinue |
    Measure-Object -Property Length -Sum).Sum

  if ($null -eq $sum) {
    return 0
  }

  return [int64]$sum
}

function Remove-CleanupTarget {
  param([string]$LiteralPath)

  if (-not (Test-Path -LiteralPath $LiteralPath)) {
    return $false
  }

  try {
    Remove-Item -LiteralPath $LiteralPath -Recurse -Force -ErrorAction Stop
    return $true
  } catch {
    Write-Warning "[cleanup] failed to remove: $LiteralPath"
    Write-Warning $_.Exception.Message
    return $false
  }
}

Write-Host "[cleanup] root: $RootDir"
Write-Host "[cleanup] mode: $(if ($Apply) { 'APPLY' } else { 'DRY-RUN' })"
Write-Host ""

$rows = foreach ($target in $targets) {
  $resolved = Join-Path $RootDir $target.Path
  if (-not (Test-Path -LiteralPath $resolved)) {
    continue
  }

  $sizeBytes = Get-TargetSizeBytes -LiteralPath $resolved
  $itemCount = if ((Get-Item -LiteralPath $resolved -Force).PSIsContainer) {
    (Get-ChildItem -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object).Count
  } else {
    1
  }

  [pscustomobject]@{
    Group   = $target.Group
    Path    = $target.Path
    SizeMB  = [math]::Round(($sizeBytes / 1MB), 2)
    Items   = $itemCount
    Note    = $target.Note
    Removed = $false
  }
}

if (-not $rows) {
  Write-Host "[cleanup] no matching targets found."
  exit 0
}

$rows | Format-Table -AutoSize
Write-Host ""

if (-not $Apply) {
  Write-Host "[cleanup] dry-run complete."
  Write-Host "[cleanup] re-run with -Apply to delete the listed targets."
  exit 0
}

$removedCount = 0
foreach ($row in $rows) {
  $resolved = Join-Path $RootDir $row.Path
  if (Remove-CleanupTarget -LiteralPath $resolved) {
    $removedCount += 1
    Write-Host "[cleanup] removed: $($row.Path)"
  }
}

Write-Host ""
Write-Host "[cleanup] removed targets: $removedCount"
