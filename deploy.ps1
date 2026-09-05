# Prism 本地一键部署入口（Windows PowerShell 引导器）。
# 用途：在「什么都没装」的 Windows 上，仅凭 PowerShell 就能把部署器跑起来并打开部署 Web UI。
#
# 用法（在项目根目录，任何一处 cmd / PowerShell）：
#   .\deploy.ps1              # 启动部署 Web UI（默认 127.0.0.1:8440）
#   .\deploy.ps1 full         # 无界面一键部署（plan->install-tools->bootstrap->start）
#   .\deploy.ps1 plan|status|start|stop|bootstrap|install-tools
#
# 说明：Windows 上仓库内嵌的 micromamba 是 macOS 二进制，不能直接用来跑部署器，
#       所以这里在没有系统 Python 时自动下载一份「便携 cpPython」(python-build-standalone)
#       到 .tools\python，再调用 deploy\deploy.py。

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Tools = Join-Path $Root ".tools"
$ToolsPy = Join-Path $Tools "python"

function Log($m){ Write-Host "[deploy] $m" }

function Test-Py($exe){
  if(-not (Test-Path $exe)){ return $false }
  try{ & $exe -c "import sys;print(sys.version_info[0],sys.version_info[1])" 2>$null | Out-Null; return $true }catch{ return $false }
}

# --- 1) 解析 Python：优先 py -3 / python，其次便携下载 ---
$Py = $null
foreach($cand in @("py -3","py","python","python3")){
  $parts = $cand -split " "
  try{ $v = & $parts[0] $parts[1..($parts.Count-1)] -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null; if($LASTEXITCODE -eq 0 -and $v){ $Py=$cand; break } }catch{}
}
if(-not $Py -and (Test-Py (Join-Path $ToolsPy "python.exe"))){ $Py = (Join-Path $ToolsPy "python.exe") }

if(-not $Py){
  Log "未找到系统 Python。下载便携 Python (python-build-standalone) 到 $ToolsPy ..."
  New-Item -ItemType Directory -Force -Path $Tools | Out-Null
  try{
    $rel = Invoke-RestMethod "https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest" -Headers @{ "User-Agent"="Prism-Deployer/1.0" }
    $asset = $rel.assets | Where-Object { $_.name -match "install_only\.tar\.gz$" -and $_.name -match "x86_64-pc-windows-msvc" } | Select-Object -First 1
    $url = $asset.browser_download_url
    Log "  下载: $url"
  }catch{
    $url = "https://github.com/astral-sh/python-build-standalone/releases/download/20241016/cpython-3.12.7+20241016-x86_64-pc-windows-msvc-install_only.tar.gz"
    Log "  API 失败，回退固定版本: $url"
  }
  $arc = Join-Path $Tools "python.tar.gz"
  Invoke-WebRequest -Uri $url -OutFile $arc -UseBasicParsing
  New-Item -ItemType Directory -Force -Path $ToolsPy | Out-Null
  tar -xzf $arc -C $ToolsPy
  Remove-Item $arc
  # 动态解析 python.exe（布局可能因版本而异）
  $exe = Get-ChildItem $ToolsPy -Recurse -Filter "python.exe" | Where-Object { Test-Py $_.FullName } | Select-Object -First 1
  if($exe){
    $Py = $exe.FullName
    $Scripts = Join-Path (Split-Path $exe.FullName) "Scripts"
    if(Test-Path $Scripts){ $env:Path = "$Scripts;" + $env:Path }
    Log "  便携 Python 就绪: $Py"
  }else{
    Log "[ERROR] 便携 Python 未生成可用 python.exe。请手动安装 Python 3.11+ 后重试，或改跑 start.bat。"
    exit 1
  }
}else{
  Log "使用 Python: $Py"
}

# 把 .tools\node 等也提前放入 PATH（若已存在）
$ToolsNode = Join-Path $Tools "node"
$ToolsRedis = Join-Path $Tools "redis"
if(Test-Path (Join-Path $ToolsNode "node.exe")){ $env:Path = "$ToolsNode;" + $env:Path }
if(Test-Path (Join-Path $ToolsRedis "redis-server.exe")){ $env:Path = "$ToolsRedis;" + $env:Path }

# --- 2) 转发到 bootstrap.py（PowerShell 已自给 Python，无需预装）---
$Cmd = if($args.Count -gt 0){ $args[0] } else { "bootstrap" }   # 不带参数 = 完整部署(venv 路径，Windows 安全)
$Extra = if($args.Count -gt 1){ $args[1..($args.Count-1)] } else { @() }
# check / plan 是只读探测，转到 bootstrap.py --check
if($Cmd -eq "check" -or $Cmd -eq "plan"){ $Cmd = "--check"; $Extra = @() }
$script = "bootstrap.py"
$PyInvoke = @($Py) + @($Root, $script, $Cmd) + $Extra
if($Py -match "^py"){ $PyInvoke = @("py","-3") + @($Root, $script, $Cmd) + $Extra }
elseif($Py -match "^python" -and $Py -notmatch "\\"){ $PyInvoke = @("python") + @($Root, $script, $Cmd) + $Extra }
Log "运行: $($PyInvoke -join ' ')"
& $PyInvoke[0] $PyInvoke[1..($PyInvoke.Count-1)]
exit $LASTEXITCODE
