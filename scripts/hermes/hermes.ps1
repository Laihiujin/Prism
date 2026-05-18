param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"

$appRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$hermesRoot = Join-Path $appRoot "tools\hermes-agent"
$hermesHome = if ($env:SYNAPSE_HERMES_HOME) {
    $env:SYNAPSE_HERMES_HOME
} else {
    Join-Path $appRoot "tools\hermes-home"
}
$pythonExe = if ($env:SYNAPSE_HERMES_PYTHON -and (Test-Path $env:SYNAPSE_HERMES_PYTHON)) {
    $env:SYNAPSE_HERMES_PYTHON
} else {
    Join-Path $appRoot "synenv\Scripts\python.exe"
}

if (-not (Test-Path $pythonExe)) {
    throw "Hermes is not installed yet. Run scripts\hermes\setup-local-hermes.ps1 first."
}

New-Item -ItemType Directory -Force -Path $hermesHome | Out-Null

$env:HERMES_HOME = $hermesHome
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:HERMES_WEBUI_AGENT_DIR = $hermesRoot
$existingPythonPath = @()
foreach ($entry in ($env:PYTHONPATH -split [IO.Path]::PathSeparator)) {
    if ($entry -and ($entry -ne $hermesRoot)) {
        $existingPythonPath += $entry
    }
}
$env:PYTHONPATH = (@($hermesRoot) + $existingPythonPath) -join [IO.Path]::PathSeparator

$gitBashCandidates = @(
    (Join-Path $appRoot "tools\git\bin\bash.exe"),
    (Join-Path $appRoot "tools\git\usr\bin\bash.exe"),
    (Join-Path $env:ProgramFiles "Git\bin\bash.exe"),
    (Join-Path $env:ProgramFiles "Git\usr\bin\bash.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Git\bin\bash.exe")
)

foreach ($candidate in $gitBashCandidates) {
    if ($candidate -and (Test-Path $candidate)) {
        $env:HERMES_GIT_BASH_PATH = $candidate
        break
    }
}

Push-Location $hermesRoot
try {
    $escapedHermesRoot = $hermesRoot.Replace('\', '\\')
    $bootstrap = "import runpy, sys; sys.path.insert(0, r'$escapedHermesRoot'); runpy.run_module('hermes_cli.main', run_name='__main__')"
    & $pythonExe -c $bootstrap @Args
} finally {
    Pop-Location
}
