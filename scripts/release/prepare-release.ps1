$ErrorActionPreference = "Stop"

param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

function Remove-IfExists {
    param(
        [string]$Path,
        [switch]$RecreateDirectory
    )

    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
    }

    if ($RecreateDirectory) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Remove-Files {
    param(
        [string]$Directory,
        [string[]]$Patterns
    )

    if (-not (Test-Path -LiteralPath $Directory)) {
        return
    }

    foreach ($pattern in $Patterns) {
        Get-ChildItem -LiteralPath $Directory -Filter $pattern -File -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

$resolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
Write-Host "[prepare-release] Project root: $resolvedRoot"

$targetsToReset = @(
    @{ Path = (Join-Path $resolvedRoot "logs"); Recreate = $true },
    @{ Path = (Join-Path $resolvedRoot "syn_backend\logs"); Recreate = $true },
    @{ Path = (Join-Path $resolvedRoot "syn_backend\data\cookies"); Recreate = $false },
    @{ Path = (Join-Path $resolvedRoot "syn_backend\cookiesFile"); Recreate = $false },
    @{ Path = (Join-Path $resolvedRoot "syn_backend\fingerprints"); Recreate = $false },
    @{ Path = (Join-Path $resolvedRoot "syn_backend\browser_profiles"); Recreate = $false },
    @{ Path = (Join-Path $resolvedRoot "config\cookiesFile"); Recreate = $false },
    @{ Path = (Join-Path $resolvedRoot "config\browser_profiles"); Recreate = $false },
    @{ Path = (Join-Path $resolvedRoot "desktop-electron\dist-build"); Recreate = $false },
    @{ Path = (Join-Path $resolvedRoot "desktop-electron\dist-out"); Recreate = $false },
    @{ Path = (Join-Path $resolvedRoot "dist"); Recreate = $false },
    @{ Path = (Join-Path $resolvedRoot "dist-out"); Recreate = $false }
)

foreach ($target in $targetsToReset) {
    Remove-IfExists -Path $target.Path -RecreateDirectory:$target.Recreate
}

Remove-Files -Directory (Join-Path $resolvedRoot "syn_backend\db") -Patterns @("*.db", "*.db-*", "*.sqlite", "*.sqlite-*", "frontend_accounts_snapshot.json")
Remove-Files -Directory (Join-Path $resolvedRoot "desktop-electron") -Patterns @("*.rdb", "*.log")

Write-Host "[prepare-release] Release workspace sanitized."
