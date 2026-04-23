param(
  [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..\..").Path,
  [string]$Version = "",
  [switch]$Clean
)

$ErrorActionPreference = "Stop"

$repo = "Hibbiki/chromium-win64"
$headers = @{ "User-Agent" = "SynapseAutomation-build" }
$releaseUrl = "https://api.github.com/repos/$repo/releases/latest"

if ($Version) {
  $releaseUrl = "https://api.github.com/repos/$repo/releases/tags/$Version"
}

$release = Invoke-RestMethod -Uri $releaseUrl -Headers $headers
$asset = $release.assets | Where-Object { $_.name -eq "chrome.7z" } | Select-Object -First 1
if (-not $asset) {
  throw "Hibbiki release $($release.tag_name) does not contain chrome.7z"
}

$browserVersion = $release.tag_name -replace '^v', ''
$browserVersion = ($browserVersion -split '-')[0]
$targetRoot = Join-Path $ProjectRoot "browsers\chromium"
$targetDir = Join-Path $targetRoot "hibbiki-$browserVersion"
$chromeExe = Join-Path $targetDir "Chrome-bin\chrome.exe"

if ((Test-Path $chromeExe) -and -not $Clean) {
  Write-Host "Hibbiki Chromium already installed: $chromeExe"
  exit 0
}

$sevenZipCandidates = @(
  (Join-Path $ProjectRoot "desktop-electron\node_modules\7zip-bin\win\x64\7za.exe"),
  (Join-Path $ProjectRoot "node_modules\7zip-bin\win\x64\7za.exe"),
  "7z.exe",
  "7za.exe"
)

$sevenZip = $null
foreach ($candidate in $sevenZipCandidates) {
  if ($candidate -like "*.exe" -and (Test-Path $candidate)) {
    $sevenZip = $candidate
    break
  }
  try {
    $cmd = Get-Command $candidate -ErrorAction Stop
    $sevenZip = $cmd.Source
    break
  } catch {
    continue
  }
}

if (-not $sevenZip) {
  throw "7-Zip executable not found. Run npm --prefix desktop-electron ci first, or install 7z/7za."
}

$tmpDir = Join-Path $ProjectRoot ".tmp-hibbiki"
$archive = Join-Path $tmpDir "chrome.7z"
New-Item -ItemType Directory -Force -Path $tmpDir, $targetRoot | Out-Null

Write-Host "Downloading Hibbiki Chromium $($release.tag_name) from $($asset.browser_download_url)"
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $archive -Headers $headers

if ($Clean -and (Test-Path $targetDir)) {
  Remove-Item -LiteralPath $targetDir -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
& $sevenZip x $archive "-o$targetDir" -y | Write-Host
if ($LASTEXITCODE -ne 0) {
  throw "Failed to extract $archive"
}

if (-not (Test-Path $chromeExe)) {
  throw "Missing Hibbiki Chromium executable after extraction: $chromeExe"
}

Write-Host "Installed Hibbiki Chromium: $chromeExe"
