const { app, BrowserWindow, ipcMain, Menu, Tray } = require('electron');
const path = require('path');
const { nativeTheme } = require('electron');
const { spawn, spawnSync, execSync } = require('child_process');
const net = require('net');
const log = require('electron-log');
const fs = require('fs');

// 閰嶇疆鏃ュ織
log.transports.file.level = 'info';
log.transports.console.level = 'debug';

// 鍗曞疄渚嬮攣瀹?- 闃叉澶氭鍚姩
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  console.log('Another SynapseAutomation instance is already running. Exiting.');
  log.info('Another SynapseAutomation instance is already running. Exiting.');
  app.quit();
  process.exit(0);
}

// 娣诲姞鎺у埗鍙拌緭鍑轰互渚胯皟璇?
console.log('=== Electron Main Process Starting ===');
console.log('Log file path:', log.transports.file.getFile().path);

class SynapseApp {
  constructor() {
    this.mainWindow = null;
    this.launcherWindow = null;
    this.settingsWindow = null;
    this.backendProcess = null;
    this.celeryProcess = null;
    this.redisProcess = null;
    this.playwrightWorkerProcess = null;
    this.frontendProcess = null;
    this.supervisorProcess = null;
    this.playwrightBrowserPath = null;
    this.visualBrowserWindows = new Map();
    this.servicesStarted = false;
    this.appIconPath = null;
    this.tray = null;
    this.isQuitting = false;
    this.isRestarting = false;
    this.isPackagedRuntime = false;
    this.frontendPort = 3000;
    this.backendPort = null;
    this.playwrightWorkerPort = null;
    this.runtimeSettings = {
      browserHeadless: true,
      automationRuntime: 'patchright'
    };
  }

  useExternalStack() {
    return process.env.SYNAPSE_USE_EXTERNAL_STACK === '1';
  }

  async initialize() {
    console.log('SynapseAutomation is starting...');
    log.info('SynapseAutomation is starting...');

    // 绛夊緟 Electron 鍑嗗灏辩华
    await app.whenReady();
    nativeTheme.themeSource = 'dark';
    log.info('Applied default dark theme source for Electron browser surfaces');

    this.repoRoot = path.join(__dirname, '../../../');
    this.isPackagedRuntime = this.detectPackagedRuntime();
    this.isDev = !this.isPackagedRuntime;
    const supervisorPaths = this.getSupervisorPaths();
    const supervisorExists = Boolean(supervisorPaths.exePath || supervisorPaths.scriptPath);
    this.appIconPath = this.getAppIconPath();
    this.runtimeSettings = this.loadRuntimeSettings();
    process.env.PLAYWRIGHT_HEADLESS = this.runtimeSettings.browserHeadless ? 'true' : 'false';
    process.env.SYNAPSE_PLAYWRIGHT_RUNTIME = this.runtimeSettings.automationRuntime;
    this.applyPlatformBrowserPreferenceEnv(process.env, this.runtimeSettings.platformBrowserPreferences || {});
    this.setupTray();

    console.log('App ready. isDev:', this.isDev, 'isPackaged:', app.isPackaged, 'isPackagedRuntime:', this.isPackagedRuntime);
    console.log('resourcesPath:', process.resourcesPath);
    console.log('supervisor paths:', supervisorPaths);
    log.info('App ready. isDev:', this.isDev, 'isPackaged:', app.isPackaged, 'isPackagedRuntime:', this.isPackagedRuntime);
    log.info('resourcesPath:', process.resourcesPath);
    log.info('supervisor paths:', supervisorPaths);

    // 1. 璁剧疆 Playwright 娴忚鍣ㄨ矾寰?
    this.setupPlaywrightPath();

    // 2. 鍚姩鍚庣/鍓嶇鏈嶅姟锛堢敓浜ч粯璁ゅ惎鍔紝寮€鍙戝彲鐢?SYNAPSE_START_SERVICES=1 寮哄埗锛?
    const useExternalStack = this.useExternalStack();
    const shouldStartServices = !useExternalStack && (process.env.SYNAPSE_START_SERVICES === '1' || !this.isDev);
    const showLauncher = process.env.SYNAPSE_SHOW_LAUNCHER === '1'; // 鏄惁鏄剧ず鍚姩绠＄悊鍣?
    console.log('Use external stack:', useExternalStack);
    console.log('Should start services:', shouldStartServices, '(isDev:', this.isDev, ')');
    console.log('Show launcher:', showLauncher);
    log.info('Use external stack:', useExternalStack);
    log.info('Should start services:', shouldStartServices, '(isDev:', this.isDev, ')');
    log.info('Show launcher:', showLauncher);

    if (shouldStartServices) {
      console.log('Starting services...');
      log.info('Starting services...');
      await this.startServices();
      console.log('Services started');
      log.info('Services started');
    }

    // 3. 鍒涘缓绐楀彛锛堝鏋滃惎鐢ㄥ惎鍔ㄧ鐞嗗櫒锛屽垯鏄剧ず鍚姩绠＄悊鍣紱鍚﹀垯鍒涘缓涓荤獥鍙ｏ級
    if (showLauncher) {
      this.createLauncherWindow();
    } else {
      this.createMainWindow();
    }

    // 4. 璁剧疆 IPC 澶勭悊
    this.setupIPC();

    // 5. 璁剧疆搴旂敤浜嬩欢
    this.setupAppEvents();

    log.info('SynapseAutomation startup complete');
  }

  setupPlaywrightPath() {
    // 鑾峰彇鎵撳寘鍚庣殑璧勬簮璺緞
    const isDev = this.isDev;

    if (isDev) {
      // 寮€鍙戠幆澧冿細浣跨敤椤圭洰鏍圭洰褰曠殑娴忚鍣?
      this.playwrightBrowserPath = path.join(__dirname, '../../../browsers');
      log.info('Dev mode Playwright browser path:', this.playwrightBrowserPath);
    } else {
      // 鐢熶骇鐜锛氫娇鐢ㄦ墦鍖呭悗鐨勬祻瑙堝櫒
      this.playwrightBrowserPath = path.join(process.resourcesPath, 'browsers');
      log.info('Packaged mode Playwright browser path:', this.playwrightBrowserPath);
    }

    // 璁剧疆鐜鍙橀噺锛岃 Playwright 浣跨敤鎸囧畾鐨勬祻瑙堝櫒
    process.env.PLAYWRIGHT_BROWSERS_PATH = this.playwrightBrowserPath;

    // 楠岃瘉娴忚鍣ㄦ槸鍚﹀瓨鍦?
    if (fs.existsSync(this.playwrightBrowserPath)) {
      log.info('Playwright browser path is ready');
    } else {
      log.warn('Playwright browser path does not exist; automation features may be unavailable.');
    }
  }

  detectPackagedRuntime() {
    if (app.isPackaged) {
      return true;
    }

    const executableName = path.basename(process.execPath || '').toLowerCase();
    const runningViaElectronBinary = executableName === 'electron.exe' || executableName === 'electron';
    const packagedMarkers = [
      path.join(process.resourcesPath, 'supervisor', 'supervisor.exe'),
      path.join(process.resourcesPath, 'frontend', 'standalone', 'server.js'),
      path.join(process.resourcesPath, 'services', 'backend', 'backend.exe')
    ];

    return !runningViaElectronBinary && packagedMarkers.some((markerPath) => fs.existsSync(markerPath));
  }

  getResourcesRoot() {
    return this.isDev ? this.repoRoot : process.resourcesPath;
  }

  getSupervisorPaths() {
    const packagedExePath = path.join(process.resourcesPath, 'supervisor', 'supervisor.exe');
    const packagedScriptPath = path.join(process.resourcesPath, 'supervisor', 'supervisor.py');
    const devSupervisorDir = path.join(this.repoRoot, 'desktop-electron', 'resources', 'supervisor');
    const devExePath = path.join(devSupervisorDir, 'supervisor.exe');
    const devScriptPath = path.join(devSupervisorDir, 'supervisor.py');
    const preferScriptInDev = this.isDev;
    const exePath = preferScriptInDev
      ? null
      : this.resolveFirstPath([packagedExePath, devExePath]);
    const scriptPath = this.resolveFirstPath(
      preferScriptInDev
        ? [devScriptPath, packagedScriptPath]
        : exePath
          ? []
          : [packagedScriptPath, devScriptPath]
    );
    const fallbackExePath = exePath || (
      scriptPath
        ? null
        : this.resolveFirstPath(
            this.isDev
              ? [devExePath, packagedExePath]
              : [packagedExePath, devExePath]
          )
    );

    return {
      exePath: fallbackExePath,
      scriptPath,
      cwd: fallbackExePath ? path.dirname(fallbackExePath) : (scriptPath ? path.dirname(scriptPath) : null)
    };
  }

  normalizeBackendUrl(rawUrl) {
    const fallbackPort = this.resolveBackendPort(rawUrl);
    const fallback = `http://127.0.0.1:${fallbackPort}`;
    const candidate = String(rawUrl || '').trim().replace(/\/+$/, '') || fallback;

    try {
      const url = new URL(candidate);
      if (url.hostname === 'localhost') {
        url.hostname = '127.0.0.1';
      }
      return url.toString().replace(/\/+$/, '');
    } catch (error) {
      return fallback;
    }
  }

  getConfiguredBackendPort(rawUrl) {
    const envPort = [
      process.env.SYN_BACKEND_PORT,
      process.env.BACKEND_PORT
    ].find((value) => String(value || '').trim());

    const parsedEnvPort = Number.parseInt(envPort, 10);
    if (Number.isInteger(parsedEnvPort) && parsedEnvPort > 0) {
      return parsedEnvPort;
    }

    try {
      if (rawUrl) {
        const url = new URL(String(rawUrl).trim());
        const parsedUrlPort = Number.parseInt(url.port, 10);
        if (Number.isInteger(parsedUrlPort) && parsedUrlPort > 0) {
          return parsedUrlPort;
        }
      }
    } catch (error) {
      // Ignore malformed URL and fall back to the default port.
    }

    return 7000;
  }

  resolveBackendPort(rawUrl) {
    const configuredPort = this.getConfiguredBackendPort(rawUrl);
    const selectedPort = Number.parseInt(String(this.backendPort || ''), 10);
    if (Number.isInteger(selectedPort) && selectedPort > 0) {
      return selectedPort;
    }
    return configuredPort;
  }

  getBackendBaseUrl() {
    const rawUrl = [
      process.env.SYN_BACKEND_URL,
      process.env.NEXT_PUBLIC_SYN_BACKEND_URL,
      process.env.NEXT_PUBLIC_BACKEND_URL
    ].find((value) => String(value || '').trim());

    return this.normalizeBackendUrl(rawUrl);
  }

  getBackendPort() {
    return this.resolveBackendPort(this.getBackendBaseUrl());
  }

  getConfiguredPlaywrightWorkerPort() {
    const envPort = [
      process.env.PLAYWRIGHT_WORKER_PORT,
      process.env.SYN_PLAYWRIGHT_WORKER_PORT
    ].find((value) => String(value || '').trim());

    const parsedEnvPort = Number.parseInt(envPort, 10);
    if (Number.isInteger(parsedEnvPort) && parsedEnvPort > 0) {
      return parsedEnvPort;
    }

    return 7001;
  }

  getPlaywrightWorkerPort() {
    const selectedPort = Number.parseInt(String(this.playwrightWorkerPort || ''), 10);
    if (Number.isInteger(selectedPort) && selectedPort > 0) {
      return selectedPort;
    }
    return this.getConfiguredPlaywrightWorkerPort();
  }

  getBackendApiBaseUrl() {
    return `${this.getBackendBaseUrl()}/api/v1`;
  }

  getSystemApiBaseUrl() {
    return `${this.getBackendApiBaseUrl()}/system`;
  }

  getPreferredFrontendPort() {
    const envPort = [
      process.env.SYN_FRONTEND_PORT,
      process.env.FRONTEND_PORT,
      process.env.PORT
    ].find((value) => String(value || '').trim());

    const parsedEnvPort = Number.parseInt(envPort, 10);
    if (Number.isInteger(parsedEnvPort) && parsedEnvPort > 0) {
      return parsedEnvPort;
    }

    return 3000;
  }

  getFrontendPort() {
    const currentPort = Number.parseInt(String(this.frontendPort || ''), 10);
    if (Number.isInteger(currentPort) && currentPort > 0) {
      return currentPort;
    }
    return this.getPreferredFrontendPort();
  }

  getFrontendBaseUrl() {
    return `http://127.0.0.1:${this.getFrontendPort()}`;
  }

  async findAvailablePort(preferredPort, attempts = 20) {
    for (let offset = 0; offset < attempts; offset += 1) {
      const candidatePort = preferredPort + offset;
      if (await this.canBindPort(candidatePort)) {
        return candidatePort;
      }
    }

    throw new Error(`Unable to find an available port starting from ${preferredPort}`);
  }

  async resolveManagedPort(preferredPort, ownsPortCheck, reservedPorts = new Set(), attempts = 20) {
    for (let offset = 0; offset < attempts; offset += 1) {
      const candidatePort = preferredPort + offset;
      if (reservedPorts.has(candidatePort)) {
        continue;
      }

      if (await this.isPortInUse(candidatePort)) {
        if (ownsPortCheck && await ownsPortCheck(candidatePort)) {
          return candidatePort;
        }
        continue;
      }

      if (await this.canBindPort(candidatePort)) {
        return candidatePort;
      }
    }

    throw new Error(`Unable to resolve managed port starting from ${preferredPort}`);
  }

  getRuntimeSettingsPath() {
    return path.join(app.getPath('userData'), 'runtime-settings.json');
  }

  normalizeBooleanSetting(value, defaultValue = true) {
    if (typeof value === 'boolean') {
      return value;
    }
    if (typeof value === 'string') {
      const normalized = value.trim().toLowerCase();
      if (['true', '1', 'yes', 'on'].includes(normalized)) {
        return true;
      }
      if (['false', '0', 'no', 'off'].includes(normalized)) {
        return false;
      }
    }
    if (typeof value === 'number') {
      if (value === 1) {
        return true;
      }
      if (value === 0) {
        return false;
      }
    }
    return defaultValue;
  }

  getDefaultPlatformBrowserPreferences() {
    return {
      douyin: 'chromium',
      kuaishou: 'chromium',
      xiaohongshu: 'chromium',
      channels: 'chromium',
      bilibili: 'chromium'
    };
  }

  normalizePlatformBrowserKey(value) {
    const normalized = String(value || '').trim().toLowerCase();
    if (normalized === 'tencent') {
      return 'channels';
    }
    return normalized;
  }

  normalizePlatformBrowserChoice(value, fallback = 'chromium') {
    return ['auto', 'chromium', 'firefox'].includes(value) ? value : fallback;
  }

  normalizePlatformBrowserPreferences(raw = {}) {
    const defaults = this.getDefaultPlatformBrowserPreferences();
    const normalized = { ...defaults };

    for (const [platform, defaultChoice] of Object.entries(defaults)) {
      const directValue = raw?.[platform];
      const aliasValue = platform === 'channels' ? raw?.tencent : undefined;
      const candidate = typeof directValue === 'string'
        ? directValue.trim().toLowerCase()
        : typeof aliasValue === 'string'
          ? aliasValue.trim().toLowerCase()
          : null;
      normalized[platform] = this.normalizePlatformBrowserChoice(candidate, defaultChoice);
    }

    return normalized;
  }

  normalizeRuntimeSettings(raw = {}) {
    return {
      browserHeadless: this.normalizeBooleanSetting(raw.browserHeadless, true),
      automationRuntime: raw.automationRuntime === 'playwright' ? 'playwright' : 'patchright',
      platformBrowserPreferences: this.normalizePlatformBrowserPreferences(raw.platformBrowserPreferences)
    };
  }

  applyPlatformBrowserPreferenceEnv(targetEnv, rawPreferences = {}) {
    const preferences = this.normalizePlatformBrowserPreferences(rawPreferences);
    targetEnv.SYNAPSE_PLATFORM_BROWSER_PREFERENCES = JSON.stringify(preferences);
    for (const [platform, choice] of Object.entries(preferences)) {
      targetEnv[`SYNAPSE_PLATFORM_BROWSER_${platform.toUpperCase()}`] = choice;
    }
    targetEnv.SYNAPSE_PLATFORM_BROWSER_TENCENT = preferences.channels;
    return preferences;
  }

  loadRuntimeSettings() {
    const settingsPath = this.getRuntimeSettingsPath();
    try {
      if (!fs.existsSync(settingsPath)) {
        return this.normalizeRuntimeSettings();
      }
      return this.normalizeRuntimeSettings(JSON.parse(fs.readFileSync(settingsPath, 'utf8')));
    } catch (error) {
      log.warn('Failed to load runtime settings; using defaults:', error);
      return this.normalizeRuntimeSettings();
    }
  }

  saveRuntimeSettings(nextSettings = {}) {
    const settings = this.normalizeRuntimeSettings({
      ...this.runtimeSettings,
      ...nextSettings
    });
    const settingsPath = this.getRuntimeSettingsPath();
    fs.mkdirSync(path.dirname(settingsPath), { recursive: true });
    fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2), 'utf8');
    this.runtimeSettings = settings;
    process.env.PLAYWRIGHT_HEADLESS = settings.browserHeadless ? 'true' : 'false';
    process.env.SYNAPSE_PLAYWRIGHT_RUNTIME = settings.automationRuntime;
    this.applyPlatformBrowserPreferenceEnv(process.env, settings.platformBrowserPreferences || {});
    return settings;
  }

  getBackendDir() {
    return this.isDev
      ? path.join(this.repoRoot, 'syn_backend')
      : path.join(process.resourcesPath, 'syn_backend');
  }

  getPythonPath() {
    return this.getPythonRuntime().path;
  }

  getSynenvSitePackagesPath() {
    const candidates = [
      path.join(this.getResourcesRoot(), 'synenv', 'Lib', 'site-packages'),
      path.join(this.getResourcesRoot(), 'synenv', 'lib', 'site-packages')
    ];
    return this.resolveFirstPath(candidates) || null;
  }

  buildPythonEnv(baseEnv = process.env) {
    const sitePackagesPath = this.getSynenvSitePackagesPath();
    if (!sitePackagesPath) {
      return baseEnv;
    }

    const existing = String(baseEnv.PYTHONPATH || '')
      .split(path.delimiter)
      .filter((entry) => entry && entry !== sitePackagesPath);
    return {
      ...baseEnv,
      PYTHONPATH: [sitePackagesPath, ...existing].join(path.delimiter)
    };
  }

  testPythonExecutable(command, args = []) {
    try {
      const result = spawnSync(command, [...args, '-c', 'import sys; print(sys.version)'], {
        cwd: this.getResourcesRoot(),
        env: this.buildPythonEnv(process.env),
        encoding: 'utf8',
        windowsHide: true,
        timeout: 10000
      });

      if (result.error) {
        return { ok: false, error: result.error.message };
      }
      if (result.status !== 0) {
        return {
          ok: false,
          error: String(result.stderr || result.stdout || '').trim() || `python_probe_failed:${result.status}`
        };
      }
      return { ok: true, version: String(result.stdout || '').trim() };
    } catch (error) {
      return { ok: false, error: error.message };
    }
  }

  shouldReuseCachedPythonRuntime() {
    if (!this.pythonRuntimeCache) {
      return false;
    }

    if (this.pythonRuntimeCache.source !== 'synenv') {
      return false;
    }

    return fs.existsSync(this.pythonRuntimeCache.path);
  }

  getPythonRuntime() {
    if (this.shouldReuseCachedPythonRuntime()) {
      return this.pythonRuntimeCache;
    }

    const packagedPython = path.join(this.getResourcesRoot(), 'synenv', 'Scripts', 'python.exe');
    const candidates = [];
    if (fs.existsSync(packagedPython)) {
      candidates.push({ path: packagedPython, args: [], source: 'synenv' });
    }
    candidates.push({ path: 'python', args: [], source: 'system' });

    const failures = [];
    for (const candidate of candidates) {
      const probe = this.testPythonExecutable(candidate.path, candidate.args);
      if (probe.ok) {
        this.pythonRuntimeCache = {
          path: candidate.path,
          args: candidate.args,
          source: candidate.source,
          version: probe.version,
          sitePackagesPath: this.getSynenvSitePackagesPath(),
          error: null
        };
        if (candidate.source !== 'synenv') {
          log.warn('Packaged synenv Python is unavailable; using fallback Python:', candidate.path);
        }
        return this.pythonRuntimeCache;
      }
      failures.push(`${candidate.source}:${probe.error}`);
    }

    this.pythonRuntimeCache = {
      path: packagedPython,
      args: [],
      source: 'missing',
      version: null,
      sitePackagesPath: this.getSynenvSitePackagesPath(),
      error: failures.join(' | ')
    };
    return this.pythonRuntimeCache;
  }

  getNpmCommand() {
    if (process.platform !== 'win32') {
      return 'npm';
    }
    const candidates = [
      process.env.npm_execpath,
      path.join(process.env.ProgramFiles || 'C:\\Program Files', 'nodejs', 'npm.cmd'),
      path.join(process.env['ProgramFiles(x86)'] || 'C:\\Program Files (x86)', 'nodejs', 'npm.cmd')
    ].filter((candidate) => candidate && /\.(cmd|exe)$/i.test(candidate));
    return this.resolveFirstPath(candidates) || 'npm.cmd';
  }

  getNodeCommand() {
    if (process.platform !== 'win32') {
      return 'node';
    }
    return this.resolveFirstPath([
      path.join(process.env.ProgramFiles || 'C:\\Program Files', 'nodejs', 'node.exe'),
      path.join(process.env['ProgramFiles(x86)'] || 'C:\\Program Files (x86)', 'nodejs', 'node.exe')
    ]) || 'node.exe';
  }

  ensureSynenvConfig() {
    if (this.isDev) {
      return;
    }

    const runtime = this.getPythonRuntime();
    if (runtime.source === 'missing') {
      log.error('No usable Python runtime found:', runtime.error);
    } else {
      log.info('Python runtime selected:', runtime.path, `(${runtime.source})`);
      if (runtime.sitePackagesPath) {
        log.info('Packaged Python site-packages exposed via PYTHONPATH:', runtime.sitePackagesPath);
      }
    }
  }

  getBrowsersRoot() {
    return this.isDev
      ? path.join(this.repoRoot, 'browsers')
      : path.join(process.resourcesPath, 'browsers');
  }

  resolveFirstPath(candidates) {
    return candidates.find((candidate) => candidate && fs.existsSync(candidate));
  }

  getSubdirs(root, prefix) {
    try {
      return fs.readdirSync(root, { withFileTypes: true })
        .filter((entry) => entry.isDirectory() && entry.name.startsWith(prefix))
        .map((entry) => path.join(root, entry.name))
        .sort()
        .reverse();
    } catch (error) {
      return [];
    }
  }

  resolveChromePath(browsersRoot) {
    const chromiumRoot = path.join(browsersRoot, 'chromium');
    const candidates = [];

    for (const dir of this.getSubdirs(chromiumRoot, 'hibbiki-')) {
      candidates.push(path.join(dir, 'Chrome-bin', 'chrome.exe'));
    }
    for (const dir of this.getSubdirs(browsersRoot, 'chromium-')) {
      candidates.push(path.join(dir, 'chrome-win64', 'chrome.exe'));
      candidates.push(path.join(dir, 'chrome-win', 'chrome.exe'));
    }
    for (const dir of this.getSubdirs(chromiumRoot, 'chromium-')) {
      candidates.push(path.join(dir, 'chrome-win64', 'chrome.exe'));
      candidates.push(path.join(dir, 'chrome-win', 'chrome.exe'));
    }
    for (const dir of this.getSubdirs(path.join(browsersRoot, 'chrome-for-testing'), 'chrome-')) {
      candidates.push(path.join(dir, 'chrome-win64', 'chrome.exe'));
    }

    return this.resolveFirstPath(candidates) || null;
  }

  resolveFirefoxPath(browsersRoot) {
    const candidates = [];

    for (const dir of this.getSubdirs(browsersRoot, 'firefox-')) {
      candidates.push(path.join(dir, 'firefox', 'firefox.exe'));
    }
    for (const dir of this.getSubdirs(path.join(browsersRoot, 'firefox'), 'firefox-')) {
      candidates.push(path.join(dir, 'firefox', 'firefox.exe'));
    }

    return this.resolveFirstPath(candidates) || null;
  }

  getBrowserAssetVersion(executablePath) {
    if (!executablePath) {
      return null;
    }

    const parts = String(executablePath).split(/[\\/]+/).reverse();
    const prefixes = ['hibbiki-', 'chromium-', 'chrome-', 'firefox-'];
    return parts.find((part) => prefixes.some((prefix) => part.startsWith(prefix))) || null;
  }

  getPythonPackageInfo(packageName) {
    const runtime = this.getPythonRuntime();
    const pythonPath = runtime.path;
    const inspectCode = [
      'import importlib.metadata',
      'import importlib.util',
      'import pathlib',
      'import json',
      `name = ${JSON.stringify(packageName)}`,
      'payload = {"installed": False, "version": None, "error": None, "driverInstalled": None, "driverPath": None}',
      'spec = importlib.util.find_spec(name)',
      'if spec is not None:',
      '    payload["installed"] = True',
      '    try:',
      '        payload["version"] = importlib.metadata.version(name)',
      '    except Exception:',
      '        payload["version"] = None',
      '    try:',
      '        pkg_dir = pathlib.Path(spec.origin).resolve().parent if spec.origin else None',
      '        driver = pkg_dir / "driver" / ("node.exe" if __import__("sys").platform == "win32" else "node") if pkg_dir else None',
      '        payload["driverPath"] = str(driver) if driver else None',
      '        payload["driverInstalled"] = bool(driver and driver.exists())',
      '    except Exception as exc:',
      '        payload["driverInstalled"] = False',
      '        payload["error"] = str(exc)',
      'print(json.dumps(payload, ensure_ascii=True))'
    ].join('\n');

    try {
      if (runtime.source === 'missing') {
        return {
          installed: false,
          version: null,
          driverInstalled: false,
          driverPath: null,
          error: runtime.error || 'python_runtime_unavailable'
        };
      }

      const result = spawnSync(pythonPath, [...runtime.args, '-c', inspectCode], {
        cwd: this.getResourcesRoot(),
        env: this.buildPythonEnv(process.env),
        encoding: 'utf8',
        windowsHide: true
      });

      if (result.error) {
        return {
          installed: false,
          version: null,
          driverInstalled: false,
          driverPath: null,
          error: result.error.message
        };
      }

      const raw = String(result.stdout || '').trim();
      if (!raw) {
        return {
          installed: false,
          version: null,
          driverInstalled: false,
          driverPath: null,
          error: String(result.stderr || '').trim() || 'empty_python_package_probe'
        };
      }

      return JSON.parse(raw);
    } catch (error) {
      return {
        installed: false,
        version: null,
        driverInstalled: false,
        driverPath: null,
        error: error.message
      };
    }
  }

  getPackagedWorkerRuntimeInfo(packageName) {
    const packageRoot = path.join(
      this.getResourcesRoot(),
      'services',
      'playwright-worker',
      '_internal',
      packageName
    );
    if (!fs.existsSync(packageRoot)) {
      return {
        installed: false,
        version: null,
        driverInstalled: false,
        driverPath: null,
        error: null
      };
    }

    const driverPath = path.join(
      packageRoot,
      'driver',
      process.platform === 'win32' ? 'node.exe' : 'node'
    );
    return {
      installed: true,
      version: null,
      driverInstalled: fs.existsSync(driverPath),
      driverPath,
      source: 'packaged-worker',
      error: fs.existsSync(driverPath) ? null : 'driver_missing'
    };
  }

  mergeRuntimeInfo(pythonInfo, packagedInfo) {
    if (pythonInfo.installed) {
      return {
        ...pythonInfo,
        source: pythonInfo.source || 'python',
        driverInstalled: pythonInfo.driverInstalled || packagedInfo.driverInstalled,
        driverPath: pythonInfo.driverInstalled ? pythonInfo.driverPath : packagedInfo.driverPath
      };
    }
    if (packagedInfo.installed) {
      return packagedInfo;
    }
    return pythonInfo;
  }

  getBrowserRuntimeInfo() {
    const browsersRoot = this.getBrowsersRoot();
    const chromiumPath = this.resolveChromePath(browsersRoot);
    const firefoxPath = this.resolveFirefoxPath(browsersRoot);
    const patchrightInfo = this.mergeRuntimeInfo(
      this.getPythonPackageInfo('patchright'),
      this.getPackagedWorkerRuntimeInfo('patchright')
    );
    const playwrightInfo = this.mergeRuntimeInfo(
      this.getPythonPackageInfo('playwright'),
      this.getPackagedWorkerRuntimeInfo('playwright')
    );
    const preferredRuntime = this.runtimeSettings.automationRuntime;

    let activeRuntime = null;
    const patchrightReady = patchrightInfo.installed && patchrightInfo.driverInstalled !== false;
    const playwrightReady = playwrightInfo.installed && playwrightInfo.driverInstalled !== false;
    if (preferredRuntime === 'playwright' && playwrightReady) {
      activeRuntime = 'playwright';
    } else if (preferredRuntime === 'patchright' && patchrightReady) {
      activeRuntime = 'patchright';
    } else if (patchrightReady) {
      activeRuntime = 'patchright';
    } else if (playwrightReady) {
      activeRuntime = 'playwright';
    }

    return {
      pythonPath: this.getPythonPath(),
      pythonRuntime: this.getPythonRuntime(),
      browsersPath: browsersRoot,
      preferredRuntime,
      activeRuntime,
      platformBrowserPreferences: this.runtimeSettings.platformBrowserPreferences,
      runtimes: {
        patchright: patchrightInfo,
        playwright: playwrightInfo
      },
      browsers: {
        chromium: {
          installed: Boolean(chromiumPath),
          path: chromiumPath,
          version: this.getBrowserAssetVersion(chromiumPath),
          uninstallable: true
        },
        firefox: {
          installed: Boolean(firefoxPath),
          path: firefoxPath,
          version: this.getBrowserAssetVersion(firefoxPath),
          uninstallable: true,
          required: false
        }
      }
    };
  }

  getHibbikiInstallerPath() {
    return this.resolveFirstPath([
      path.join(this.getResourcesRoot(), 'scripts', 'packaging', 'install_hibbiki_chromium.ps1'),
      path.join(this.repoRoot, 'scripts', 'packaging', 'install_hibbiki_chromium.ps1')
    ]);
  }

  async installHibbikiChromium() {
    const scriptPath = this.getHibbikiInstallerPath();
    if (!scriptPath) {
      return {
        success: false,
        output: '',
        error: 'hibbiki_installer_not_found'
      };
    }

    const env = this.buildPythonEnv({
      ...process.env,
      PLAYWRIGHT_BROWSERS_PATH: this.getBrowsersRoot(),
      SYNAPSE_PLAYWRIGHT_RUNTIME: this.runtimeSettings.automationRuntime
    });

    return this.runManagedCommand(
      'powershell.exe',
      [
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', scriptPath,
        '-ProjectRoot', this.getResourcesRoot(),
        '-Clean'
      ],
      { env, logPrefix: 'hibbiki:chromium' }
    );
  }

  getBrowserAssetRemovalTargets(target) {
    const browsersRoot = this.getBrowsersRoot();

    if (target === 'chromium') {
      return [
        path.join(browsersRoot, 'chromium'),
        ...this.getSubdirs(browsersRoot, 'chromium-'),
        ...this.getSubdirs(browsersRoot, 'chromium_headless_shell-'),
        path.join(browsersRoot, 'chrome-for-testing')
      ];
    }

    if (target === 'firefox') {
      return [
        path.join(browsersRoot, 'firefox'),
        ...this.getSubdirs(browsersRoot, 'firefox-')
      ];
    }

    return [];
  }

  async uninstallBrowserComponent(target) {
    const allowedTargets = new Set(['chromium', 'firefox', 'patchright', 'playwright']);
    if (!allowedTargets.has(target)) {
      return { success: false, error: `unsupported_uninstall_target:${target}` };
    }

    if (target === 'patchright' || target === 'playwright') {
      const runtime = this.getPythonRuntime();
      if (runtime.source !== 'synenv') {
        return {
          success: false,
          output: '',
          error: `packaged_python_unavailable:${runtime.error || runtime.source}`,
          browserRuntimeInfo: this.getBrowserRuntimeInfo()
        };
      }

      const env = this.buildPythonEnv({
        ...process.env,
        PLAYWRIGHT_BROWSERS_PATH: this.getBrowsersRoot(),
        SYNAPSE_PLAYWRIGHT_RUNTIME: this.runtimeSettings.automationRuntime
      });

      const result = await this.runManagedCommand(
        this.getPythonPath(),
        ['-m', 'pip', 'uninstall', '-y', target],
        { env, logPrefix: `pip:remove:${target}` }
      );

      if (result.success && this.runtimeSettings.automationRuntime === target) {
        const fallbackRuntime = target === 'patchright' ? 'playwright' : 'patchright';
        const fallbackInfo = this.mergeRuntimeInfo(
          this.getPythonPackageInfo(fallbackRuntime),
          this.getPackagedWorkerRuntimeInfo(fallbackRuntime)
        );
        if (fallbackInfo.installed && fallbackInfo.driverInstalled !== false) {
          this.saveRuntimeSettings({ automationRuntime: fallbackRuntime });
        }
      }

      return {
        success: result.success,
        output: result.stdout,
        error: result.error,
        browserRuntimeInfo: this.getBrowserRuntimeInfo()
      };
    }

    const removalTargets = this.getBrowserAssetRemovalTargets(target);
    const removedPaths = [];

    for (const candidate of removalTargets) {
      if (!candidate || !fs.existsSync(candidate)) {
        continue;
      }
      fs.rmSync(candidate, { recursive: true, force: true });
      removedPaths.push(candidate);
    }

    if (target === 'firefox') {
      const nextPreferences = this.normalizePlatformBrowserPreferences(
        this.runtimeSettings.platformBrowserPreferences
      );
      let preferencesChanged = false;

      for (const platform of Object.keys(nextPreferences)) {
        if (nextPreferences[platform] === 'firefox') {
          nextPreferences[platform] = 'chromium';
          preferencesChanged = true;
        }
      }

      if (preferencesChanged) {
        this.saveRuntimeSettings({
          platformBrowserPreferences: nextPreferences
        });
      }
    }

    return {
      success: true,
      removedPaths,
      browserRuntimeInfo: this.getBrowserRuntimeInfo()
    };
  }

  runManagedCommand(command, args, options = {}) {
    const { cwd = this.getResourcesRoot(), env = process.env, logPrefix = 'command' } = options;

    return new Promise((resolve) => {
      let stdout = '';
      let stderr = '';
      let settled = false;

      const child = spawn(command, args, {
        cwd,
        env,
        windowsHide: true
      });

      const finish = (result) => {
        if (settled) {
          return;
        }
        settled = true;
        resolve(result);
      };

      child.stdout?.on('data', (chunk) => {
        const text = chunk.toString();
        stdout += text;
        log.info(`[${logPrefix}] ${text.trimEnd()}`);
      });

      child.stderr?.on('data', (chunk) => {
        const text = chunk.toString();
        stderr += text;
        log.warn(`[${logPrefix}] ${text.trimEnd()}`);
      });

      child.on('error', (error) => {
        finish({
          success: false,
          code: -1,
          stdout,
          stderr,
          error: error.message
        });
      });

      child.on('close', (code) => {
        finish({
          success: code === 0,
          code,
          stdout,
          stderr,
          error: code === 0 ? null : (stderr.trim() || stdout.trim() || `command_failed:${code}`)
        });
      });
    });
  }

  async installBrowserComponent(target) {
    const allowedTargets = new Set(['chromium', 'firefox', 'patchright', 'playwright']);
    if (!allowedTargets.has(target)) {
      return { success: false, error: `unsupported_target:${target}` };
    }

    const pythonPath = this.getPythonPath();
    const browsersRoot = this.getBrowsersRoot();
    fs.mkdirSync(browsersRoot, { recursive: true });

    const env = this.buildPythonEnv({
      ...process.env,
      PLAYWRIGHT_BROWSERS_PATH: browsersRoot,
      SYNAPSE_PLAYWRIGHT_RUNTIME: this.runtimeSettings.automationRuntime
    });

    if (target === 'patchright' || target === 'playwright') {
      const runtime = this.getPythonRuntime();
      if (runtime.source !== 'synenv') {
        return {
          success: false,
          output: '',
          error: `packaged_python_unavailable:${runtime.error || runtime.source}`,
          browserRuntimeInfo: this.getBrowserRuntimeInfo()
        };
      }

      const conflictingRuntime = target === 'patchright' ? 'playwright' : 'patchright';
      const conflictingInfo = this.mergeRuntimeInfo(
        this.getPythonPackageInfo(conflictingRuntime),
        this.getPackagedWorkerRuntimeInfo(conflictingRuntime)
      );
      if (conflictingInfo.installed) {
        const uninstallResult = await this.runManagedCommand(
          pythonPath,
          ['-m', 'pip', 'uninstall', '-y', conflictingRuntime],
          { env, logPrefix: `pip:remove:${conflictingRuntime}` }
        );

        if (!uninstallResult.success) {
          return {
            success: false,
            output: uninstallResult.stdout,
            error: uninstallResult.error,
            browserRuntimeInfo: this.getBrowserRuntimeInfo()
          };
        }
      }

      const result = await this.runManagedCommand(
        pythonPath,
        ['-m', 'pip', 'install', target],
        { env, logPrefix: `pip:${target}` }
      );

      return {
        success: result.success,
        output: result.stdout,
        error: result.error,
        browserRuntimeInfo: this.getBrowserRuntimeInfo()
      };
    }

    if (target === 'chromium') {
      const installResult = await this.installHibbikiChromium();
      return {
        success: installResult.success,
        output: installResult.stdout,
        error: installResult.error,
        browserRuntimeInfo: this.getBrowserRuntimeInfo()
      };
    }

    const patchrightInfo = this.getPythonPackageInfo('patchright');
    if (!patchrightInfo.installed) {
      const runtimeInstall = await this.runManagedCommand(
        pythonPath,
        ['-m', 'pip', 'install', '--upgrade', '--force-reinstall', 'patchright==1.59.1'],
        { env, logPrefix: 'pip:patchright' }
      );

      if (!runtimeInstall.success) {
        return {
          success: false,
          output: runtimeInstall.stdout,
          error: runtimeInstall.error,
          browserRuntimeInfo: this.getBrowserRuntimeInfo()
        };
      }
    }

    const preferredRuntime = (this.runtimeSettings.automationRuntime === 'playwright') ? 'playwright' : 'patchright';
    const installCommand = preferredRuntime === 'playwright'
      ? ['-m', 'playwright', 'install', target]
      : ['-m', 'patchright', 'install', target];

    const installResult = await this.runManagedCommand(
      pythonPath,
      installCommand,
      { env, logPrefix: `${preferredRuntime}:${target}` }
    );

    return {
      success: installResult.success,
      output: installResult.stdout,
      error: installResult.error,
      browserRuntimeInfo: this.getBrowserRuntimeInfo()
    };
  }

  getAppIconPath() {
    return this.resolveFirstPath([
      path.join(app.getAppPath(), 'icon.ico'),
      path.join(process.resourcesPath, 'icon.ico'),
      path.join(__dirname, '..', '..', 'icon.ico')
    ]);
  }

  setupTray() {
    if (this.tray || !this.appIconPath) {
      return;
    }

    this.tray = new Tray(this.appIconPath);
    this.tray.setToolTip('SynapseAutomation');
    this.refreshTrayMenu();

    this.tray.on('click', () => {
      this.showMainWindow();
    });

    this.tray.on('double-click', () => {
      this.showMainWindow();
    });
  }

  refreshTrayMenu() {
    if (!this.tray) {
      return;
    }

    this.tray.setContextMenu(Menu.buildFromTemplate([
      {
        label: 'Open main window',
        click: () => this.showMainWindow()
      },
      {
        label: 'Open settings',
        click: () => this.createSettingsWindow()
      },
      {
        label: 'Restart application and all processes',
        click: () => {
          void this.restartApplication();
        }
      },
      { type: 'separator' },
      {
        label: 'Quit and stop all processes',
        click: () => {
          void this.quitApplication();
        }
      }
    ]));
  }

  showMainWindow() {
    if (!this.mainWindow || this.mainWindow.isDestroyed()) {
      this.createMainWindow();
      return;
    }

    if (this.mainWindow.isMinimized()) {
      this.mainWindow.restore();
    }

    this.mainWindow.show();
    this.mainWindow.focus();
  }

  async requestSupervisor(pathname, method = 'GET', timeoutMs = 20000) {
    const http = require('http');

    return new Promise((resolve, reject) => {
      const req = http.request({
        hostname: '127.0.0.1',
        port: 7002,
        path: pathname,
        method
      }, (res) => {
        let data = '';

        res.on('data', (chunk) => {
          data += chunk;
        });

        res.on('end', () => {
          try {
            resolve(data ? JSON.parse(data) : {});
          } catch (error) {
            reject(error);
          }
        });
      });

      req.on('error', reject);
      req.setTimeout(timeoutMs, () => {
        req.destroy();
        reject(new Error(`Supervisor request timeout: ${pathname}`));
      });
      req.end();
    });
  }

  syncManagedServicePortsFromStatus(statusPayload) {
    const status = statusPayload?.data || statusPayload || {};
    const backendStatus = status.backend || {};
    const workerStatus = status.playwright_worker || status.worker || {};
    const parsePort = (value) => {
      const parsed = Number.parseInt(String(value || ''), 10);
      return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
    };

    const nextBackendPort = parsePort(backendStatus.port);
    const nextWorkerPort = parsePort(workerStatus.port);

    if (nextBackendPort && nextBackendPort !== this.backendPort) {
      log.info(`Syncing backend port from supervisor status: ${this.backendPort || 'unset'} -> ${nextBackendPort}`);
      this.backendPort = nextBackendPort;
    }

    if (nextWorkerPort && nextWorkerPort !== this.playwrightWorkerPort) {
      log.info(`Syncing playwright-worker port from supervisor status: ${this.playwrightWorkerPort || 'unset'} -> ${nextWorkerPort}`);
      this.playwrightWorkerPort = nextWorkerPort;
    }

    if (nextBackendPort) {
      const backendUrl = this.getBackendBaseUrl();
      const backendApiBaseUrl = this.getBackendApiBaseUrl();
      process.env.BACKEND_PORT = String(this.getBackendPort());
      process.env.SYN_BACKEND_PORT = process.env.BACKEND_PORT;
      process.env.SYN_BACKEND_URL = backendUrl;
      process.env.NEXT_PUBLIC_SYN_BACKEND_URL = backendUrl;
      process.env.NEXT_PUBLIC_BACKEND_URL = backendUrl;
      process.env.NEXT_PUBLIC_API_URL = backendUrl;
      process.env.MANUS_API_BASE_URL = backendApiBaseUrl;
      process.env.AGENT_API_BASE_URL = backendApiBaseUrl;
    }

    if (nextWorkerPort) {
      process.env.PLAYWRIGHT_WORKER_PORT = String(this.getPlaywrightWorkerPort());
      process.env.SYN_PLAYWRIGHT_WORKER_PORT = process.env.PLAYWRIGHT_WORKER_PORT;
    }

    return status;
  }

  async getSupervisorStatus(timeoutMs = 5000) {
    const statusPayload = await this.requestSupervisor('/api/status', 'GET', timeoutMs);
    this.syncManagedServicePortsFromStatus(statusPayload);
    return statusPayload;
  }

  async requestSupervisorRestartAll(timeoutMs = 30000) {
    let lastError = null;

    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        return await this.requestSupervisor('/api/restart', 'POST', timeoutMs);
      } catch (error) {
        lastError = error;
        const message = String(error?.message || '');
        const isTimeout = message.includes('Supervisor request timeout: /api/restart');

        if (!isTimeout) {
          throw error;
        }

        log.warn(`Supervisor restart request timed out on attempt ${attempt + 1}; probing restart state...`);

        try {
          const restartState = await this.requestSupervisor('/api/restart-status', 'GET', 5000);
          if (restartState?.data?.restart_in_progress) {
            return { status: 'accepted', message: 'Restart already in progress' };
          }
        } catch (probeError) {
          log.warn('Failed to probe supervisor restart state after timeout:', probeError);
        }

        if (attempt === 0) {
          await new Promise((resolve) => setTimeout(resolve, 1500));
        }
      }
    }

    throw lastError || new Error('Supervisor restart request failed');
  }

  async waitForSupervisorServices(timeoutMs = 60000, pollIntervalMs = 1000) {
    const deadline = Date.now() + timeoutMs;

    while (Date.now() < deadline) {
      try {
        const restartState = await this.requestSupervisor('/api/restart-status', 'GET', 5000);
        const statusPayload = await this.getSupervisorStatus(5000);
        const status = statusPayload?.data || {};
        const isServiceReady = (service, { allowDisabled = false, optional = false } = {}) => {
          if (!service) {
            return optional;
          }
          if (service.running || service.external) {
            return true;
          }
          if (allowDisabled && (service.configured === false || service.source === 'disabled')) {
            return true;
          }
          return false;
        };

        const backendReady = isServiceReady(status.backend);
        const workerReady = isServiceReady(status.playwright_worker || status.worker);
        const celeryReady = isServiceReady(status.celery_worker || status.celery);
        const restartInProgress = Boolean(restartState?.data?.restart_in_progress);

        // Hermes sidecars are non-blocking for desktop startup. They may be
        // absent, disabled, or recover asynchronously, but the packaged app
        // should still finish booting once the core automation stack is ready.
        if (
          backendReady &&
          workerReady &&
          celeryReady &&
          !restartInProgress
        ) {
          return true;
        }
      } catch (error) {
        log.warn('Waiting for supervisor services failed; retrying...', error);
      }

      await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
    }

    throw new Error('Timed out waiting for supervisor services to become healthy');
  }

  async stopManagedServices() {
    if (this.supervisorProcess && !this.supervisorProcess.killed) {
      try {
        await this.requestSupervisor('/api/stop', 'POST');
      } catch (error) {
        log.warn('Failed to stop managed services via supervisor API:', error);
      }
    }

    this.cleanup();
  }

  async restartManagedServices() {
    log.info('Restarting managed service stack...');
    await this.stopManagedServices();
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await this.startServices();
    this.servicesStarted = true;
    log.info('Managed service stack restarted successfully');
    return { success: true };
  }

  async quitApplication() {
    if (this.isQuitting) {
      return { success: true };
    }

    this.isQuitting = true;
    this.isRestarting = false;
    log.info('Quitting application and stopping all processes...');

    try {
      await this.stopManagedServices();
      if (this.tray) {
        this.tray.destroy();
        this.tray = null;
      }
      app.quit();
      return { success: true };
    } catch (error) {
      this.isQuitting = false;
      log.error('Failed to quit application cleanly:', error);
      return { success: false, error: error.message };
    }
  }

  scheduleAppRestart() {
    const relaunchEnv = {
      ...process.env,
      PLAYWRIGHT_HEADLESS: this.runtimeSettings.browserHeadless ? 'true' : 'false',
      SYNAPSE_PLAYWRIGHT_RUNTIME: this.runtimeSettings.automationRuntime
    };
    this.applyPlatformBrowserPreferenceEnv(relaunchEnv, this.runtimeSettings.platformBrowserPreferences || {});

    if (this.isDev) {
      relaunchEnv.SYNAPSE_START_SERVICES = process.env.SYNAPSE_START_SERVICES || '1';
      relaunchEnv.SYNAPSE_START_FRONTEND = process.env.SYNAPSE_START_FRONTEND || '1';

      const appPath = app.getAppPath();
      const child = spawn(process.execPath, [appPath], {
        cwd: appPath,
        env: relaunchEnv,
        detached: true,
        stdio: 'ignore',
        windowsHide: true
      });
      child.unref();
      log.info('Scheduled dev app restart via detached Electron process');
      return;
    }

    app.relaunch({
      execPath: process.execPath,
      args: process.argv.slice(1)
    });
    log.info('Scheduled packaged app restart via app.relaunch');
  }

  async restartApplication() {
    if (this.isQuitting) {
      return { success: true };
    }

    this.isQuitting = true;
    this.isRestarting = true;
    log.info('Restarting application and stopping all processes...');

    try {
      this.scheduleAppRestart();
      await this.stopManagedServices();
      if (this.tray) {
        this.tray.destroy();
        this.tray = null;
      }
      app.exit(0);
      return { success: true };
    } catch (error) {
      this.isQuitting = false;
      this.isRestarting = false;
      log.error('Failed to restart application cleanly:', error);
      return { success: false, error: error.message };
    }
  }

  getServiceExe(name) {
    if (this.isDev) {
      return null;
    }
    const candidates = [
      path.join(process.resourcesPath, 'services', name, `${name}.exe`),
      path.join(process.resourcesPath, 'services', `${name}.exe`)
    ];
    return this.resolveFirstPath(candidates) || null;
  }

  buildServiceEnv() {
    const browsersRoot = this.getBrowsersRoot();
    const backendUrl = this.getBackendBaseUrl();
    const backendApiBaseUrl = this.getBackendApiBaseUrl();
    const backendPort = String(this.getBackendPort());
    const playwrightWorkerPort = String(this.getPlaywrightWorkerPort());
    const pythonPath = this.getPythonPath();
    log.info('Preparing service environment...');
    log.info('  - Browsers Root:', browsersRoot);
    log.info('  - Browsers Root exists:', fs.existsSync(browsersRoot));

    const appRoot = this.getResourcesRoot();
    const env = {
      ...process.env,
      PYTHONUTF8: '1',
      PYTHONIOENCODING: 'utf-8',
      SYNAPSE_APP_ROOT: appRoot,
      SYNAPSE_RESOURCES_PATH: appRoot,
      SYNAPSE_HERMES_PYTHON: pythonPath,
      SYNAPSE_RUNTIME_SETTINGS_PATH: this.getRuntimeSettingsPath(),
      PLAYWRIGHT_BROWSERS_PATH: browsersRoot,
      PLAYWRIGHT_HEADLESS: this.runtimeSettings.browserHeadless ? 'true' : 'false',
      SYNAPSE_PLAYWRIGHT_RUNTIME: this.runtimeSettings.automationRuntime,
      BACKEND_PORT: backendPort,
      SYN_BACKEND_PORT: backendPort,
      PLAYWRIGHT_WORKER_PORT: playwrightWorkerPort,
      SYN_PLAYWRIGHT_WORKER_PORT: playwrightWorkerPort,
      SYN_BACKEND_URL: backendUrl,
      NEXT_PUBLIC_SYN_BACKEND_URL: backendUrl,
      NEXT_PUBLIC_BACKEND_URL: backendUrl,
      NEXT_PUBLIC_API_URL: backendUrl,
      MANUS_API_BASE_URL: backendApiBaseUrl,
      AGENT_API_BASE_URL: backendApiBaseUrl
    };
    const pythonEnv = this.buildPythonEnv(env);
    Object.assign(env, pythonEnv);
    this.applyPlatformBrowserPreferenceEnv(env, this.runtimeSettings.platformBrowserPreferences || {});
    if (!env.SYNAPSE_DATA_DIR) {
      if (this.isDev) {
        const devDataDir = path.join(this.repoRoot, 'syn_backend');
        env.SYNAPSE_DATA_DIR = devDataDir;
        log.info('  - SYNAPSE_DATA_DIR (dev):', devDataDir);
      } else {
        const userDataDir = app.getPath('userData');
        const dataDir = path.join(userDataDir, 'data');
        if (!fs.existsSync(dataDir)) {
          fs.mkdirSync(dataDir, { recursive: true });
        }
        env.SYNAPSE_DATA_DIR = dataDir;
        const hermesRoot = path.join(userDataDir, 'hermes');
        const hermesHome = path.join(hermesRoot, 'home');
        const hermesWebUiState = path.join(hermesRoot, 'webui');
        const hermesWorkspace = path.join(hermesRoot, 'workspace');
        const hermesConfigRoot = path.join(userDataDir, 'config');
        [hermesHome, hermesWebUiState, hermesWorkspace, hermesConfigRoot].forEach((dirPath) => {
          if (!fs.existsSync(dirPath)) {
            fs.mkdirSync(dirPath, { recursive: true });
          }
        });
        env.SYNAPSE_HERMES_HOME = hermesHome;
        env.SYNAPSE_HERMES_WEBUI_STATE_DIR = hermesWebUiState;
        env.SYNAPSE_HERMES_WORKSPACE = hermesWorkspace;
        env.SYNAPSE_HERMES_CONFIG_ROOT = hermesConfigRoot;
        log.info('  - SYNAPSE_DATA_DIR:', dataDir);
      }
    }
    if (!env.PLAYWRIGHT_AUTO_INSTALL) {
      env.PLAYWRIGHT_AUTO_INSTALL = this.isDev ? '1' : '0';
    }
    if (!env.ENABLE_OCR_RESCUE) {
      env.ENABLE_OCR_RESCUE = '1';
    }
    if (!env.ENABLE_SELENIUM_RESCUE) {
      env.ENABLE_SELENIUM_RESCUE = '1';
    }
    if (!env.ENABLE_SELENIUM_DEBUG) {
      env.ENABLE_SELENIUM_DEBUG = '1';
    }

    const chromePath = this.resolveChromePath(browsersRoot);
    if (chromePath) {
      env.LOCAL_CHROME_PATH = chromePath;
      log.info('  - Chrome Path:', chromePath);
    } else {
      log.warn('  - Chrome Path: NOT FOUND');
    }

    const firefoxPath = this.resolveFirefoxPath(browsersRoot);
    if (firefoxPath) {
      env.LOCAL_FIREFOX_PATH = firefoxPath;
      log.info('  - Firefox Path:', firefoxPath);
    } else {
      log.warn('  - Firefox Path: NOT FOUND');
    }

    log.info('Service environment prepared');
    return env;
  }

  isPortInUse(port, host = '127.0.0.1', timeoutMs = 500) {
    return new Promise((resolve) => {
      const socket = new net.Socket();
      let settled = false;

      const finish = (inUse) => {
        if (settled) {
          return;
        }
        settled = true;
        socket.destroy();
        resolve(inUse);
      };

      socket.setTimeout(timeoutMs);
      socket.once('connect', () => finish(true));
      socket.once('timeout', () => finish(false));
      socket.once('error', () => finish(false));
      socket.connect(port, host);
    });
  }

  canBindPort(port, host = '127.0.0.1') {
    return new Promise((resolve) => {
      const server = net.createServer();
      let settled = false;

      const finish = (result) => {
        if (settled) {
          return;
        }
        settled = true;
        try {
          server.close(() => resolve(result));
        } catch (error) {
          resolve(result);
        }
      };

      server.once('error', () => finish(false));
      server.once('listening', () => finish(true));
      server.listen({
        host,
        port,
        exclusive: true
      });
    });
  }

  requestLocalJson(port, pathName, timeoutMs = 2000) {
    const http = require('http');

    return new Promise((resolve, reject) => {
      const req = http.request({
        hostname: '127.0.0.1',
        port,
        path: pathName,
        method: 'GET'
      }, (res) => {
        let data = '';

        res.on('data', (chunk) => {
          data += chunk;
        });

        res.on('end', () => {
          try {
            resolve(data ? JSON.parse(data) : {});
          } catch (error) {
            reject(error);
          }
        });
      });

      req.on('error', reject);
      req.setTimeout(timeoutMs, () => {
        req.destroy();
        reject(new Error(`Local request timeout: ${port}${pathName}`));
      });
      req.end();
    });
  }

  async isSynapseBackendOnPort(port) {
    if (!(await this.isPortInUse(port))) {
      return false;
    }

    try {
      const payload = await this.requestLocalJson(port, '/health', 2000);
      return String(payload?.status || '').toLowerCase() === 'healthy' && Boolean(payload?.version);
    } catch (error) {
      return false;
    }
  }

  async isPlaywrightWorkerOnPort(port) {
    if (!(await this.isPortInUse(port))) {
      return false;
    }

    try {
      const payload = await this.requestLocalJson(port, '/health', 2000);
      return String(payload?.status || '').toLowerCase() === 'ok' && payload?.service === 'playwright-worker';
    } catch (error) {
      return false;
    }
  }

  async prepareManagedServicePorts() {
    const configuredWorkerPort = this.getConfiguredPlaywrightWorkerPort();
    const configuredBackendPort = this.getConfiguredBackendPort();
    const reservedPorts = new Set();

    this.backendPort = await this.resolveManagedPort(
      configuredBackendPort,
      this.isSynapseBackendOnPort.bind(this),
      reservedPorts
    );
    reservedPorts.add(this.backendPort);

    this.playwrightWorkerPort = await this.resolveManagedPort(
      configuredWorkerPort,
      this.isPlaywrightWorkerOnPort.bind(this),
      reservedPorts
    );

    log.info('Managed service ports prepared:', {
      backendPort: this.backendPort,
      playwrightWorkerPort: this.playwrightWorkerPort
    });
  }

  listListeningPidsByPort(port) {
    if (process.platform !== 'win32') {
      return [];
    }

    try {
      const psCommand = [
        '$ErrorActionPreference = "SilentlyContinue"',
        `$pids = Get-NetTCPConnection -State Listen -LocalPort ${Number(port)} | Select-Object -ExpandProperty OwningProcess -Unique`,
        'if ($pids) { $pids | ConvertTo-Json -Compress }'
      ].join('; ');
      const result = spawnSync('powershell.exe', ['-NoProfile', '-Command', psCommand], {
        encoding: 'utf8',
        windowsHide: true
      });

      if (result.error || result.status !== 0) {
        return [];
      }

      const raw = String(result.stdout || '').trim();
      if (!raw) {
        return [];
      }

      const parsed = JSON.parse(raw);
      const values = Array.isArray(parsed) ? parsed : [parsed];
      return values
        .map((value) => Number.parseInt(value, 10))
        .filter((value) => Number.isInteger(value) && value > 0);
    } catch (error) {
      log.warn(`Failed to inspect listening PIDs on port ${port}:`, error);
      return [];
    }
  }

  getSupervisorResourceMarkers() {
    const candidates = [
      path.join(process.resourcesPath, 'supervisor'),
      path.join(this.repoRoot, 'desktop-electron', 'resources', 'supervisor')
    ];

    return [...new Set(
      candidates
        .filter(Boolean)
        .map((candidate) => path.normalize(candidate).toLowerCase())
    )];
  }

  getManagedServiceResourceMarkers() {
    const candidates = [
      this.repoRoot,
      path.join(this.repoRoot, 'syn_backend'),
      path.join(this.repoRoot, 'tools', 'hermes-agent'),
      path.join(this.repoRoot, 'tools', 'hermes-webui'),
      path.join(process.resourcesPath, 'syn_backend'),
      path.join(process.resourcesPath, 'tools', 'hermes-agent'),
      path.join(process.resourcesPath, 'tools', 'hermes-webui'),
      path.join(process.resourcesPath, 'services', 'backend'),
      path.join(process.resourcesPath, 'supervisor'),
      path.join(this.repoRoot, 'desktop-electron', 'resources', 'supervisor')
    ];

    return [...new Set(
      candidates
        .filter(Boolean)
        .map((candidate) => path.normalize(candidate).toLowerCase())
    )];
  }

  listRepoManagedServicePids() {
    if (process.platform !== 'win32') {
      return [];
    }

    try {
      const markers = this.getManagedServiceResourceMarkers()
        .map((marker) => `'${marker.replace(/'/g, "''")}'`)
        .join(', ');
      const psCommand = [
        '$ErrorActionPreference = "SilentlyContinue"',
        `$markers = @(${markers})`,
        '$keywords = @(',
        "  'fastapi_app\\\\run.py',",
        "  'playwright_worker\\\\worker.py',",
        "  'tools\\\\hermes-webui\\\\server.py',",
        "  'hermes_cli.main',",
        "  'celery_app',",
        "  'supervisor.py'",
        ')',
        '$pids = Get-CimInstance Win32_Process | Where-Object {',
        '  $name = [string]$_.Name',
        '  $cmd = [string]$_.CommandLine',
        '  $exe = [string]$_.ExecutablePath',
        '  $cmdLower = $cmd.ToLower()',
        '  $exeLower = $exe.ToLower()',
        '  $belongsToRepo = $false',
        '  foreach ($marker in $markers) {',
        '    if (($cmdLower -and $cmdLower.Contains($marker)) -or ($exeLower -and $exeLower.Contains($marker))) {',
        '      $belongsToRepo = $true',
        '      break',
        '    }',
        '  }',
        '  if (-not $belongsToRepo) { return $false }',
        "  $serviceByName = $name.ToLower() -in @('backend.exe', 'supervisor.exe')",
        '  $serviceByCommand = $false',
        '  foreach ($keyword in $keywords) {',
        '    if ($cmdLower -and $cmdLower.Contains($keyword)) {',
        '      $serviceByCommand = $true',
        '      break',
        '    }',
        '  }',
        '  $serviceByName -or $serviceByCommand',
        '} | Select-Object -ExpandProperty ProcessId -Unique',
        'if ($pids) { $pids | ConvertTo-Json -Compress }'
      ].join('; ');
      const result = spawnSync('powershell.exe', ['-NoProfile', '-Command', psCommand], {
        encoding: 'utf8',
        windowsHide: true
      });

      if (result.error || result.status !== 0) {
        return [];
      }

      const raw = String(result.stdout || '').trim();
      if (!raw) {
        return [];
      }

      const parsed = JSON.parse(raw);
      const values = Array.isArray(parsed) ? parsed : [parsed];
      return values
        .map((value) => Number.parseInt(value, 10))
        .filter((value) => Number.isInteger(value) && value > 0);
    } catch (error) {
      log.warn('Failed to inspect repo managed service processes:', error);
      return [];
    }
  }

  listRepoSupervisorPids() {
    if (process.platform !== 'win32') {
      return [];
    }

    try {
      const markers = this.getSupervisorResourceMarkers()
        .map((marker) => `'${marker.replace(/'/g, "''")}'`)
        .join(', ');
      const psCommand = [
        '$ErrorActionPreference = "SilentlyContinue"',
        `$markers = @(${markers})`,
        '$pids = Get-CimInstance Win32_Process | Where-Object {',
        '  $name = [string]$_.Name',
        '  $cmd = [string]$_.CommandLine',
        '  $exe = [string]$_.ExecutablePath',
        '  $belongsToRepo = $false',
        '  foreach ($marker in $markers) {',
        '    if (($cmd -and $cmd.ToLower().Contains($marker)) -or ($exe -and $exe.ToLower().Contains($marker))) {',
        '      $belongsToRepo = $true',
        '      break',
        '    }',
        '  }',
        "  $looksLikeSupervisor = ($name.ToLower() -eq 'supervisor.exe') -or (($name.ToLower().StartsWith('python')) -and $cmd -and $cmd.ToLower().Contains('supervisor.py'))",
        '  $belongsToRepo -and $looksLikeSupervisor',
        '} | Select-Object -ExpandProperty ProcessId -Unique',
        'if ($pids) { $pids | ConvertTo-Json -Compress }'
      ].join('; ');
      const result = spawnSync('powershell.exe', ['-NoProfile', '-Command', psCommand], {
        encoding: 'utf8',
        windowsHide: true
      });

      if (result.error || result.status !== 0) {
        return [];
      }

      const raw = String(result.stdout || '').trim();
      if (!raw) {
        return [];
      }

      const parsed = JSON.parse(raw);
      const values = Array.isArray(parsed) ? parsed : [parsed];
      return values
        .map((value) => Number.parseInt(value, 10))
        .filter((value) => Number.isInteger(value) && value > 0);
    } catch (error) {
      log.warn('Failed to inspect repo supervisor processes:', error);
      return [];
    }
  }

  getProcessDetails(pid) {
    if (process.platform !== 'win32' || !Number.isInteger(pid) || pid <= 0) {
      return null;
    }

    try {
      const psCommand = [
        '$ErrorActionPreference = "SilentlyContinue"',
        `$proc = Get-CimInstance Win32_Process -Filter "ProcessId = ${pid}"`,
        'if ($proc) {',
        '  [PSCustomObject]@{',
        '    processId = $proc.ProcessId',
        '    name = $proc.Name',
        '    executablePath = $proc.ExecutablePath',
        '    commandLine = $proc.CommandLine',
        '  } | ConvertTo-Json -Compress',
        '}'
      ].join('; ');
      const result = spawnSync('powershell.exe', ['-NoProfile', '-Command', psCommand], {
        encoding: 'utf8',
        windowsHide: true
      });

      if (result.error || result.status !== 0) {
        return null;
      }

      const raw = String(result.stdout || '').trim();
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      log.warn(`Failed to inspect process details for PID ${pid}:`, error);
      return null;
    }
  }

  terminateProcessByPid(pid) {
    if (!Number.isInteger(pid) || pid <= 0) {
      return false;
    }

    try {
      execSync(`taskkill /F /T /PID ${pid}`, { stdio: 'ignore' });
      return true;
    } catch (error) {
      log.warn(`Failed to terminate PID ${pid}:`, error);
      return false;
    }
  }

  cleanupStaleSupervisorOnPort(port = 7002) {
    const candidatePids = new Set(this.listRepoSupervisorPids());
    for (const pid of this.listListeningPidsByPort(port)) {
      candidatePids.add(pid);
    }

    if (candidatePids.size === 0) {
      return;
    }

    const repoMarkers = this.getSupervisorResourceMarkers();
    const terminated = [];

    for (const pid of candidatePids) {
      const details = this.getProcessDetails(pid);
      const commandLine = String(details?.commandLine || '').toLowerCase();
      const executablePath = path.normalize(String(details?.executablePath || '')).toLowerCase();
      const isSupervisorProcess = commandLine.includes('supervisor') || executablePath.includes('supervisor');
      const belongsToRepo = repoMarkers.some((marker) => commandLine.includes(marker) || executablePath.includes(marker));

      if (!isSupervisorProcess || !belongsToRepo) {
        continue;
      }

      if (this.terminateProcessByPid(pid)) {
        terminated.push(pid);
      }
    }

    if (terminated.length > 0) {
      log.warn(`Terminated stale repo supervisor process(es) before startup: ${terminated.join(', ')}`);
    }
  }

  cleanupStaleManagedServices() {
    const terminated = [];

    for (const pid of this.listRepoManagedServicePids()) {
      if (this.terminateProcessByPid(pid)) {
        terminated.push(pid);
      }
    }

    if (terminated.length > 0) {
      log.warn(`Terminated stale repo managed service process(es) before startup: ${terminated.join(', ')}`);
    }
  }

  async startServices() {
    if (this.servicesStarted) {
      return;
    }

    this.cleanupStaleManagedServices();
    await this.prepareManagedServicePorts();
    console.log('Using supervisor to manage backend services...');
    log.info('Using supervisor to manage backend services...');
    this.startSupervisor();
    await this.waitForSupervisorServices(90000, 1500);
    await this.startFrontend(this.buildServiceEnv());
    this.servicesStarted = true;
  }

  startSupervisor() {
    if (this.supervisorProcess) {
      return;
    }

    this.ensureSynenvConfig();
    this.cleanupStaleSupervisorOnPort(7002);
    const supervisorPaths = this.getSupervisorPaths();
    const supervisorExe = supervisorPaths.exePath;
    const supervisorScript = supervisorPaths.scriptPath;
    const pythonPath = this.getPythonPath();

    console.log('Supervisor exe:', supervisorExe);
    console.log('Supervisor script:', supervisorScript);
    log.info('Starting supervisor...');
    log.info('  - Supervisor exe:', supervisorExe);
    log.info('  - Supervisor script:', supervisorScript);
    log.info('  - Supervisor cwd:', supervisorPaths.cwd);
    log.info('  - Exe exists:', Boolean(supervisorExe && fs.existsSync(supervisorExe)));
    log.info('  - Script exists:', Boolean(supervisorScript && fs.existsSync(supervisorScript)));

    if (!supervisorExe && !supervisorScript) {
      throw new Error('Supervisor entrypoint not found in packaged resources or desktop-electron/resources/supervisor');
    }

    const launchCmd = supervisorExe || pythonPath;
    const launchArgs = supervisorExe ? [] : [supervisorScript];

    console.log('Supervisor launch command:', launchCmd, launchArgs);
    log.info('  - Launch Command:', launchCmd);
    log.info('  - Launch Args:', launchArgs);

    // 鏋勫缓鐜鍙橀噺
    const env = this.buildServiceEnv();

    this.supervisorProcess = spawn(launchCmd, launchArgs, {
      cwd: supervisorPaths.cwd || this.getResourcesRoot(),
      env: env,
      windowsHide: true
    });

    this.supervisorProcess.on('error', (error) => {
      console.error('Supervisor failed to start:', error);
      log.error('Supervisor failed to start:', error);
    });

    this.supervisorProcess.stdout?.on('data', (data) => {
      console.log('[Supervisor]', data.toString());
      log.info('[Supervisor]', data.toString());
    });

    this.supervisorProcess.stderr?.on('data', (data) => {
      console.error('[Supervisor Error]', data.toString());
      log.error('[Supervisor Error]', data.toString());
    });

    this.supervisorProcess.on('exit', (code) => {
      console.warn(`Supervisor exited with code: ${code}`);
      log.warn(`Supervisor exited with code: ${code}`);
      this.supervisorProcess = null;
    });

    console.log('Supervisor started');
    log.info('Supervisor started');
  }

  async startRedis(env) {
    if (this.redisProcess) {
      return;
    }
    const redisPath = this.isDev
      ? (process.env.SYNAPSE_REDIS_PATH || 'redis-server')
      : path.join(process.resourcesPath, 'redis', 'redis-server.exe');

    log.info('Starting Redis...');
    log.info('  - Redis Path:', redisPath);
    log.info('  - Redis exists:', fs.existsSync(redisPath));
    log.info('  - Is Dev:', this.isDev);

    if (await this.isPortInUse(6379)) {
      log.warn('Redis already running on port 6379; skipping start.');
      return;
    }

    if (!this.isDev && !fs.existsSync(redisPath)) {
      log.error(`Redis executable not found: ${redisPath}`);
      return;
    }
    this.redisProcess = spawn(redisPath, [], {
      env,
      cwd: this.getResourcesRoot(),
      windowsHide: true
    });
    this.redisProcess.on('error', (error) => {
      log.error('Redis failed to start:', error);
      this.redisProcess = null;
    });
    this.redisProcess.stdout?.on('data', (data) => log.info('[Redis]', data.toString()));
    this.redisProcess.stderr?.on('data', (data) => log.error('[Redis Error]', data.toString()));
    this.redisProcess.on('exit', (code) => {
      log.warn(`Redis exited with code: ${code}`);
    });
  }

  async startPlaywrightWorker(env) {
    if (this.playwrightWorkerProcess) {
      return;
    }
    if (!this.playwrightWorkerPort) {
      await this.prepareManagedServicePorts();
    }
    const workerPort = this.getPlaywrightWorkerPort();
    if (await this.isPlaywrightWorkerOnPort(workerPort)) {
      log.warn(`Playwright Worker already running on port ${workerPort}; skipping start.`);
      return;
    }
    const backendDir = this.getBackendDir();
    const workerExe = this.getServiceExe('playwright-worker');
    const workerScript = path.join(backendDir, 'playwright_worker', 'worker.py');

    log.info('Starting Playwright worker...');
    log.info('  - Backend Dir:', backendDir);
    log.info('  - Worker Exe:', workerExe || 'N/A');
    log.info('  - Worker Script:', workerScript);
    log.info('  - Script exists:', fs.existsSync(workerScript));

    if (!workerExe && !fs.existsSync(workerScript)) {
      log.error(`Playwright worker script not found: ${workerScript}`);
      return;
    }
    const pythonPath = this.getPythonPath();
    const launchCmd = workerExe || pythonPath;
    const launchArgs = workerExe ? [] : [workerScript];

    log.info('  - Launch Command:', launchCmd);
    log.info('  - Launch Args:', launchArgs.join(' '));

    this.playwrightWorkerProcess = spawn(launchCmd, launchArgs, {
      env: { ...env, PYTHONPATH: backendDir, PLAYWRIGHT_WORKER_PORT: String(workerPort) },
      cwd: backendDir,
      windowsHide: true
    });
    this.playwrightWorkerProcess.stdout?.on('data', (data) => log.info('[Worker]', data.toString()));
    this.playwrightWorkerProcess.stderr?.on('data', (data) => log.error('[Worker Error]', data.toString()));
    this.playwrightWorkerProcess.on('exit', (code) => {
      log.warn(`Playwright worker exited with code: ${code}`);
    });
  }

  startCelery(env) {
    if (this.celeryProcess) {
      return;
    }
    const backendDir = this.getBackendDir();
    const celeryExe = this.getServiceExe('celery-worker');
    const pythonPath = this.getPythonPath();

    log.info('Starting Celery worker...');
    log.info('  - Backend Dir:', backendDir);
    log.info('  - Celery Exe:', celeryExe || 'N/A');
    log.info('  - Python Path:', pythonPath);

    if (process.platform === 'win32') {
      try {
        const powershellPath = this.resolveFirstPath([
          path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
        ]) || 'powershell.exe';
        const killCmd = "Get-CimInstance Win32_Process | Where-Object { ($_.Name -match 'python|celery-worker') -and ($_.CommandLine -match 'fastapi_app.tasks.celery_app' -or $_.CommandLine -match 'synapse-worker') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }";
        execSync(`"${powershellPath}" -NoProfile -Command "${killCmd}"`, { stdio: 'ignore' });
        log.info('Existing Celery workers stopped (if any).');
      } catch (error) {
        log.warn('Failed to stop existing Celery workers.', error);
      }
    }


    const launchCmd = celeryExe || pythonPath;
    const launchArgs = celeryExe
      ? []
      : [
          '-m',
          'celery',
          '-A',
          'fastapi_app.tasks.celery_app',
          'worker',
          '--loglevel=info',
          '--pool=threads',
          '--concurrency=1000',
          '--hostname=synapse-worker@electron'
        ];

    log.info('  - Launch Command:', launchCmd);
    log.info('  - Launch Args:', launchArgs.join(' '));

    const pythonPathEnv = [backendDir, env.PYTHONPATH].filter(Boolean).join(path.delimiter);
    const celeryEnv = { ...env, PYTHONPATH: pythonPathEnv };
    if (!celeryEnv.PYTHONUTF8) {
      celeryEnv.PYTHONUTF8 = '1';
    }
    if (!celeryEnv.PYTHONIOENCODING) {
      celeryEnv.PYTHONIOENCODING = 'utf-8';
    }
    if (!celeryEnv.FORKED_BY_MULTIPROCESSING) {
      celeryEnv.FORKED_BY_MULTIPROCESSING = '1';
    }
    this.celeryProcess = spawn(launchCmd, launchArgs, {
      env: celeryEnv,
      cwd: backendDir,
      windowsHide: true
    });
    this.celeryProcess.stdout?.on('data', (data) => log.info('[Celery]', data.toString()));
    this.celeryProcess.stderr?.on('data', (data) => log.error('[Celery Error]', data.toString()));
    this.celeryProcess.on('exit', (code) => {
      log.warn(`Celery exited with code: ${code}`);
    });
  }

  async startFrontend(env) {
    log.info('Starting frontend...');
    log.info(`  - this.frontendProcess: ${this.frontendProcess ? 'exists' : 'null'}`);
    log.info(`  - this.isDev: ${this.isDev}`);
    if (this.useExternalStack()) {
      this.frontendPort = this.getPreferredFrontendPort();
      log.info('External stack mode enabled; skipping frontend startup.');
      return;
    }
    const serviceEnv = env || this.buildServiceEnv();
    const preferredFrontendPort = this.getPreferredFrontendPort();

    if (this.frontendProcess) {
      log.info('Frontend process already exists; skipping start.');
      return;
    }

    if (this.isDev) {
      const shouldStartDevFrontend =
        process.env.SYNAPSE_START_FRONTEND === '1' ||
        process.env.SYNAPSE_START_SERVICES === '1';
      if (!shouldStartDevFrontend) {
        log.info('Dev frontend auto-start is disabled; skipping start.');
        return;
      }

      this.frontendPort = await this.findAvailablePort(preferredFrontendPort);

      const frontendDir = path.join(this.repoRoot, 'syn_frontend_react');
      log.info(`  - frontendDir: ${frontendDir}`);
      log.info(`  - frontendPort: ${this.frontendPort}`);

      const nextCli = path.join(frontendDir, 'node_modules', 'next', 'dist', 'bin', 'next');
      const launchCmd = this.getNodeCommand();
      const launchArgs = [nextCli, 'dev', '--webpack'];
      const backendUrl = this.getBackendBaseUrl();
      const frontendEnv = {
        ...serviceEnv,
        NODE_ENV: 'development',
        PORT: String(this.frontendPort),
        HOSTNAME: '127.0.0.1',
        NEXT_PUBLIC_BACKEND_URL: backendUrl,
        NEXT_PUBLIC_API_URL: backendUrl,
        NEXT_PUBLIC_SYN_BACKEND_URL: backendUrl,
        SYN_BACKEND_URL: backendUrl
      };

      log.info('Launching development frontend...');
      this.frontendProcess = spawn(launchCmd, launchArgs, {
        env: frontendEnv,
        cwd: frontendDir,
        windowsHide: true
      });
      this.frontendProcess.stdout?.on('data', (data) => log.info('[Frontend]', data.toString()));
      this.frontendProcess.stderr?.on('data', (data) => log.error('[Frontend Error]', data.toString()));
      this.frontendProcess.on('exit', (code) => {
        log.warn(`Development frontend exited with code: ${code}`);
        this.frontendProcess = null;
      });
      return;
    }

    this.frontendPort = await this.findAvailablePort(preferredFrontendPort);
    const frontendDir = path.join(process.resourcesPath, 'frontend', 'standalone');
    const serverJs = path.join(frontendDir, 'server.js');
    log.info(`  - frontendDir: ${frontendDir}`);
    log.info(`  - serverJs: ${serverJs}`);
    log.info(`  - serverJs exists: ${fs.existsSync(serverJs)}`);
    log.info(`  - frontendPort: ${this.frontendPort}`);

    if (!fs.existsSync(serverJs)) {
      log.warn(`Frontend server entrypoint not found: ${serverJs}`);
      return;
    }
    log.info('Launching packaged frontend...');
    const backendUrl = this.getBackendBaseUrl();
    const frontendEnv = {
      ...serviceEnv,
      ELECTRON_RUN_AS_NODE: '1',
      NODE_ENV: 'production',
      PORT: String(this.frontendPort),
      HOSTNAME: '127.0.0.1',
      NEXT_PUBLIC_BACKEND_URL: backendUrl,
      NEXT_PUBLIC_API_URL: backendUrl,
      NEXT_PUBLIC_SYN_BACKEND_URL: backendUrl,
      SYN_BACKEND_URL: backendUrl,
      NEXT_TELEMETRY_DISABLED: '1'
    };
    this.frontendProcess = spawn(process.execPath, [serverJs], {
      env: frontendEnv,
      cwd: frontendDir,
      windowsHide: true
    });
    this.frontendProcess.stdout?.on('data', (data) => log.info('[Frontend]', data.toString()));
    this.frontendProcess.stderr?.on('data', (data) => log.error('[Frontend Error]', data.toString()));
    this.frontendProcess.on('exit', (code) => {
      log.warn(`Packaged frontend exited with code: ${code}`);
    });
  }


  async startBackend(env) {
    if (this.backendProcess) {
      return;
    }
    if (!this.backendPort) {
      await this.prepareManagedServicePorts();
    }
    const backendPort = this.getBackendPort();
    if (await this.isSynapseBackendOnPort(backendPort)) {
      log.warn(`Backend already running on port ${backendPort}; skipping start.`);
      return;
    }
    const backendDir = this.getBackendDir();
    const backendExe = this.getServiceExe('backend');
    const pythonPath = this.getPythonPath();
    const mainScript = path.join(backendDir, 'fastapi_app', 'run.py');

    log.info('Starting FastAPI backend...');
    log.info('  - Backend Dir:', backendDir);
    log.info('  - Backend Dir exists:', fs.existsSync(backendDir));
    log.info('  - Backend Exe:', backendExe || 'N/A');
    log.info('  - Python Path:', pythonPath);
    log.info('  - Python exists:', fs.existsSync(pythonPath));
    log.info('  - Main Script:', mainScript);
    log.info('  - Script exists:', fs.existsSync(mainScript));

    return new Promise((resolve, reject) => {
      if (!backendExe && !fs.existsSync(mainScript)) {
        log.error(`FastAPI entry script not found: ${mainScript}`);
        resolve();
        return;
      }

      const launchCmd = backendExe || pythonPath;
      const launchArgs = backendExe ? [] : [mainScript];

      log.info('  - Launch Command:', launchCmd);
      log.info('  - Launch Args:', launchArgs.join(' '));

      this.backendProcess = spawn(launchCmd, launchArgs, {
        cwd: backendDir,
        env: {
          ...env,
          PORT: String(backendPort),
          PYTHONPATH: backendDir
        },
        windowsHide: true
      });

      this.backendProcess.stdout?.on('data', (data) => {
        const output = data.toString();
        log.info('[Backend]', output);
        if (output.includes('Uvicorn running') || output.includes('Application startup complete')) {
          log.info('FastAPI backend started successfully');
          resolve();
        }
      });

      this.backendProcess.stderr?.on('data', (data) => {
        log.error('[Backend Error]', data.toString());
      });

      this.backendProcess.on('error', (error) => {
        log.error('Backend process failed to start:', error);
        reject(error);
      });

      this.backendProcess.on('exit', (code) => {
        log.warn(`Backend process exited with code: ${code}`);
      });

      setTimeout(() => {
        log.warn('Backend startup timed out; continuing app launch');
        resolve();
      }, 10000);
    });
  }

  createLauncherWindow() {
    log.info('Creating launcher window...');

    this.launcherWindow = new BrowserWindow({
      width: 800,
      height: 700,
      resizable: false,
      frame: true,
      backgroundColor: '#0a0a0e',
      titleBarStyle: 'default',
      autoHideMenuBar: true,
      icon: this.appIconPath || undefined,
      webPreferences: {
        preload: path.join(__dirname, '../preload/index.js'),
        contextIsolation: true,
        nodeIntegration: false,
        webSecurity: true
      }
    });

    // 鍔犺浇鍚姩绠＄悊鍣ㄩ〉闈?
    const launcherPath = path.join(__dirname, '../launcher/launcher.html');
    log.info('Loading launcher page:', launcherPath);
    this.launcherWindow.loadFile(launcherPath);

    // 绐楀彛鍏抽棴浜嬩欢
    this.launcherWindow.on('closed', () => {
      this.launcherWindow = null;
      log.info('Launcher window closed');
    });

    this.launcherWindow.show();
  }

  createSettingsWindow() {
    log.info('Creating settings window...');

    // 濡傛灉璁剧疆绐楀彛宸插瓨鍦紝鐩存帴鏄剧ず
    if (this.settingsWindow) {
      this.settingsWindow.show();
      this.settingsWindow.focus();
      return;
    }

    this.settingsWindow = new BrowserWindow({
      width: 1200,
      height: 800,
      minWidth: 1000,
      minHeight: 600,
      backgroundColor: '#0a0a0e',
      titleBarStyle: 'default',
      autoHideMenuBar: true,
      icon: this.appIconPath || undefined,
      webPreferences: {
        preload: path.join(__dirname, '../preload/index.js'),
        contextIsolation: true,
        nodeIntegration: false,
        webSecurity: false // 鍏佽璁块棶 localhost API
      }
    });

    // 鍔犺浇璁剧疆椤甸潰
    const settingsPath = path.join(__dirname, '../settings/settings.html');
    log.info('Loading settings page:', settingsPath);
    this.settingsWindow.loadFile(settingsPath);

    // 绐楀彛鍏抽棴浜嬩欢
    this.settingsWindow.on('closed', () => {
      this.settingsWindow = null;
      log.info('Settings window closed');
    });

    this.settingsWindow.show();
  }

  createMainWindow() {
    log.info('Creating main window...');

    this.mainWindow = new BrowserWindow({
      width: 1400,
      height: 900,
      minWidth: 1200,
      minHeight: 700,
      show: false,
      backgroundColor: '#0a0a0e',
      titleBarStyle: 'default',
      autoHideMenuBar: true,
      icon: this.appIconPath || undefined,
      webPreferences: {
        preload: path.join(__dirname, '../preload/index.js'),
        contextIsolation: true,
        nodeIntegration: false,
        webSecurity: true,
        webviewTag: true
      }
    });

    const indexPath = path.join(__dirname, '../renderer/index.html');
    log.info('Loading app shell:', indexPath);
    this.mainWindow.loadFile(indexPath);

    this.mainWindow.once('ready-to-show', () => {
      this.mainWindow.show();
      log.info('Main window is ready');
    });

    this.mainWindow.on('close', (event) => {
      if (this.isQuitting) {
        return;
      }

      event.preventDefault();
      this.mainWindow.hide();
      log.info('Main window hidden to tray');
    });

    this.mainWindow.on('closed', () => {
      this.mainWindow = null;
      log.info('Main window closed');
    });
  }

  setupIPC() {
    log.info('Setting up IPC handlers...');

    // 鑾峰彇 Playwright 娴忚鍣ㄨ矾寰?
    ipcMain.handle('playwright:getBrowserPath', () => {
      return this.playwrightBrowserPath;
    });

    // 鍒涘缓鍙鍖栨祻瑙堝櫒绐楀彛锛堢敤浜庤皟璇曞拰棰勮锛?
    ipcMain.handle('browser:createVisual', async (event, url, options = {}) => {
      log.info('Creating visual browser window:', url);

      const browserWindow = new BrowserWindow({
        width: options.width || 1200,
        height: options.height || 800,
        show: true,
        backgroundColor: '#0a0a0e',
        icon: this.appIconPath || undefined,
        title: options.title || 'Browser Preview',
        webPreferences: {
          contextIsolation: true,
          nodeIntegration: false,
          webSecurity: true
        }
      });

      await browserWindow.loadURL(url);

      const windowId = browserWindow.id;
      this.visualBrowserWindows.set(windowId, browserWindow);

      browserWindow.on('closed', () => {
        this.visualBrowserWindows.delete(windowId);
      });

      return windowId;
    });

    // 鍏抽棴鍙鍖栨祻瑙堝櫒绐楀彛
    ipcMain.handle('browser:closeVisual', (event, windowId) => {
      const win = this.visualBrowserWindows.get(windowId);
      if (win && !win.isDestroyed()) {
        win.close();
        return true;
      }
      return false;
    });

    // 鑾峰彇搴旂敤淇℃伅
    ipcMain.handle('app:getInfo', () => {
      return {
        version: app.getVersion(),
        name: app.getName(),
        isPackaged: this.isPackagedRuntime,
        runtimeMode: this.isPackagedRuntime ? 'packaged' : 'development',
        resourcesPath: process.resourcesPath,
        playwrightBrowserPath: this.playwrightBrowserPath,
        runtimeSettings: this.runtimeSettings,
        browserRuntimeInfo: this.getBrowserRuntimeInfo(),
        backendUrl: this.getBackendBaseUrl(),
        backendPort: this.getBackendPort(),
        frontendUrl: this.getFrontendBaseUrl(),
        frontendPort: this.getFrontendPort(),
        systemApiBaseUrl: this.getSystemApiBaseUrl()
      };
    });

    ipcMain.handle('settings:get', () => {
      return this.runtimeSettings;
    });

    ipcMain.handle('settings:update', (event, settings = {}) => {
      try {
        if (settings.automationRuntime === 'patchright' || settings.automationRuntime === 'playwright') {
          const runtimeInfo = this.getBrowserRuntimeInfo();
          const selectedRuntime = runtimeInfo.runtimes[settings.automationRuntime];
          if (!selectedRuntime?.installed || selectedRuntime.driverInstalled === false) {
            return {
              success: false,
              error: `runtime_incomplete:${settings.automationRuntime}`,
              browserRuntimeInfo: runtimeInfo
            };
          }
        }
        const nextSettings = this.saveRuntimeSettings(settings);
        return {
          success: true,
          settings: nextSettings,
          browserRuntimeInfo: this.getBrowserRuntimeInfo()
        };
      } catch (error) {
        log.error('Failed to update runtime settings:', error);
        return { success: false, error: error.message };
      }
    });

    ipcMain.handle('browserRuntime:getStatus', () => {
      try {
        return { success: true, browserRuntimeInfo: this.getBrowserRuntimeInfo() };
      } catch (error) {
        log.error('Failed to inspect browser runtime info:', error);
        return { success: false, error: error.message };
      }
    });

    ipcMain.handle('browserRuntime:install', async (event, target) => {
      try {
        return await this.installBrowserComponent(target);
      } catch (error) {
        log.error(`Failed to install browser runtime target ${target}:`, error);
        return { success: false, error: error.message };
      }
    });

    ipcMain.handle('browserRuntime:uninstall', async (event, target) => {
      try {
        return await this.uninstallBrowserComponent(target);
      } catch (error) {
        log.error(`Failed to uninstall browser runtime target ${target}:`, error);
        return { success: false, error: error.message };
      }
    });

    // 璁剧疆 Session Cookies
    ipcMain.handle('session:setCookies', async (event, partition, cookies) => {
      log.info(`Setting ${cookies.length} cookies for partition ${partition}`);
      const { session } = require('electron');
      const sess = session.fromPartition(partition);

      const sameSiteMap = {
        None: 'no_restriction',
        Lax: 'lax',
        Strict: 'strict',
        no_restriction: 'no_restriction',
        lax: 'lax',
        strict: 'strict'
      };
      const results = [];

      for (const cookie of cookies) {
        try {
          if (!cookie?.name || !cookie?.domain) {
            throw new Error('Missing cookie name or domain');
          }
          const pathName = cookie.path || '/';
          const hostname = cookie.domain.startsWith('.') ? cookie.domain.substring(1) : cookie.domain;
          const details = {
            url: `${cookie.secure ? 'https' : 'http'}://${hostname}${pathName}`,
            name: cookie.name,
            value: String(cookie.value ?? ''),
            path: pathName,
            secure: Boolean(cookie.secure),
            httpOnly: Boolean(cookie.httpOnly)
          };
          if (!cookie.name.startsWith('__Host-')) {
            details.domain = cookie.domain;
          }
          if (typeof cookie.expires === 'number' && cookie.expires > 0) {
            details.expirationDate = cookie.expires;
          }
          if (cookie.sameSite && sameSiteMap[cookie.sameSite]) {
            details.sameSite = sameSiteMap[cookie.sameSite];
          }
          await sess.cookies.set(details);
          results.push({ name: cookie.name, domain: cookie.domain, success: true });
        } catch (error) {
          log.error(`Failed to set cookie ${cookie?.name || '<unknown>'}:`, error);
          results.push({ name: cookie?.name, domain: cookie?.domain, success: false, error: error.message });
        }
      }

      const failed = results.filter((item) => !item.success);
      try {
        await sess.cookies.flushStore();
      } catch (error) {
        log.warn(`Cookie flush failed for partition ${partition}:`, error);
      }
      log.info(`Cookie setup finished for ${partition}: ${results.length - failed.length}/${results.length}`);
      return { success: failed.length === 0, results };
    });

    // ========== 绯荤粺绠＄悊 IPC 澶勭悊鍣?==========

    // 閲嶅惎鍓嶇鏈嶅姟
    ipcMain.handle('system:restart-frontend', async () => {
      log.info('Restarting frontend service...');
      try {
        if (this.frontendProcess) {
          this.frontendProcess.kill();
          this.frontendProcess = null;
        }
        await this.startFrontend();
        log.info('Frontend service restarted successfully');
        return { success: true };
      } catch (error) {
        log.error('Failed to restart frontend service:', error);
        return { success: false, error: error.message };
      }
    });

    // 閲嶅惎鍚庣鏈嶅姟
    ipcMain.handle('system:restart-backend', async () => {
      log.info('Restarting backend service...');
      try {
        if (this.supervisorProcess && !this.supervisorProcess.killed) {
          await this.requestSupervisor('/api/restart/backend', 'POST', 30000);
        } else {
          if (this.backendProcess) {
            this.backendProcess.kill();
            this.backendProcess = null;
          }
          await this.startBackend(this.buildServiceEnv());
        }
        log.info('Backend service restarted successfully');
        return { success: true };
      } catch (error) {
        log.error('Failed to restart backend service:', error);
        return { success: false, error: error.message };
      }
    });

    // 閲嶅惎鎵€鏈夋湇鍔?
    ipcMain.handle('system:restart-all', async () => {
        log.info('Restarting all services...');
      try {
        await this.restartManagedServices();
        log.info('All services restarted successfully');
        return { success: true };
      } catch (error) {
        log.error('Failed to restart all services:', error);
        return { success: false, error: error.message };
      }
    });

    // 鍋滄鎵€鏈夋湇鍔?
    ipcMain.handle('system:stop-all', async () => {
      log.info('Stopping all services...');
      try {
        await this.stopManagedServices();
        log.info('All services stopped');
        return { success: true };
      } catch (error) {
        log.error('Failed to stop services:', error);
        return { success: false, error: error.message };
      }
    });

    ipcMain.handle('system:quit-app', async () => {
      return this.quitApplication();
    });

    ipcMain.handle('system:restart-app', async () => {
      return this.restartApplication();
    });

    // 鑾峰彇绯荤粺鐘舵€?
    ipcMain.handle('system:get-status', () => {
      return {
        frontend: {
          running: this.frontendProcess !== null && !this.frontendProcess.killed,
          pid: this.frontendProcess?.pid
        },
        backend: {
          running: this.backendProcess !== null && !this.backendProcess.killed,
          pid: this.backendProcess?.pid
        },
        supervisor: {
          running: this.supervisorProcess !== null && !this.supervisorProcess.killed,
          pid: this.supervisorProcess?.pid
        },
        playwright_worker: {
          running: this.playwrightWorkerProcess !== null && !this.playwrightWorkerProcess.killed,
          pid: this.playwrightWorkerProcess?.pid
        },
        celery_worker: {
          running: this.celeryProcess !== null && !this.celeryProcess.killed,
          pid: this.celeryProcess?.pid
        },
        hermes_gateway: {
          running: false,
          pid: null,
        },
        hermes_dashboard: {
          running: false,
          pid: null,
        },
        hermes_webui: {
          running: false,
          pid: null,
        }
      };
    });

    // ========== Supervisor 绠＄悊 IPC (閫氳繃 HTTP API 涓?supervisor 閫氫俊) ==========

    // 鑾峰彇 supervisor 绠＄悊鐨勬湇鍔＄姸鎬?
    ipcMain.handle('supervisor:get-status', async () => {
      try {
        if (!this.supervisorProcess || this.supervisorProcess.killed) {
          return {
            frontend: {
              running: this.frontendProcess !== null && !this.frontendProcess.killed,
              pid: this.frontendProcess?.pid
            },
            backend: {
              running: this.backendProcess !== null && !this.backendProcess.killed,
              pid: this.backendProcess?.pid
            },
            supervisor: {
              running: this.supervisorProcess !== null && !this.supervisorProcess.killed,
              pid: this.supervisorProcess?.pid
            },
            playwright_worker: {
              running: this.playwrightWorkerProcess !== null && !this.playwrightWorkerProcess.killed,
              pid: this.playwrightWorkerProcess?.pid
            },
            celery_worker: {
              running: this.celeryProcess !== null && !this.celeryProcess.killed,
              pid: this.celeryProcess?.pid
            },
            hermes_gateway: {
              running: false,
              pid: null,
            },
            hermes_dashboard: {
              running: false,
              pid: null,
            },
            hermes_webui: {
              running: false,
              pid: null,
            }
          };
        }

        const result = await this.getSupervisorStatus(5000);
        const payload = result?.data || {};
        payload.frontend = {
          running: this.frontendProcess !== null && !this.frontendProcess.killed,
          pid: this.frontendProcess?.pid
        };
        const workerStatus = payload.playwright_worker || payload.worker || { running: false, pid: null, external: false };
        const celeryStatus = payload.celery_worker || payload.celery || { running: false, pid: null, external: false };
        const gatewayStatus = payload.hermes_gateway || payload.gateway || { running: false, pid: null, external: false };
        const hermesDashboardStatus = payload.hermes_dashboard || payload.dashboard || { running: false, pid: null, external: false };
        const hermesWebuiStatus = payload.hermes_webui || payload.webui || { running: false, pid: null, external: false };
        return {
          backend: payload.backend || { running: false, pid: null, external: false },
          playwright_worker: workerStatus,
          celery_worker: celeryStatus,
          hermes_gateway: gatewayStatus,
          hermes_dashboard: hermesDashboardStatus,
          hermes_webui: hermesWebuiStatus,
          frontend: payload.frontend,
          supervisor: {
            running: this.supervisorProcess !== null && !this.supervisorProcess.killed,
            pid: this.supervisorProcess?.pid
          }
        };
      } catch (error) {
        log.error('Failed to get supervisor status:', error);
        throw error;
      }
    });

    // 鍚姩鎵€鏈夋湇鍔?
    ipcMain.handle('supervisor:start-all', async () => {
      try {
        const http = require('http');

        return new Promise((resolve, reject) => {
          const req = http.request({
            hostname: '127.0.0.1',
            port: 7002,
            path: '/api/start',
            method: 'POST'
          }, (res) => {
            let data = '';

            res.on('data', (chunk) => {
              data += chunk;
            });

            res.on('end', () => {
              try {
                const result = JSON.parse(data);
                // 鍚屾椂鍚姩鍓嶇
                this.startFrontend();
                resolve({ success: true, message: result.message });
              } catch (error) {
                reject(error);
              }
            });
          });

          req.on('error', (error) => {
            reject(error);
          });

          req.end();
        });
      } catch (error) {
        log.error('Failed to start supervisor-managed services:', error);
        return { success: false, error: error.message };
      }
    });

    // 鍋滄鎵€鏈夋湇鍔?
    ipcMain.handle('supervisor:stop-all', async () => {
      try {
        const http = require('http');

        return new Promise((resolve, reject) => {
          const req = http.request({
            hostname: '127.0.0.1',
            port: 7002,
            path: '/api/stop',
            method: 'POST'
          }, (res) => {
            let data = '';

            res.on('data', (chunk) => {
              data += chunk;
            });

            res.on('end', () => {
              try {
                const result = JSON.parse(data);
                // 鍚屾椂鍋滄鍓嶇
                if (this.frontendProcess) {
                  this.frontendProcess.kill();
                  this.frontendProcess = null;
                }
                resolve({ success: true, message: result.message });
              } catch (error) {
                reject(error);
              }
            });
          });

          req.on('error', (error) => {
            reject(error);
          });

          req.end();
        });
      } catch (error) {
        log.error('Failed to stop supervisor-managed services:', error);
        return { success: false, error: error.message };
      }
    });

    // 閲嶅惎鎵€鏈夋湇鍔?
    ipcMain.handle('supervisor:restart-all', async () => {
      try {
        await this.restartManagedServices();
        return { success: true, message: 'Restart completed' };
      } catch (error) {
        log.error('Failed to restart supervisor-managed services:', error);
        return { success: false, error: error.message };
      }
    });

    // 鍚姩涓诲簲鐢?
    ipcMain.handle('supervisor:launch-main-app', async () => {
      try {
        // 鍏抽棴鍚姩绠＄悊鍣ㄧ獥鍙?
        if (this.launcherWindow) {
          this.launcherWindow.close();
          this.launcherWindow = null;
        }

        // 鍒涘缓涓荤獥鍙?
        if (!this.mainWindow) {
          this.createMainWindow();
        }

        return { success: true };
      } catch (error) {
        log.error('Failed to launch main application window:', error);
        return { success: false, error: error.message };
      }
    });

    // ========== 鎵撳紑璁剧疆绐楀彛 ==========
    ipcMain.handle('window:openSettings', () => {
      log.info('Opening settings window');
      this.createSettingsWindow();
      return { success: true };
    });

    // ========== 鏁版嵁娓呯悊 IPC ==========
    ipcMain.handle('system:clear-video-data', async (event, options = {}) => {
      log.info('Clearing video data...');
      try {
        const http = require('http');
        const backendBaseUrl = new URL(this.getBackendBaseUrl());
        const backendPort = Number.parseInt(backendBaseUrl.port, 10) || (backendBaseUrl.protocol === 'https:' ? 443 : 80);

        return new Promise((resolve, reject) => {
          const req = http.request({
            hostname: backendBaseUrl.hostname,
            port: backendPort,
            path: '/api/v1/system/clear-video-data',
            method: 'POST'
          }, (res) => {
            let data = '';

            res.on('data', (chunk) => {
              data += chunk;
            });

            res.on('end', () => {
              try {
                const result = JSON.parse(data);
                if (res.statusCode === 200) {
                  log.info('Video data cleared successfully');
                  resolve(result);
                } else {
                  log.error('Video data clear failed:', result);
                  reject(new Error(result.detail || 'Clear operation failed'));
                }
              } catch (error) {
                log.error('Failed to parse clear-video-data response:', error);
                reject(error);
              }
            });
          });

          req.on('error', (error) => {
            log.error('clear-video-data request failed:', error);
            reject(error);
          });

          req.setTimeout(30000, () => {
            req.destroy();
            reject(new Error('Request timeout'));
          });

          req.end();
        });
      } catch (error) {
        log.error('Failed to clear video data:', error);
        return { success: false, error: error.message };
      }
    });

    log.info('IPC handlers ready');
  }

  setupAppEvents() {
    app.on('second-instance', () => {
      log.info('Detected second instance, focusing current window');
      this.showMainWindow();
    });

    app.on('window-all-closed', () => {
      log.info('All windows closed; application remains available from tray');
    });

    app.on('activate', () => {
      this.showMainWindow();
    });

    app.on('before-quit', () => {
      this.isQuitting = true;
      log.info('Application is about to quit, cleaning up resources...');
      this.cleanup();
      if (this.tray) {
        this.tray.destroy();
        this.tray = null;
      }
    });
  }

  cleanup() {
    log.info('Cleaning up resources...');

    for (const [, win] of this.visualBrowserWindows) {
      if (!win.isDestroyed()) {
        win.close();
      }
    }
    this.visualBrowserWindows.clear();

    const stopProcess = (proc, label) => {
      if (!proc) {
        return;
      }

      try {
        log.info(`Stopping ${label} process...`);
        if (process.platform === 'win32' && proc.pid) {
          execSync(`taskkill /F /T /PID ${proc.pid}`, { stdio: 'ignore' });
        } else if (!proc.killed) {
          proc.kill();
        }
      } catch (error) {
        log.warn(`Failed to terminate ${label}:`, error);
      }
    };

    stopProcess(this.frontendProcess, 'frontend');
    this.frontendProcess = null;

    stopProcess(this.celeryProcess, 'celery');
    this.celeryProcess = null;

    stopProcess(this.playwrightWorkerProcess, 'playwright worker');
    this.playwrightWorkerProcess = null;

    stopProcess(this.backendProcess, 'backend');
    this.backendProcess = null;

    stopProcess(this.redisProcess, 'redis');
    this.redisProcess = null;

    stopProcess(this.supervisorProcess, 'supervisor');
    this.supervisorProcess = null;

    this.servicesStarted = false;
    log.info('Resource cleanup complete');
  }
}

// 鍚姩搴旂敤
const synapseApp = new SynapseApp();

// 鎹曡幏鏈鐞嗙殑閿欒
process.on('uncaughtException', (error) => {
  log.error('Uncaught exception:', error);
});

process.on('unhandledRejection', (reason, promise) => {
  log.error('Unhandled promise rejection:', reason);
});

// 鍒濆鍖栧簲鐢?
synapseApp.initialize().catch((error) => {
  log.error('Application initialization failed:', error);
  if (app && app.quit) {
    app.quit();
  } else {
    process.exit(1);
  }
});
