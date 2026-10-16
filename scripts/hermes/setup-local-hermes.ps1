param([string]$Branch = "main", [string]$Version = "", [string]$WebUIVersion = "", [switch]$Force)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$node = & (Join-Path $root 'scripts\ensure-node.ps1')
$code = 'const r=require(process.argv[1]);r.ensureRuntime(process.argv[2],process.argv[3],{force:process.argv[4]==="true"}).catch(e=>{console.error(e.message);process.exitCode=1})'
$data = if ($env:PRISM_RUNTIME_DATA_DIR) { $env:PRISM_RUNTIME_DATA_DIR } else { Join-Path $root 'runtime-data' }
& $node -e $code (Join-Path $root 'scripts\runtime\ensure-runtime.cjs') $root $data $Force.IsPresent.ToString().ToLowerInvariant()
exit $LASTEXITCODE
