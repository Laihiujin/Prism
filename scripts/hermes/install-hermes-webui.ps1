param(
    [string]$Version = "v0.51.50",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$hermesRoot = Join-Path $repoRoot "tools\hermes-agent"
$hermesWebUiRoot = Join-Path $repoRoot "tools\hermes-webui"
$hermesHome = Join-Path $repoRoot "tools\hermes-home"
$brandingAssetsRoot = Join-Path $PSScriptRoot "assets"
$pythonExe = Join-Path $repoRoot "synenv\Scripts\python.exe"
$downloadRoot = Join-Path $repoRoot "tmp\hermes-webui-install"
$zipPath = Join-Path $downloadRoot "$Version.zip"
$extractRoot = Join-Path $downloadRoot "extract"
$downloadUrl = "https://codeload.github.com/nesquena/hermes-webui/zip/refs/tags/$Version"
$webUiBuildVersion = "$Version-synapse-black2"

function Replace-First {
    param(
        [string]$InputText,
        [string]$Pattern,
        [string]$Replacement,
        [string]$Label
    )

    $regex = [System.Text.RegularExpressions.Regex]::new(
        $Pattern,
        [System.Text.RegularExpressions.RegexOptions]::Singleline
    )

    if (-not $regex.IsMatch($InputText)) {
        throw "Unable to patch Hermes WebUI $Label."
    }

    return $regex.Replace($InputText, $Replacement, 1)
}

function Convert-FileToDataUri {
    param(
        [string]$Path,
        [string]$MimeType
    )

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    return "data:$MimeType;base64," + [Convert]::ToBase64String($bytes)
}

function Stop-HermesWebUiProcesses {
    param(
        [string]$WebUiRoot
    )

    $normalizedRoot = [System.IO.Path]::GetFullPath($WebUiRoot)
    $candidates = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $commandLine = $_.CommandLine
        if (-not $commandLine) {
            return $false
        }

        $normalizedCommandLine = $commandLine.Replace('/', '\')
        return (
            $normalizedCommandLine -like "*$($normalizedRoot.Replace('/', '\'))*" -or
            $normalizedCommandLine -like "*hermes-webui\\server.py*" -or
            $normalizedCommandLine -like "*hermes-webui*"
        )
    }

    foreach ($candidate in $candidates) {
        if ($candidate.ProcessId -eq $PID) {
            continue
        }

        try {
            Stop-Process -Id $candidate.ProcessId -Force -ErrorAction Stop
        } catch {
            Write-Warning "Failed to stop Hermes WebUI process $($candidate.ProcessId): $($_.Exception.Message)"
        }
    }

    if ($candidates) {
        Start-Sleep -Milliseconds 800
    }
}

function Apply-SynapseHermesBranding {
    param(
        [string]$WebUiRoot,
        [string]$AssetsRoot,
        [string]$HermesHomePath
    )

    $blackLogoSource = Join-Path $AssetsRoot "hermes-agent-logo.svg"
    $whiteLogoSource = Join-Path $AssetsRoot "hermes.svg"
    $legacyWhiteLogoSource = Join-Path $AssetsRoot "hermes-agent-logo-white.svg"
    $brandAssetNames = @(
        "apple-touch-icon.png",
        "favicon-32.png",
        "favicon-192.png",
        "favicon-512.png",
        "favicon-512.svg",
        "favicon.ico",
        "favicon.svg",
        "hermes.svg"
    )
    if (-not (Test-Path $whiteLogoSource) -and (Test-Path $legacyWhiteLogoSource)) {
        $whiteLogoSource = $legacyWhiteLogoSource
    }
    if (-not (Test-Path $blackLogoSource) -or -not (Test-Path $whiteLogoSource)) {
        throw "Missing Hermes branding assets under $AssetsRoot"
    }
    $whiteLogoDataUri = Convert-FileToDataUri -Path $whiteLogoSource -MimeType "image/svg+xml"

    $staticRoot = Join-Path $WebUiRoot "static"
    Copy-Item -LiteralPath $blackLogoSource -Destination (Join-Path $staticRoot "hermes-agent-logo.svg") -Force
    Copy-Item -LiteralPath $whiteLogoSource -Destination (Join-Path $staticRoot "hermes.svg") -Force
    Copy-Item -LiteralPath $whiteLogoSource -Destination (Join-Path $staticRoot "hermes-agent-logo-white.svg") -Force
    foreach ($assetName in $brandAssetNames) {
        $assetSource = Join-Path $AssetsRoot $assetName
        if (Test-Path $assetSource) {
            Copy-Item -LiteralPath $assetSource -Destination (Join-Path $staticRoot $assetName) -Force
        }
    }

    $indexPath = Join-Path $staticRoot "index.html"
    $indexHtml = Get-Content -LiteralPath $indexPath -Raw
    $indexHtml = $indexHtml.Replace('<html lang="en">', '<html lang="zh-CN">')
    $baseHrefScript = '<script>(function(){var path=location.pathname,marker=''/session/'',i=path.indexOf(marker),p;i>=0?p=(path.slice(0,i+1)||''/''):p=(path.endsWith(''/'')?path:(path.replace(/\/[^\/]*$/,''/'')||''/''));document.write(''<base href="''+location.origin+p+''">'');})()</script>'
    $fileModeGuard = @'
<script>(function(){if(location.protocol!=='file:')return;document.documentElement.innerHTML='';document.write('<style>body{margin:0;background:#000;color:#f5f5f5;font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;display:grid;place-items:center;min-height:100vh} .box{width:min(560px,calc(100vw - 48px));padding:28px;border:1px solid rgba(255,255,255,.12);border-radius:18px;background:#0b0b0b;box-shadow:0 24px 60px rgba(0,0,0,.45)} h1{margin:0 0 10px;font-size:22px} p{margin:0 0 10px;color:#a3a3a3} code{color:#fff} a{color:#fff;text-decoration:none;border:1px solid rgba(255,255,255,.14);background:#161616;padding:10px 14px;border-radius:12px;display:inline-block;margin-top:8px}</style><div class="box"><h1>Do not open static/index.html directly</h1><p>This page must be served by Hermes WebUI. In <code>file://</code> mode, assets, API calls, and app state will break.</p><p>Open <code>http://127.0.0.1:9131/</code> or use the app entry at <code>/ai-agent</code>.</p><a href="http://127.0.0.1:9131/">Open Hermes WebUI</a></div>');throw new Error('Hermes WebUI static index does not support file:// mode.');})()</script>
'@
    if ($indexHtml -notmatch 'Hermes WebUI static index does not support file:// mode') {
        $indexHtml = $indexHtml.Replace($baseHrefScript, "$baseHrefScript`n$fileModeGuard")
    }
    $logoBootScript = "<script>(function(){var src='$whiteLogoDataUri';window.__HERMES_LOGO_WHITE_DATA_URI=src;document.addEventListener('DOMContentLoaded',function(){document.querySelectorAll('[data-hermes-logo-white]').forEach(function(el){el.setAttribute('src',src);});},{once:true});})()</script>"
    $indexHtml = Replace-First $indexHtml '<script>\(function\(\)\{var themes=.*?</script>' "<script>(function(){var theme='dark',skin='mono';localStorage.setItem('hermes-theme',theme);localStorage.setItem('hermes-skin',skin);if(!localStorage.getItem('hermes-lang'))localStorage.setItem('hermes-lang','zh');document.documentElement.lang='zh-CN';document.documentElement.classList.add('dark');document.documentElement.dataset.skin=skin;})()</script>" "theme bootstrap"
    $indexHtml = $indexHtml.Replace('<meta name="theme-color" content="#0D0D1A" media="(prefers-color-scheme: dark)">', '<meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)">')
    $indexHtml = $indexHtml.Replace('<meta name="theme-color" id="hermes-theme-color" content="#0D0D1A">', '<meta name="theme-color" id="hermes-theme-color" content="#000000">')
    $indexHtml = Replace-First $indexHtml '<script>\(function\(\)\{try\{var t=localStorage\.getItem\(''hermes-theme''\)\|\|''dark'';.*?</script>' "<script>(function(){try{var c='#000000';document.querySelectorAll('meta[name=""theme-color""]').forEach(function(m){m.setAttribute('content',c);m.removeAttribute('media');});}catch(e){}})()</script>" "theme color bootstrap"
    if ($indexHtml -notmatch '__HERMES_LOGO_WHITE_DATA_URI') {
        $indexHtml = $indexHtml.Replace('<script>(function(){try{var c=''#000000'';document.querySelectorAll(''meta[name=""theme-color""]'').forEach(function(m){m.setAttribute(''content'',c);m.removeAttribute(''media'');});}catch(e){}})()</script>', "<script>(function(){try{var c='#000000';document.querySelectorAll('meta[name=""theme-color""]').forEach(function(m){m.setAttribute('content',c);m.removeAttribute('media');});}catch(e){}})()</script>`n$logoBootScript")
    }
    $indexHtml = Replace-First $indexHtml '<span class="app-titlebar-icon" aria-hidden="true">.*?</span>' '<span class="app-titlebar-icon" aria-hidden="true"><img src="" data-hermes-logo-white="1" alt="" class="app-titlebar-logo"></span>' "titlebar logo"
    $indexHtml = Replace-First $indexHtml '<div class="empty-logo">.*?</div>' '<div class="empty-logo"><img src="" data-hermes-logo-white="1" alt="Hermes logo" class="empty-logo-image"></div>' "empty state logo"
    $indexHtml = $indexHtml.Replace('<span aria-hidden="true">鈫?/span><span data-i18n="session_jump_start">Start</span>', '<span aria-hidden="true">&#8593;</span><span data-i18n="session_jump_start">Start</span>')
    $indexHtml = $indexHtml.Replace('<span aria-hidden="true">鈫?/span><span class="session-jump-btn__text" data-i18n="session_jump_end">End</span>', '<span aria-hidden="true">&#8595;</span><span class="session-jump-btn__text" data-i18n="session_jump_end">End</span>')
    $indexHtml = $indexHtml.Replace('<kbd class="approval-kbd">鈫?/kbd>', '<kbd class="approval-kbd">Enter</kbd>')
    $indexHtml = $indexHtml.Replace('<span class="approval-btn-icon" aria-hidden="true">鈿?/span>', '<span class="approval-btn-icon" aria-hidden="true">&#9889;</span>')
    $indexHtml = $indexHtml.Replace('<span class="yolo-pill-icon" aria-hidden="true">鈿?/span>', '<span class="yolo-pill-icon" aria-hidden="true">&#9889;</span>')
    $indexHtml = $indexHtml.Replace('>鈻?/button>', '>&#9655;</button>')
    $indexHtml = $indexHtml.Replace(@'
            <div class="settings-field">
              <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input type="checkbox" id="settingsSessionJumpButtons" style="width:15px;height:15px;accent-color:var(--accent)">
                <span data-i18n="settings_label_session_jump_buttons">Show session jump buttons</span>
              </label>
              <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_session_jump_buttons">Show floating Start and End buttons while reading long session histories.</div>
                <input type="checkbox" id="settingsSessionEndlessScroll" style="width:15px;height:15px;accent-color:var(--accent)">
                <span data-i18n="settings_label_session_endless_scroll">Load older messages while scrolling up</span>
              </label>
              <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_session_endless_scroll">When enabled, older messages load automatically as you scroll upward. When disabled, use the older-messages button.</div>
            </div>
'@, @'
            <div class="settings-field">
              <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input type="checkbox" id="settingsSessionJumpButtons" style="width:15px;height:15px;accent-color:var(--accent)">
                <span data-i18n="settings_label_session_jump_buttons">Show session jump buttons</span>
              </label>
              <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_session_jump_buttons">Show floating Start and End buttons while reading long session histories.</div>
              <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input type="checkbox" id="settingsSessionEndlessScroll" style="width:15px;height:15px;accent-color:var(--accent)">
                <span data-i18n="settings_label_session_endless_scroll">Load older messages while scrolling up</span>
              </label>
              <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_session_endless_scroll">When enabled, older messages load automatically as you scroll upward. When disabled, use the older-messages button.</div>
            </div>
'@)
    $indexHtml = $indexHtml.Replace('<script src="static/boot.js?v=__WEBUI_VERSION__" defer></script>', '<script src="static/boot.js?v=__WEBUI_VERSION__&syn=black3" defer></script>')
    Set-Content -LiteralPath $indexPath -Value $indexHtml -Encoding utf8

    $stylePath = Join-Path $staticRoot "style.css"
    $styleCss = Get-Content -LiteralPath $stylePath -Raw
    $styleCss = Replace-First $styleCss ':root\.dark\s*\{.*?\n\s*\}' @'
:root.dark {
    --bg:#000000;--sidebar:#050505;--border:#171717;--border2:rgba(255,255,255,0.12);
    --text:#F5F5F5;--muted:#A3A3A3;--accent:#E5E5E5;--blue:#A3A3A3;--gold:#E5E5E5;--code-bg:#0A0A0A;
    --surface:#0B0B0B;--topbar-bg:rgba(8,8,8,.98);--main-bg:rgba(0,0,0,0.58);
    --focus-ring:rgba(229,229,229,.28);--focus-glow:rgba(229,229,229,.08);
    --input-bg:rgba(255,255,255,.04);--hover-bg:rgba(255,255,255,.06);
    --strong:#fff;--em:#CFCFCF;--code-text:#E5E5E5;--code-inline-bg:rgba(255,255,255,.08);--pre-text:#F5F5F5;
    --accent-hover:#FFFFFF;--accent-bg:rgba(229,229,229,0.08);--accent-bg-strong:rgba(229,229,229,0.14);--accent-text:#E5E5E5;
    --error:#EF5350;--success:#4CAF50;--warning:#FFA726;--info:#A3A3A3;
    --surface-subtle:rgba(255,255,255,.025);--surface-subtle-hover:rgba(255,255,255,.045);
    --border-subtle:rgba(255,255,255,.075);--border-muted:rgba(255,255,255,.12);
  }
'@ "dark theme"
    if ($styleCss -notmatch [regex]::Escape('.app-titlebar-logo{display:block;width:16px;height:16px;object-fit:contain;}')) {
        $styleCss = $styleCss.Replace('.app-titlebar-icon{display:inline-flex;align-items:center;color:var(--accent);}', ".app-titlebar-icon{display:inline-flex;align-items:center;color:var(--accent);}`n  .app-titlebar-logo{display:block;width:16px;height:16px;object-fit:contain;}")
    }
    $styleCss = $styleCss.Replace('.logo{width:32px;height:32px;border-radius:9px;background:linear-gradient(145deg,var(--accent-hover),var(--accent));display:flex;align-items:center;justify-content:center;font-weight:800;font-size:14px;color:#fff;flex-shrink:0;box-shadow:0 2px 8px var(--accent-bg-strong);}', ".logo{width:32px;height:32px;border-radius:9px;background:linear-gradient(145deg,var(--accent-hover),var(--accent));display:flex;align-items:center;justify-content:center;font-weight:800;font-size:14px;color:transparent;flex-shrink:0;box-shadow:0 2px 8px var(--accent-bg-strong);position:relative;overflow:hidden;}`n  .logo::after{content:"""";display:block;width:18px;height:18px;background:url('hermes.svg') no-repeat center / contain;}")
    $styleCss = $styleCss.Replace("background:url('hermes-agent-logo-white.svg') no-repeat center / contain;", "background:url('hermes.svg') no-repeat center / contain;")
    $styleCss = $styleCss.Replace('.empty-logo{width:64px;height:64px;border-radius:20px;background:linear-gradient(145deg,var(--accent-bg),var(--accent-bg));border:1px solid var(--accent-bg);display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:700;color:var(--accent-text);margin-bottom:4px;box-shadow:0 4px 20px var(--accent-bg);}', '.empty-logo{width:80px;height:80px;border-radius:20px;background:#000;border:1px solid rgba(255,255,255,.08);display:flex;align-items:center;justify-content:center;margin-bottom:4px;box-shadow:0 12px 30px rgba(0,0,0,.45);}')
    if ($styleCss -notmatch [regex]::Escape('.empty-logo-image{display:block;width:52px;height:52px;object-fit:contain;}')) {
        $styleCss = $styleCss.Replace('.empty-logo{width:80px;height:80px;border-radius:20px;background:#000;border:1px solid rgba(255,255,255,.08);display:flex;align-items:center;justify-content:center;margin-bottom:4px;box-shadow:0 12px 30px rgba(0,0,0,.45);}', ".empty-logo{width:80px;height:80px;border-radius:20px;background:#000;border:1px solid rgba(255,255,255,.08);display:flex;align-items:center;justify-content:center;margin-bottom:4px;box-shadow:0 12px 30px rgba(0,0,0,.45);}`n.empty-logo-image{display:block;width:52px;height:52px;object-fit:contain;}")
    }
    $styleCss = $styleCss.Replace('.app-dialog-overlay{position:fixed;inset:0;background:rgba(7,12,19,.62);backdrop-filter:blur(6px);z-index:1100;display:none;align-items:center;justify-content:center;padding:24px;}', '.app-dialog-overlay{position:fixed;inset:0;background:rgba(0,0,0,.72);backdrop-filter:blur(6px);z-index:1100;display:none;align-items:center;justify-content:center;padding:24px;}')
    $styleCss = $styleCss.Replace('.app-dialog{width:min(460px,100%);background:linear-gradient(180deg,rgba(21,31,45,.98),rgba(13,20,31,.98));border:1px solid var(--accent-bg-strong);border-radius:18px;box-shadow:0 18px 60px rgba(0,0,0,.45);padding:18px 18px 16px;color:var(--text);}', '.app-dialog{width:min(460px,100%);background:linear-gradient(180deg,#111,#080808);border:1px solid var(--border);border-radius:18px;box-shadow:0 18px 60px rgba(0,0,0,.45);padding:18px 18px 16px;color:var(--text);}')
    $styleCss = $styleCss.Replace('.onboarding-overlay{position:fixed;inset:0;z-index:1050;background:rgba(7,12,19,.78);backdrop-filter:blur(8px);display:none;align-items:center;justify-content:center;padding:24px;}', '.onboarding-overlay{position:fixed;inset:0;z-index:1050;background:rgba(0,0,0,.78);backdrop-filter:blur(8px);display:none;align-items:center;justify-content:center;padding:24px;}')
    $styleCss = $styleCss.Replace('.onboarding-card{width:min(980px,100%);max-height:min(760px,94vh);overflow:auto;border:1px solid var(--accent-bg-strong);border-radius:24px;background:linear-gradient(180deg,rgba(20,30,44,.98),rgba(11,17,27,.98));box-shadow:0 24px 80px rgba(0,0,0,.45);}', '.onboarding-card{width:min(980px,100%);max-height:min(760px,94vh);overflow:auto;border:1px solid var(--border);border-radius:24px;background:linear-gradient(180deg,#111,#080808);box-shadow:0 24px 80px rgba(0,0,0,.45);}')
    $styleCss = $styleCss.Replace('.onboarding-sidebar{padding:28px 24px;border-right:1px solid var(--border);background:linear-gradient(180deg,var(--accent-bg),transparent);}', '.onboarding-sidebar{padding:28px 24px;border-right:1px solid var(--border);background:linear-gradient(180deg,rgba(255,255,255,.04),transparent);}')
    $styleCss = $styleCss.Replace('background:linear-gradient(180deg,rgba(21,31,45,.98),rgba(13,20,31,.98));', 'background:linear-gradient(180deg,#111,#080808);')
    $styleCss = $styleCss.Replace('position:fixed;inset:0;background:rgba(7,12,19,.62);backdrop-filter:blur(6px);', 'position:fixed;inset:0;background:rgba(0,0,0,.72);backdrop-filter:blur(6px);')
    Set-Content -LiteralPath $stylePath -Value $styleCss -Encoding utf8

    $bootJsPath = Join-Path $staticRoot "boot.js"
    $bootJs = Get-Content -LiteralPath $bootJsPath -Raw
    $newChatHandler = @'
$('btnNewChat').onclick=async()=>{
  await newSession();await renderSessionList();closeMobileSidebar();$('msg').focus();
};
'@
    $bootJs = Replace-First $bootJs '\$\(''btnNewChat''\)\.onclick=async\(\)=>\{.*?\n\};' $newChatHandler "new conversation button"
    Set-Content -LiteralPath $bootJsPath -Value $bootJs -Encoding utf8

    $swJsPath = Join-Path $staticRoot "sw.js"
    $swJs = Get-Content -LiteralPath $swJsPath -Raw
    $swJs = $swJs.Replace("  './static/favicon.svg',`n  './static/favicon-32.png',`n  './manifest.json',", "  './static/favicon.svg',`n  './static/favicon-32.png',`n  './static/hermes.svg',`n  './manifest.json',")
    $swJs = $swJs.Replace("  './static/favicon.svg',`n  './static/favicon-32.png',`n  './static/hermes-agent-logo-white.svg',`n  './manifest.json',", "  './static/favicon.svg',`n  './static/favicon-32.png',`n  './static/hermes.svg',`n  './manifest.json',")
    Set-Content -LiteralPath $swJsPath -Value $swJs -Encoding utf8

    $webUiSettingsDir = Join-Path $HermesHomePath "webui"
    $webUiSettingsPath = Join-Path $webUiSettingsDir "settings.json"
    New-Item -ItemType Directory -Force -Path $webUiSettingsDir | Out-Null
    $settings = @{}
    if (Test-Path $webUiSettingsPath) {
        try {
            $loaded = Get-Content -LiteralPath $webUiSettingsPath -Raw | ConvertFrom-Json -AsHashtable
            if ($loaded -is [hashtable]) {
                $settings = $loaded
            }
        } catch {
            $settings = @{}
        }
    }
    $settings["theme"] = "dark"
    $settings["skin"] = "mono"
    $settings["language"] = "zh"
    $settings | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $webUiSettingsPath -Encoding utf8
}

if (-not (Test-Path $pythonExe)) {
    throw "Hermes Agent Python runtime not found: $pythonExe. Run scripts\hermes\setup-local-hermes.ps1 first."
}

New-Item -ItemType Directory -Force -Path $downloadRoot | Out-Null
if (Test-Path $extractRoot) {
    Remove-Item -LiteralPath $extractRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null

Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath
Expand-Archive -LiteralPath $zipPath -DestinationPath $extractRoot -Force

$sourceRoot = Get-ChildItem -Path $extractRoot -Directory | Select-Object -First 1
if (-not $sourceRoot) {
    throw "Unable to locate extracted Hermes WebUI source."
}

$resolvedRepoRoot = [System.IO.Path]::GetFullPath($repoRoot)
$resolvedTargetRoot = [System.IO.Path]::GetFullPath($hermesWebUiRoot)
if (-not $resolvedTargetRoot.StartsWith($resolvedRepoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to write Hermes WebUI outside the repository root: $resolvedTargetRoot"
}

if (Test-Path $hermesWebUiRoot) {
    Stop-HermesWebUiProcesses -WebUiRoot $hermesWebUiRoot
    for ($attempt = 1; $attempt -le 3 -and (Test-Path $hermesWebUiRoot); $attempt++) {
        try {
            Remove-Item -LiteralPath $hermesWebUiRoot -Recurse -Force -ErrorAction Stop
        } catch {
            if ($attempt -ge 3) {
                throw
            }
            Start-Sleep -Seconds 1
        }
    }
}

if (-not (Test-Path $hermesWebUiRoot)) {
    New-Item -ItemType Directory -Force -Path $hermesWebUiRoot | Out-Null
}

$runtimeItems = @(
    "api",
    "static",
    "server.py",
    "mcp_server.py",
    "requirements.txt",
    "README.md",
    "LICENSE"
)

foreach ($item in $runtimeItems) {
    $sourceItem = Join-Path $sourceRoot.FullName $item
    if (-not (Test-Path $sourceItem)) {
        throw "Missing runtime item in Hermes WebUI archive: $item"
    }
    Copy-Item -LiteralPath $sourceItem -Destination (Join-Path $hermesWebUiRoot $item) -Recurse -Force
}

$versionModulePath = Join-Path $hermesWebUiRoot "api\_version.py"
$versionModule = @(
    "__version__ = '$webUiBuildVersion'"
    ""
) -join "`n"
Set-Content -LiteralPath $versionModulePath -Value $versionModule -Encoding utf8

$configPyPath = Join-Path $hermesWebUiRoot "api\config.py"
$configPy = Get-Content -LiteralPath $configPyPath -Raw
$configPatchMarker = "def _delete_models_cache_on_disk() -> None:`n    try:`n        cache_path = globals().get(""_models_cache_path"")"
if ($configPy -notmatch [regex]::Escape($configPatchMarker)) {
    $hotfix = @'
def _delete_models_cache_on_disk() -> None:
    try:
        cache_path = globals().get("_models_cache_path")
        if cache_path:
            os.unlink(str(cache_path))
    except OSError:
        pass


'@
    $configPy = $configPy -replace "# Initial load`r?`nreload_config\(\)", "$hotfix# Initial load`nreload_config()"
    Set-Content -LiteralPath $configPyPath -Value $configPy -Encoding utf8
}

$helpersPath = Join-Path $hermesWebUiRoot "api\helpers.py"
$helpersText = Get-Content -LiteralPath $helpersPath -Raw
$helpersText = $helpersText -replace "handler\.send_header\('X-Frame-Options', 'DENY'\)\r?\n", ""
$helpersText = $helpersText -replace "(?m)^[ \t]+handler\.send_header\('Referrer-Policy', 'same-origin'\)$", "    handler.send_header('Referrer-Policy', 'same-origin')"
$helpersText = $helpersText -replace "connect-src 'self' https://cdn\.jsdelivr\.net; ", "connect-src 'self' https://cdn.jsdelivr.net http://127.0.0.1:* http://localhost:* ws://127.0.0.1:* ws://localhost:*; "
$helpersText = $helpersText -replace "base-uri 'self'; form-action 'self'", "base-uri 'self'; form-action 'self'; frame-ancestors 'self' http://127.0.0.1:* http://localhost:*"
Set-Content -LiteralPath $helpersPath -Value $helpersText -Encoding utf8

$configPyPath = Join-Path $hermesWebUiRoot "api\config.py"
$configPy = Get-Content -LiteralPath $configPyPath -Raw
$configPy = $configPy.Replace('    "language": "en",  # UI locale code; must match a key in static/i18n.js LOCALES', '    "language": "zh",  # UI locale code; must match a key in static/i18n.js LOCALES')
Set-Content -LiteralPath $configPyPath -Value $configPy -Encoding utf8

$serverPyPath = Join-Path $hermesWebUiRoot "server.py"
$serverPy = Get-Content -LiteralPath $serverPyPath -Raw
$serverPy = $serverPy -replace "frame-ancestors 'self'; ", "frame-ancestors 'self' http://127.0.0.1:* http://localhost:*; "
Set-Content -LiteralPath $serverPyPath -Value $serverPy -Encoding utf8

$manifestPath = Join-Path $hermesWebUiRoot "webui-version.json"
$manifest = [ordered]@{
    version = $Version
    source = "https://github.com/nesquena/hermes-webui"
    archive = $downloadUrl
    installed_at = (Get-Date).ToString("o")
}
$manifest | ConvertTo-Json | Set-Content -LiteralPath $manifestPath -Encoding utf8

Apply-SynapseHermesBranding -WebUiRoot $hermesWebUiRoot -AssetsRoot $brandingAssetsRoot -HermesHomePath $hermesHome

& $pythonExe -m pip install -r (Join-Path $hermesWebUiRoot "requirements.txt")

Write-Host "Hermes WebUI :" $hermesWebUiRoot
Write-Host "Version      :" $Version
Write-Host "Python       :" $pythonExe
