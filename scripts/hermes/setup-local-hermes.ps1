param(
    [string]$Branch = "main",
    [string]$WebUIVersion = "v0.51.91",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$hermesRoot = Join-Path $repoRoot "tools\hermes-agent"
$hermesHome = Join-Path $repoRoot "tools\hermes-home"
$synenvPath = Join-Path $repoRoot "synenv"
$pythonExe = Join-Path $synenvPath "Scripts\python.exe"
$runtimeStamp = Join-Path $synenvPath ".hermes-runtime-ready"
$hermesConfigPath = Join-Path $hermesRoot "hermes_cli\config.py"
$requiredExistingPaths = @(
    $pythonExe,
    $runtimeStamp,
    (Join-Path $hermesRoot "run_agent.py"),
    (Join-Path $repoRoot "tools\hermes-webui\server.py"),
    (Join-Path $repoRoot "tools\hermes-webui\static\index.html")
)

function Test-ContainsMergeMarkers {
    param(
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        return $false
    }

    return [bool](Select-String -Path $Path -Pattern '^(<<<<<<<|=======|>>>>>>>)' -Quiet)
}

if (-not $Force) {
    $hasPreparedRuntime = $true
    foreach ($requiredPath in $requiredExistingPaths) {
        if (-not (Test-Path $requiredPath)) {
            $hasPreparedRuntime = $false
            break
        }
    }

    if ($hasPreparedRuntime -and (Test-ContainsMergeMarkers -Path $hermesConfigPath)) {
        Write-Warning "Existing Hermes runtime contains unresolved merge markers. Forcing a clean refresh of tools\\hermes-agent."
        $hasPreparedRuntime = $false
        $Force = $true
    }

    if ($hasPreparedRuntime) {
        Write-Host "Hermes runtime already prepared. Reusing existing synenv, agent, and WebUI assets."
        Write-Host "Hermes source :" $hermesRoot
        Write-Host "Hermes python :" $pythonExe
        Write-Host "Hermes home   :" $hermesHome
        Write-Host "Hermes WebUI  :" (Join-Path $repoRoot "tools\hermes-webui")
        return
    }
}

if (-not (Test-Path $hermesRoot)) {
    git clone --depth 1 --branch $Branch https://github.com/NousResearch/hermes-agent.git $hermesRoot
} elseif ($Force) {
    git -C $hermesRoot fetch --depth 1 origin $Branch
    git -C $hermesRoot reset --hard "origin/$Branch"
    git -C $hermesRoot clean -fd
}

if (-not (Test-Path $pythonExe)) {
    python -m venv $synenvPath
}

if (-not (Test-Path $pythonExe)) {
    throw "Synapse Python runtime not found: $pythonExe"
}

& $pythonExe -m pip install --upgrade pip wheel "setuptools<82"
& $pythonExe -m pip uninstall -y openmanus browser-use langchain-openai

Push-Location $hermesRoot
try {
    $dependencyJson = @'
import json
import pathlib
import tomllib

pyproject = pathlib.Path("pyproject.toml")
data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
project = data.get("project", {})
deps = list(project.get("dependencies", []))
deps.extend((project.get("optional-dependencies") or {}).get("web", []))
print(json.dumps(deps, ensure_ascii=True))
'@ | & $pythonExe -
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to resolve Hermes dependencies from pyproject.toml"
    }
    $dependencyList = @($dependencyJson | ConvertFrom-Json)
    if ($dependencyList.Count -gt 0) {
        & $pythonExe -m pip install @dependencyList
    }
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Force -Path $hermesHome | Out-Null

$gitBashCandidates = @(
    (Join-Path $repoRoot "tools\git\bin\bash.exe"),
    (Join-Path $repoRoot "tools\git\usr\bin\bash.exe"),
    (Join-Path $env:ProgramFiles "Git\bin\bash.exe"),
    (Join-Path $env:ProgramFiles "Git\usr\bin\bash.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Git\bin\bash.exe")
)

$gitBashPath = $null
foreach ($candidate in $gitBashCandidates) {
    if ($candidate -and (Test-Path $candidate)) {
        $gitBashPath = $candidate
        break
    }
}

if ($gitBashPath) {
    $webPath = Join-Path $hermesRoot "web"
    if (Test-Path $webPath) {
        $nodeModulesPath = Join-Path $webPath "node_modules"
        if (Test-Path $nodeModulesPath) {
            Remove-Item -LiteralPath $nodeModulesPath -Recurse -Force
        }
        $webPathUnix = $webPath -replace '\\', '/'
        if ($webPathUnix -match '^([A-Za-z]):/(.*)$') {
            $drive = $matches[1].ToLower()
            $rest = $matches[2]
            $webPathUnix = "/$drive/$rest"
        }
        & $gitBashPath -lc "cd '$webPathUnix' && if [ -f package-lock.json ]; then npm ci; else npm install; fi && npm run build"
        if ($LASTEXITCODE -ne 0) {
            throw "Hermes dashboard web build failed with exit code $LASTEXITCODE."
        }
    }
}

$dashboardOverrideScript = Join-Path $PSScriptRoot "apply-hermes-dashboard-overrides.py"
$dashboardDist = Join-Path $hermesRoot "hermes_cli\web_dist"
$dashboardConfigExample = Join-Path $hermesRoot "cli-config.yaml.example"
if ((Test-Path $dashboardOverrideScript) -and (Test-Path $dashboardDist) -and (Test-Path $dashboardConfigExample)) {
    & $pythonExe $dashboardOverrideScript --repo-root $repoRoot --dashboard-dist $dashboardDist --config-example $dashboardConfigExample
    if ($LASTEXITCODE -ne 0) {
        throw "Dashboard override patch failed with exit code $LASTEXITCODE."
    }
}

$installHermesWebUiArgs = @(
    "-NoProfile"
    "-ExecutionPolicy"
    "Bypass"
    "-File"
    (Join-Path $PSScriptRoot "install-hermes-webui.ps1")
    "-Version"
    $WebUIVersion
)

if ($Force) {
    $installHermesWebUiArgs += "-Force"
}

& powershell @installHermesWebUiArgs
if ($LASTEXITCODE -ne 0) {
    throw "Hermes WebUI installer failed with exit code $LASTEXITCODE."
}

Set-Content -LiteralPath $runtimeStamp -Value (Get-Date).ToString("o") -Encoding ascii

$requiredHermesWebUiPaths = @(
    (Join-Path $repoRoot "tools\hermes-webui\server.py"),
    (Join-Path $repoRoot "tools\hermes-webui\static\index.html")
)

foreach ($requiredHermesWebUiPath in $requiredHermesWebUiPaths) {
    if (-not (Test-Path $requiredHermesWebUiPath)) {
        throw "Hermes WebUI installation is incomplete. Missing: $requiredHermesWebUiPath"
    }
}

Write-Host "Hermes source :" $hermesRoot
Write-Host "Hermes python :" $pythonExe
Write-Host "Hermes home   :" $hermesHome
Write-Host "Hermes WebUI  :" (Join-Path $repoRoot "tools\hermes-webui")
if ($gitBashPath) {
    Write-Host "Git Bash      :" $gitBashPath
} else {
    Write-Warning "Git Bash not found. Hermes terminal tools may be limited on native Windows."
}
Write-Host ""
Write-Host "Next:"
Write-Host "  1. Save model config in the SynapseAutomation Hermes settings page."
Write-Host "  2. Start Hermes WebUI from the same page, or run:"
Write-Host "     powershell -ExecutionPolicy Bypass -File `"$repoRoot\scripts\hermes\hermes.ps1`" --version"
