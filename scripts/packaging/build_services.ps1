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
  "--paths", (Join-Path $root "syn_backend"),
  "--paths", (Join-Path $root "syn_backend\douyin_tiktok_api"),
  "--distpath", $dist,
  "--workpath", $build,
  "--specpath", $spec
)

$backendExcludes = @(
  "--exclude-module", "patchright",
  "--exclude-module", "patchright.async_api",
  "--exclude-module", "patchright.sync_api",
  "--exclude-module", "playwright",
  "--exclude-module", "playwright.async_api",
  "--exclude-module", "playwright.sync_api",
  "--exclude-module", "playwright._impl",
  "--exclude-module", "stream_gears",
  "--exclude-module", "selenium",
  "--exclude-module", "fastapi_app.api.v1.auth.services",
  "--exclude-module", "myUtils.auth",
  "--exclude-module", "myUtils.platform_explorer",
  "--exclude-module", "myUtils.maintenance"
)

$targetOptions = @{
  "backend" = @(
    "--hidden-import", "fastapi.middleware",
    "--hidden-import", "fastapi.middleware.cors",
    "--hidden-import", "celery.fixups",
    "--hidden-import", "playwright_worker.client",
    "--collect-submodules", "http",
    "--collect-submodules", "email",
    "--collect-submodules", "fastapi",
    "--collect-submodules", "starlette",
    "--collect-submodules", "celery",
    "--collect-submodules", "kombu",
    "--collect-submodules", "billiard",
    "--collect-submodules", "vine",
    "--collect-submodules", "amqp",
    "--collect-all", "fastapi",
    "--collect-all", "starlette",
    "--collect-all", "uvicorn",
    "--collect-all", "celery",
    "--collect-all", "kombu",
    "--collect-all", "billiard",
    "--collect-all", "pydantic",
    "--collect-all", "pydantic_core",
    "--collect-all", "pydantic_settings",
    "--collect-all", "rich"
  )
  "celery-worker" = @(
    "--hidden-import", "celery.fixups",
    "--collect-submodules", "celery",
    "--collect-submodules", "kombu",
    "--collect-submodules", "billiard",
    "--collect-submodules", "vine",
    "--collect-submodules", "amqp",
    "--collect-submodules", "fastapi_app.tasks",
    "--collect-all", "celery",
    "--collect-all", "kombu",
    "--collect-all", "billiard",
    "--collect-all", "vine",
    "--collect-all", "amqp",
    "--collect-all", "pydantic",
    "--collect-all", "pydantic_core"
  )
  "playwright-worker" = @(
    "--hidden-import", "fastapi.middleware",
    "--hidden-import", "fastapi.middleware.cors",
    "--collect-submodules", "http",
    "--collect-submodules", "email",
    "--collect-submodules", "fastapi",
    "--collect-submodules", "starlette",
    "--collect-submodules", "fastapi_app",
    "--collect-submodules", "app_new",
    "--collect-submodules", "playwright_worker",
    "--collect-submodules", "utils",
    "--collect-submodules", "crawlers",
    "--collect-all", "fastapi",
    "--collect-all", "starlette",
    "--collect-all", "uvicorn",
    "--collect-all", "patchright",
    "--collect-all", "playwright",
    "--collect-all", "pydantic",
    "--collect-all", "pydantic_core",
    "--collect-all", "pydantic_settings",
    "--collect-all", "rich"
  )
}

$targets = @("backend", "celery-worker", "playwright-worker")
if ($env:PACKAGING_TARGETS) {
  $targets = $env:PACKAGING_TARGETS.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}

$entryScripts = @{
  "backend" = "$PSScriptRoot\backend_service.py"
  "celery-worker" = "$PSScriptRoot\celery_worker_service.py"
  "playwright-worker" = "$PSScriptRoot\playwright_worker_service.py"
}

function Find-PackagedDriverNode {
  param(
    [string]$TargetDir,
    [string]$RuntimeName
  )

  $match = Get-PackagedDriverNodes -TargetDir $TargetDir -RuntimeName $RuntimeName |
    Select-Object -First 1

  if ($match) {
    return $match
  }

  return $null
}

function Get-PackagedDriverNodes {
  param(
    [string]$TargetDir,
    [string]$RuntimeName
  )

  $directPath = Join-Path $TargetDir "_internal\$RuntimeName\driver\node.exe"
  $matches = @()

  if (Test-Path $directPath) {
    $matches += (Resolve-Path $directPath).Path
  }

  $escapedRuntimeName = [regex]::Escape($RuntimeName)
  $matches += Get-ChildItem -Path $TargetDir -Filter node.exe -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match "\\$escapedRuntimeName\\driver\\node\.exe$" } |
    Select-Object -ExpandProperty FullName

  return @($matches | Where-Object { $_ } | Select-Object -Unique)
}

function Get-PatchrightDriverNodeSource {
  if ($script:PatchrightDriverNodeSource) {
    return $script:PatchrightDriverNodeSource
  }

  $patchrightNodeOutput = & $python -c @"
import pathlib
import sys

candidates = []
try:
    import patchright

    pkg_dir = pathlib.Path(patchright.__file__).resolve().parent
    candidates.append(pkg_dir / "driver" / ("node.exe" if sys.platform == "win32" else "node"))

    try:
        from patchright._impl._driver import compute_driver_executable

        driver_path, _ = compute_driver_executable()
        candidates.insert(0, pathlib.Path(driver_path))
    except Exception:
        pass
except Exception:
    pass

for candidate in candidates:
    if candidate.exists():
        print(candidate)
        break
"@

  if ($LASTEXITCODE -eq 0 -and $null -ne $patchrightNodeOutput) {
    $patchrightNode = (@($patchrightNodeOutput) -join [Environment]::NewLine).Trim()
    if (-not [string]::IsNullOrWhiteSpace($patchrightNode) -and (Test-Path $patchrightNode)) {
      $script:PatchrightDriverNodeSource = $patchrightNode
      return $script:PatchrightDriverNodeSource
    }
  }

  $fallbackCandidates = @()
  if ($env:PACKAGED_DRIVER_NODE_SOURCE) {
    $fallbackCandidates += $env:PACKAGED_DRIVER_NODE_SOURCE
  }

  try {
    $resolvedNode = Get-Command node -ErrorAction Stop
    if ($resolvedNode.Source) {
      $fallbackCandidates += $resolvedNode.Source
    }
  } catch {
  }

  foreach ($candidate in ($fallbackCandidates | Where-Object { $_ } | Select-Object -Unique)) {
    if (Test-Path $candidate) {
      $script:PatchrightDriverNodeSource = (Resolve-Path $candidate).Path
      return $script:PatchrightDriverNodeSource
    }
  }

  return $null
}

function Prune-PlaywrightDriverNode {
  param([string]$TargetName)

  $targetDir = Join-Path $dist $TargetName
  if (-not (Test-Path $targetDir)) {
    return
  }

  $patchrightNode = Find-PackagedDriverNode -TargetDir $targetDir -RuntimeName "patchright"
  $playwrightNodes = @(Get-PackagedDriverNodes -TargetDir $targetDir -RuntimeName "playwright")
  $playwrightNode = $playwrightNodes | Select-Object -First 1
  $expectedPatchrightNode = Join-Path $targetDir "_internal\patchright\driver\node.exe"

  if (-not $patchrightNode) {
    if ($TargetName -eq "playwright-worker") {
      $sourcePatchrightNode = Get-PatchrightDriverNodeSource
      if ($sourcePatchrightNode) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $expectedPatchrightNode) | Out-Null
        Copy-Item -LiteralPath $sourcePatchrightNode -Destination $expectedPatchrightNode -Force
        Write-Host "Injected patchright driver node.exe into packaged $TargetName from $sourcePatchrightNode"
      } elseif ($playwrightNode) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $expectedPatchrightNode) | Out-Null
        Copy-Item -LiteralPath $playwrightNode -Destination $expectedPatchrightNode -Force
        Write-Host "Rebased packaged Playwright driver node.exe into patchright runtime for $TargetName from $playwrightNode"
      }

      $patchrightNode = Find-PackagedDriverNode -TargetDir $targetDir -RuntimeName "patchright"
      if (-not $patchrightNode) {
        throw "Missing patchright driver node.exe in packaged $TargetName after injection attempt."
      }
    }
    return
  }

  if ($patchrightNode -ne $expectedPatchrightNode) {
    $expectedPatchrightDir = Split-Path $expectedPatchrightNode -Parent
    if (-not (Test-Path $expectedPatchrightDir)) {
      New-Item -ItemType Directory -Force -Path $expectedPatchrightDir | Out-Null
    }
    Move-Item -LiteralPath $patchrightNode -Destination $expectedPatchrightNode -Force
    Write-Host "Rebased patchright driver node.exe to $expectedPatchrightNode"
    $patchrightNode = $expectedPatchrightNode
  }

  foreach ($candidate in $playwrightNodes) {
    if ($candidate -and (Test-Path $candidate)) {
      Remove-Item -LiteralPath $candidate -Force
      Write-Host "Pruned duplicate Playwright driver node.exe from $candidate"
    }
  }

  $remainingPlaywrightNodes = @(Get-PackagedDriverNodes -TargetDir $targetDir -RuntimeName "playwright")
  if ($remainingPlaywrightNodes.Count -gt 0) {
    $remainingList = $remainingPlaywrightNodes -join ", "
    throw "Duplicate Playwright driver node.exe still packaged in $TargetName after pruning: $remainingList"
  }

  if ($TargetName -eq "playwright-worker") {
    $verifiedPatchrightNode = Find-PackagedDriverNode -TargetDir $targetDir -RuntimeName "patchright"
    if (-not $verifiedPatchrightNode) {
      throw "Missing patchright driver node.exe in packaged $TargetName after pruning."
    }
  }
}

foreach ($target in $targets) {
  if (-not $entryScripts.ContainsKey($target)) {
    Write-Error "Unsupported packaging target: $target"
    exit 1
  }
  $targetArgs = $targetOptions[$target]
  if (-not $targetArgs) {
    Write-Error "Missing PyInstaller option set for target: $target"
    exit 1
  }
  $extraArgs = @()
  if ($target -eq "backend") {
    $extraArgs += $backendExcludes
  }
  & $python -m PyInstaller @common @targetArgs @extraArgs @runtimeDllArgs --name $target $entryScripts[$target]
  if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed for target: $target"
    exit $LASTEXITCODE
  }
  Prune-PlaywrightDriverNode -TargetName $target
}

Write-Host "Service executables built in dist/services"
