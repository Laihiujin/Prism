param(
    [string]$Message,
    [switch]$All,
    [switch]$Push,
    [string]$Remote = "origin",
    [string]$Branch = ""
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    $root = git rev-parse --show-toplevel 2>$null
    if (-not $root) {
        throw "Not inside a git repo."
    }
    return $root.Trim()
}

function Get-CurrentBranch {
    $branch = git rev-parse --abbrev-ref HEAD 2>$null
    return $branch.Trim()
}

$repoRoot = Get-RepoRoot
Set-Location $repoRoot

if (-not $Message) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $Message = "chore: quick save $timestamp"
}

if ($All) {
    git add -A
} else {
    # Default: only tracked changes, avoid accidental large untracked files.
    git add -u
}

git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "No staged changes to commit."
    exit 0
}

git commit -m $Message

if ($Push) {
    if (-not $Branch) {
        $Branch = Get-CurrentBranch
    }
    git push $Remote $Branch
}
