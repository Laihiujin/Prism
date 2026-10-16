$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'
$commandArgs = if ($args.Count) { @($args) } else { @('start') }
if ($commandArgs[0] -eq 'full') { $commandArgs[0] = 'start' }
$hash = [Security.Cryptography.SHA256]::Create()
$key = ([BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($root)))).Replace('-', '')
$hash.Dispose()
$mutex = New-Object Threading.Mutex($false, "Local\Prism.Start.$key")
if (-not $mutex.WaitOne(0)) { $mutex.Dispose(); exit 0 }
try {
    $node = & (Join-Path $PSScriptRoot 'ensure-node.ps1')
    $env:PATH = (Split-Path -Parent $node) + ';' + $env:PATH
    $launchArgs = @('"' + (Join-Path $PSScriptRoot 'runtime\ensure-runtime.cjs') + '"') + $commandArgs
    $process = Start-Process -FilePath $node -ArgumentList $launchArgs -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'startup.log') -RedirectStandardError (Join-Path $logDir 'startup-error.log')
    $null = $process.Handle
    $process.WaitForExit()
    $process.Refresh()
    if ($process.ExitCode -ne 0) { throw "Prism startup failed (exit $($process.ExitCode)); see startup-error.log" }
    if ($commandArgs[0] -in @('start', 'bootstrap') -and $commandArgs -notcontains '--check') {
        Start-Process 'http://localhost:3000'
    }
} catch {
    $_ | Out-String | Add-Content -LiteralPath (Join-Path $logDir 'startup-error.log') -Encoding UTF8
    exit 1
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
