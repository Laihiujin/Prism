$ErrorActionPreference = 'Stop'
$node = Get-Command node.exe -ErrorAction SilentlyContinue
if ($node) {
    $major = & $node.Source -p 'parseInt(process.versions.node)'
    if ([int]$major -ge 22) { return $node.Source }
}
$data = if ($env:PRISM_RUNTIME_DATA_DIR) { $env:PRISM_RUNTIME_DATA_DIR } else { Join-Path (Split-Path -Parent $PSScriptRoot) 'runtime-data' }
$nodeRoot = Join-Path $data 'node'
$existing = Get-ChildItem -LiteralPath $nodeRoot -Filter node.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if ($existing) { return $existing.FullName }
New-Item -ItemType Directory -Force -Path $nodeRoot | Out-Null
$bases = @('https://nodejs.org/dist/latest-v22.x', 'https://npmmirror.com/mirrors/node/latest-v22.x')
foreach ($base in $bases) {
    try {
        $sums = (Invoke-WebRequest -UseBasicParsing -Uri "$base/SHASUMS256.txt" -TimeoutSec 30).Content
        if ($sums -is [byte[]]) { $sums = [Text.Encoding]::UTF8.GetString($sums) }
        $entry = ([string]$sums -split "`n") | Where-Object { $_ -match 'node-v[0-9.]+-win-x64\.zip$' } | Select-Object -First 1
        if (-not $entry) { throw 'Node archive not found in release checksums' }
        $parts = $entry.Trim() -split '\s+'
        $archive = Join-Path $nodeRoot 'download.zip'
        Invoke-WebRequest -UseBasicParsing -Uri "$base/$($parts[1])" -OutFile $archive -TimeoutSec 180
        if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $parts[0]) { throw 'Node checksum mismatch' }
        Expand-Archive -LiteralPath $archive -DestinationPath $nodeRoot -Force
        Remove-Item -LiteralPath $archive -Force
        return (Get-ChildItem -LiteralPath $nodeRoot -Filter node.exe -Recurse | Select-Object -First 1).FullName
    } catch { Write-Warning "Node source unavailable: $base" }
}
throw 'All Node download sources failed; see startup-error.log'
