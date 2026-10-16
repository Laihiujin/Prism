$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'
$commandArgs = if ($args.Count) { @($args) } else { @('start') }
$hash = [Security.Cryptography.SHA256]::Create()
$key = ([BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($root)))).Replace('-', '')
$hash.Dispose()
$mutex = New-Object Threading.Mutex($false, "Local\Prism.Start.$key")
if (-not $mutex.WaitOne(0)) { $mutex.Dispose(); exit 0 }
try {
    $python = @(
        (Join-Path $root 'prismenv\python.exe'),
        (Join-Path $root '.tools\python\python.exe'),
        (Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
    if (-not $python) { throw 'Python bootstrap interpreter missing. Run deploy.cmd once to provision micromamba.' }
    $launchArgs = @('"' + (Join-Path $root 'bootstrap.py') + '"') + $commandArgs
    $process = Start-Process -FilePath $python -ArgumentList $launchArgs -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'startup.log') -RedirectStandardError (Join-Path $logDir 'startup-error.log')
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
