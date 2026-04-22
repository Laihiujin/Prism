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

$common = @(
  "--noconfirm",
  "--clean",
  "--onefile",
  "--hidden-import", "zoneinfo",
  "--hidden-import", "_zoneinfo",
  "--collect-submodules", "http",
  "--collect-submodules", "email",
  "--paths", (Join-Path $root "syn_backend"),
  "--distpath", $dist,
  "--workpath", $build,
  "--specpath", $spec
)

& $python -m PyInstaller @common --name backend "$PSScriptRoot\backend_service.py"
& $python -m PyInstaller @common --name celery-worker "$PSScriptRoot\celery_worker_service.py"
& $python -m PyInstaller @common --name playwright-worker "$PSScriptRoot\playwright_worker_service.py"
& $python -m PyInstaller @common --name start_all_services_synenv "$PSScriptRoot\start_all_services_synenv.py"

Write-Host "Service executables built in dist/services"
