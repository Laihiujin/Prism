$ErrorActionPreference = "Stop"

$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$pythonCandidates = @()
if ($env:PACKAGING_PYTHON) {
  $pythonCandidates += $env:PACKAGING_PYTHON
}
$pythonCandidates += @(
  (Join-Path $root "synenv\Scripts\python.exe"),
  "python"
)

$python = $null
foreach ($candidate in $pythonCandidates) {
  try {
    if ($candidate -like "*.exe" -or $candidate -like "*\python") {
      if (Test-Path $candidate) {
        $python = $candidate
        break
      }
    } else {
      $resolved = Get-Command $candidate -ErrorAction Stop
      $python = $resolved.Source
      break
    }
  } catch {
    continue
  }
}

if (-not $python) {
  Write-Error "No Python executable available for service packaging."
  exit 1
}

& $python -m pip show pyinstaller > $null 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Error "pyinstaller is not installed for $python"
  exit 1
}

$dist = Join-Path $root "dist\services"
$spec = Join-Path $root "dist\specs"
$build = Join-Path $root "dist\build"

New-Item -ItemType Directory -Force -Path $dist, $spec, $build | Out-Null

@("backend.exe", "celery-worker.exe", "playwright-worker.exe") | ForEach-Object {
  $legacyExe = Join-Path $dist $_
  if (Test-Path $legacyExe) {
    Remove-Item -LiteralPath $legacyExe -Force
  }
}

$pythonInfoJson = & $python -c "import json, os, pathlib, sys; print(json.dumps({'base_prefix': sys.base_prefix, 'prefix': sys.prefix, 'executable': sys.executable}))"
if ($LASTEXITCODE -ne 0) {
  Write-Error "Failed to inspect Python runtime information for $python"
  exit 1
}

$pythonInfo = $pythonInfoJson | ConvertFrom-Json
$runtimeDllDirs = @(
  (Join-Path $pythonInfo.base_prefix "DLLs"),
  (Join-Path $pythonInfo.base_prefix "Library\bin"),
  (Join-Path $pythonInfo.prefix "DLLs"),
  (Join-Path $pythonInfo.prefix "Library\bin")
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

$runtimeDllArgs = @()
foreach ($dllDir in $runtimeDllDirs) {
  Get-ChildItem -Path $dllDir -Filter *.dll -File -ErrorAction SilentlyContinue | ForEach-Object {
    $runtimeDllArgs += @("--add-binary", "$($_.FullName);.")
  }
}

$common = @(
  "--noconfirm",
  "--clean",
  "--onedir",
  "--hidden-import", "zoneinfo",
  "--hidden-import", "_zoneinfo",
  "--collect-submodules", "http",
  "--collect-submodules", "email",
  "--collect-submodules", "fastapi_app",
  "--collect-submodules", "app_new",
  "--collect-submodules", "playwright_worker",
  "--collect-submodules", "utils",
  "--collect-submodules", "crawlers",
  "--collect-all", "fastapi",
  "--collect-all", "starlette",
  "--collect-all", "uvicorn",
  "--collect-all", "celery",
  "--collect-all", "kombu",
  "--collect-all", "billiard",
  "--collect-all", "playwright",
  "--collect-all", "pydantic",
  "--collect-all", "pydantic_core",
  "--collect-all", "pydantic_settings",
  "--collect-all", "rich",
  "--paths", (Join-Path $root "syn_backend"),
  "--paths", (Join-Path $root "syn_backend\douyin_tiktok_api"),
  "--distpath", $dist,
  "--workpath", $build,
  "--specpath", $spec
)

$targets = @("backend", "celery-worker", "playwright-worker")
if ($env:PACKAGING_TARGETS) {
  $targets = $env:PACKAGING_TARGETS.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}

$entryScripts = @{
  "backend" = "$PSScriptRoot\backend_service.py"
  "celery-worker" = "$PSScriptRoot\celery_worker_service.py"
  "playwright-worker" = "$PSScriptRoot\playwright_worker_service.py"
}

foreach ($target in $targets) {
  if (-not $entryScripts.ContainsKey($target)) {
    Write-Error "Unsupported packaging target: $target"
    exit 1
  }
  & $python -m PyInstaller @common @runtimeDllArgs --name $target $entryScripts[$target]
  if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed for target: $target"
    exit $LASTEXITCODE
  }
}

Write-Host "Service executables built in dist/services"
