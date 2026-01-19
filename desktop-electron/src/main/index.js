const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn, execSync } = require('child_process');
const net = require('net');
const log = require('electron-log');
const fs = require('fs');

// 配置日志
log.transports.file.level = 'info';
log.transports.console.level = 'debug';

// 单实例锁定 - 防止多次启动
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  console.log('⚠️ 应用已在运行中，退出此实例');
  log.info('⚠️ 应用已在运行中，退出此实例');
  app.quit();
  process.exit(0);
}

// 添加控制台输出以便调试
console.log('=== Electron Main Process Starting ===');
console.log('Log file path:', log.transports.file.getFile().path);

class SynapseApp {
  constructor() {
    this.mainWindow = null;
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
  }

  async initialize() {
    console.log('🚀 SynapseAutomation 启动中...');
    log.info('🚀 SynapseAutomation 启动中...');

    // 等待 Electron 准备就绪
    await app.whenReady();

    // 检查是否存在打包后的 supervisor.exe 来判断是否为生产环境
    const supervisorExePath = path.join(process.resourcesPath, 'supervisor', 'supervisor.exe');
    const supervisorExists = fs.existsSync(supervisorExePath);
    this.isDev = !app.isPackaged;
    this.repoRoot = path.join(__dirname, '../../../');
    this.appIconPath = this.getAppIconPath();

    console.log('📍 App ready. isDev:', this.isDev, 'isPackaged:', app.isPackaged);
    console.log('📍 resourcesPath:', process.resourcesPath);
    console.log('📍 supervisor.exe exists:', supervisorExists, 'at:', supervisorExePath);
    log.info('📍 App ready. isDev:', this.isDev, 'isPackaged:', app.isPackaged);
    log.info('📍 resourcesPath:', process.resourcesPath);
    log.info('📍 supervisor.exe exists:', supervisorExists);

    // 1. 设置 Playwright 浏览器路径
    this.setupPlaywrightPath();

    // 2. 启动后端/前端服务（生产默认启动，开发可用 SYNAPSE_START_SERVICES=1 强制）
    const shouldStartServices = process.env.SYNAPSE_START_SERVICES === '1' || !this.isDev;
    const showLauncher = process.env.SYNAPSE_SHOW_LAUNCHER === '1'; // 是否显示启动管理器
    console.log('📍 Should start services:', shouldStartServices, '(isDev:', this.isDev, ')');
    console.log('📍 Show launcher:', showLauncher);
    log.info('📍 Should start services:', shouldStartServices, '(isDev:', this.isDev, ')');
    log.info('📍 Show launcher:', showLauncher);

    if (shouldStartServices) {
      console.log('🔧 Starting services...');
      log.info('🔧 Starting services...');
      await this.startServices();
      console.log('✅ Services started');
      log.info('✅ Services started');
    }

    // 3. 创建窗口（如果启用启动管理器，则显示启动管理器；否则创建主窗口）
    if (showLauncher) {
      this.createLauncherWindow();
    } else {
      this.createMainWindow();
    }

    // 4. 设置 IPC 处理
    this.setupIPC();

    // 5. 设置应用事件
    this.setupAppEvents();

    log.info('✅ SynapseAutomation 启动完成');
  }

  setupPlaywrightPath() {
    // 获取打包后的资源路径
    const isDev = this.isDev;

    if (isDev) {
      // 开发环境：使用项目根目录的浏览器
      this.playwrightBrowserPath = path.join(__dirname, '../../../browsers');
      log.info('🔧 开发模式 - 浏览器路径:', this.playwrightBrowserPath);
    } else {
      // 生产环境：使用打包后的浏览器
      this.playwrightBrowserPath = path.join(process.resourcesPath, 'browsers');
      log.info('📦 生产模式 - 浏览器路径:', this.playwrightBrowserPath);
    }

    // 设置环境变量，让 Playwright 使用指定的浏览器
    process.env.PLAYWRIGHT_BROWSERS_PATH = this.playwrightBrowserPath;

    // 验证浏览器是否存在
    if (fs.existsSync(this.playwrightBrowserPath)) {
      log.info('✅ Playwright 浏览器路径已设置');
    } else {
      log.warn('⚠️ Playwright 浏览器路径不存在，自动化功能可能无法使用');
    }
  }

  getResourcesRoot() {
    return this.isDev ? this.repoRoot : process.resourcesPath;
  }

  getBackendDir() {
    return this.isDev
      ? path.join(this.repoRoot, 'syn_backend')
      : path.join(process.resourcesPath, 'syn_backend');
  }

  getPythonPath() {
    const pythonPath = path.join(this.getResourcesRoot(), 'synenv', 'Scripts', 'python.exe');
    if (fs.existsSync(pythonPath)) {
      return pythonPath;
    }
    return 'python';
  }

  ensureSynenvConfig() {
    if (this.isDev) {
      return;
    }

    const resourcesRoot = this.getResourcesRoot();
    const venvDir = path.join(resourcesRoot, 'synenv');
    const cfgPath = path.join(venvDir, 'pyvenv.cfg');
    if (!fs.existsSync(cfgPath)) {
      log.warn('pyvenv.cfg not found:', cfgPath);
      return;
    }

    const pythonHome = path.join(venvDir, '_python');
    const pythonExe = path.join(pythonHome, 'python.exe');
    const expected = {
      home: pythonHome,
      executable: pythonExe,
      command: `${pythonExe} -m venv ${venvDir}`
    };

    const raw = fs.readFileSync(cfgPath, 'utf8');
    const eol = raw.includes('\r\n') ? '\r\n' : '\n';
    const lines = raw.split(/\r?\n/);
    let changed = false;

    const updated = lines.map((line) => {
      const match = line.match(/^(\w+)\s*=\s*(.*)$/);
      if (!match) {
        return line;
      }
      const key = match[1];
      if (!Object.prototype.hasOwnProperty.call(expected, key)) {
        return line;
      }
      const nextValue = expected[key];
      const nextLine = `${key} = ${nextValue}`;
      if (line !== nextLine) {
        changed = true;
        return nextLine;
      }
      return line;
    });

    if (changed) {
      fs.writeFileSync(cfgPath, updated.join(eol), 'utf8');
      log.info('pyvenv.cfg updated for current install path:', cfgPath);
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

  getAppIconPath() {
    return this.resolveFirstPath([
      path.join(app.getAppPath(), 'icon.ico'),
      path.join(process.resourcesPath, 'icon.ico'),
      path.join(__dirname, '..', '..', 'icon.ico')
    ]);
  }

  getServiceExe(name) {
    if (this.isDev) {
      return null;
    }
    const exePath = path.join(process.resourcesPath, 'services', `${name}.exe`);
    return fs.existsSync(exePath) ? exePath : null;
  }

  buildServiceEnv() {
    const browsersRoot = this.getBrowsersRoot();
    log.info('🔍 构建服务环境变量...');
    log.info('  - Browsers Root:', browsersRoot);
    log.info('  - Browsers Root exists:', fs.existsSync(browsersRoot));

    const appRoot = this.getResourcesRoot();
    const env = {
      ...process.env,
      PYTHONUTF8: '1',
      PYTHONIOENCODING: 'utf-8',
      SYNAPSE_APP_ROOT: appRoot,
      SYNAPSE_RESOURCES_PATH: appRoot,
      PLAYWRIGHT_BROWSERS_PATH: browsersRoot
    };
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

    const chromePath = this.resolveFirstPath([
      path.join(browsersRoot, 'chromium', 'chromium-1161', 'chrome-win', 'chrome.exe'),
      path.join(browsersRoot, 'chrome-for-testing', 'chrome-143.0.7499.169', 'chrome-win64', 'chrome.exe')
    ]);
    if (chromePath) {
      env.LOCAL_CHROME_PATH = chromePath;
      log.info('  - Chrome Path:', chromePath);
    } else {
      log.warn('  - Chrome Path: NOT FOUND');
    }

    const firefoxPath = this.resolveFirstPath([
      path.join(browsersRoot, 'firefox', 'firefox-1495', 'firefox', 'firefox.exe')
    ]);
    if (firefoxPath) {
      env.LOCAL_FIREFOX_PATH = firefoxPath;
      log.info('  - Firefox Path:', firefoxPath);
    } else {
      log.warn('  - Firefox Path: NOT FOUND');
    }

    log.info('✅ 服务环境变量已构建');
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

  async startServices() {
    if (this.servicesStarted) {
      return;
    }

    // 在生产环境使用 supervisor 统一管理所有后端服务
    if (!this.isDev) {
      console.log('🔧 Using supervisor to manage backend services...');
      log.info('🔧 Using supervisor to manage backend services...');
      // 生产环境下，supervisor 会自己启动 Redis，我们不需要单独启动
      this.startSupervisor();
      await this.startFrontend(this.buildServiceEnv());  // 生产环境也需要启动前端
      this.servicesStarted = true;
      return;
    }

    // 开发环境：分别启动各个服务
    const env = this.buildServiceEnv();
    await this.startRedis(env);
    await this.startPlaywrightWorker(env);
    await this.startBackend(env);
    this.startCelery(env);
    await this.startFrontend(env);
    this.servicesStarted = true;
  }

  startSupervisor() {
    if (this.supervisorProcess) {
      return;
    }

    this.ensureSynenvConfig();

    const supervisorExe = path.join(process.resourcesPath, 'supervisor', 'supervisor.exe');
    const supervisorScript = path.join(process.resourcesPath, 'supervisor', 'supervisor.py');
    const pythonPath = this.getPythonPath();

    console.log('📍 Supervisor exe:', supervisorExe);
    console.log('📍 Supervisor script:', supervisorScript);
    log.info('🚀 Starting Supervisor...');
    log.info('  - Supervisor exe:', supervisorExe);
    log.info('  - Supervisor script:', supervisorScript);
    log.info('  - Exe exists:', fs.existsSync(supervisorExe));
    log.info('  - Script exists:', fs.existsSync(supervisorScript));

    // 优先使用 exe，如果不存在则用 Python 脚本
    const launchCmd = fs.existsSync(supervisorExe) ? supervisorExe : pythonPath;
    const launchArgs = fs.existsSync(supervisorExe) ? [] : [supervisorScript];

    console.log('📍 Launch command:', launchCmd, launchArgs);
    log.info('  - Launch Command:', launchCmd);
    log.info('  - Launch Args:', launchArgs);

    // 构建环境变量
    const env = this.buildServiceEnv();

    this.supervisorProcess = spawn(launchCmd, launchArgs, {
      cwd: path.dirname(supervisorScript),
      env: env,
      windowsHide: true
    });

    this.supervisorProcess.on('error', (error) => {
      console.error('❌ Supervisor failed to start:', error);
      log.error('❌ Supervisor failed to start:', error);
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
      console.warn(`⚠️ Supervisor exited with code: ${code}`);
      log.warn(`⚠️ Supervisor 退出，退出码: ${code}`);
      this.supervisorProcess = null;
    });

    console.log('✅ Supervisor started');
    log.info('✅ Supervisor started');
  }

  async startRedis(env) {
    if (this.redisProcess) {
      return;
    }
    const redisPath = this.isDev
      ? (process.env.SYNAPSE_REDIS_PATH || 'redis-server')
      : path.join(process.resourcesPath, 'redis', 'redis-server.exe');

    log.info('🧩 启动 Redis...');
    log.info('  - Redis Path:', redisPath);
    log.info('  - Redis exists:', fs.existsSync(redisPath));
    log.info('  - Is Dev:', this.isDev);

    if (await this.isPortInUse(6379)) {
      log.warn('Redis already running on port 6379; skipping start.');
      return;
    }

    if (!this.isDev && !fs.existsSync(redisPath)) {
      log.error(`❌ Redis 未找到: ${redisPath}`);
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
      log.warn(`⚠️ Redis 退出，退出码: ${code}`);
    });
  }

  async startPlaywrightWorker(env) {
    if (this.playwrightWorkerProcess) {
      return;
    }
    if (await this.isPortInUse(7001)) {
      log.warn('Playwright Worker already running on port 7001; skipping start.');
      return;
    }
    const backendDir = this.getBackendDir();
    const workerExe = this.getServiceExe('playwright-worker');
    const workerScript = path.join(backendDir, 'playwright_worker', 'worker.py');

    log.info('🧩 启动 Playwright Worker...');
    log.info('  - Backend Dir:', backendDir);
    log.info('  - Worker Exe:', workerExe || 'N/A');
    log.info('  - Worker Script:', workerScript);
    log.info('  - Script exists:', fs.existsSync(workerScript));

    if (!workerExe && !fs.existsSync(workerScript)) {
      log.error(`❌ Playwright Worker 未找到: ${workerScript}`);
      return;
    }
    const pythonPath = this.getPythonPath();
    const launchCmd = workerExe || pythonPath;
    const launchArgs = workerExe ? [] : [workerScript];

    log.info('  - Launch Command:', launchCmd);
    log.info('  - Launch Args:', launchArgs.join(' '));

    this.playwrightWorkerProcess = spawn(launchCmd, launchArgs, {
      env: { ...env, PYTHONPATH: backendDir },
      cwd: backendDir,
      windowsHide: true
    });
    this.playwrightWorkerProcess.stdout?.on('data', (data) => log.info('[Worker]', data.toString()));
    this.playwrightWorkerProcess.stderr?.on('data', (data) => log.error('[Worker Error]', data.toString()));
    this.playwrightWorkerProcess.on('exit', (code) => {
      log.warn(`⚠️ Playwright Worker 退出，退出码: ${code}`);
    });
  }

  startCelery(env) {
    if (this.celeryProcess) {
      return;
    }
    const backendDir = this.getBackendDir();
    const celeryExe = this.getServiceExe('celery-worker');
    const pythonPath = this.getPythonPath();

    log.info('🧩 启动 Celery Worker...');
    log.info('  - Backend Dir:', backendDir);
    log.info('  - Celery Exe:', celeryExe || 'N/A');
    log.info('  - Python Path:', pythonPath);

    if (process.platform === 'win32') {
      try {
        const killCmd = [
          "Get-CimInstance Win32_Process",
          "Where-Object {",
          "  $_.Name -match 'celery' -or",
          "  $_.CommandLine -match 'celery' -or",
          "  $_.CommandLine -match 'fastapi_app.tasks.celery_app' -or",
          "  $_.CommandLine -match 'synapse-worker'",
          "}",
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }",
        ].join(' | ');
        execSync(`powershell -NoProfile -Command "${killCmd}"`, { stdio: 'ignore' });
        log.info('? Existing Celery workers stopped (if any).');
      } catch (error) {
        log.warn('?? Failed to stop existing Celery workers.', error);
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
      log.warn(`⚠️ Celery 退出，退出码: ${code}`);
    });
  }

  async startFrontend(env) {
    log.info(' startFrontend ?);');
    log.info(`  - this.frontendProcess: ${this.frontendProcess ? 'exists' : 'null'}`);
    log.info(`  - this.isDev: ${this.isDev}`);

    if (this.frontendProcess) {
      log.info('? ');
      return;
    }

    if (this.isDev) {
      const shouldStartDevFrontend =
        process.env.SYNAPSE_START_FRONTEND === '1' ||
        process.env.SYNAPSE_START_SERVICES === '1';
      if (!shouldStartDevFrontend) {
        log.info('? ?');
        return;
      }

      if (await this.isPortInUse(3000)) {
        log.warn('Frontend already running on port 3000; skipping start.');
        return;
      }

      const frontendDir = path.join(this.repoRoot, 'syn_frontend_react');
      log.info(`  - frontendDir: ${frontendDir}`);

      const launchCmd = process.platform === 'win32' ? 'cmd' : 'npm';
      const launchArgs = process.platform === 'win32' ? ['/c', 'npm', 'run', 'dev'] : ['run', 'dev'];
      const frontendEnv = {
        ...env,
        NODE_ENV: 'development',
        PORT: '3000',
        HOSTNAME: '127.0.0.1',
        NEXT_PUBLIC_BACKEND_URL: 'http://127.0.0.1:7000',
        NEXT_PUBLIC_API_URL: 'http://127.0.0.1:7000'
      };

      log.info(' (dev)...');
      this.frontendProcess = spawn(launchCmd, launchArgs, {
        env: frontendEnv,
        cwd: frontendDir,
        windowsHide: true
      });
      this.frontendProcess.stdout?.on('data', (data) => log.info('[Frontend]', data.toString()));
      this.frontendProcess.stderr?.on('data', (data) => log.error('[Frontend Error]', data.toString()));
      this.frontendProcess.on('exit', (code) => {
        log.warn(`? ?(dev) : ${code}`);
        this.frontendProcess = null;
      });
      return;
    }

    if (await this.isPortInUse(3000)) {
      log.warn('Frontend already running on port 3000; skipping start.');
      return;
    }
    const frontendDir = path.join(process.resourcesPath, 'frontend', 'standalone');
    const serverJs = path.join(frontendDir, 'server.js');
    log.info(`  - frontendDir: ${frontendDir}`);
    log.info(`  - serverJs: ${serverJs}`);
    log.info(`  - serverJs exists: ${fs.existsSync(serverJs)}`);

    if (!fs.existsSync(serverJs)) {
      log.warn(`? : ${serverJs}`);
      return;
    }
    log.info(' ?...');
    const frontendEnv = {
      ...env,
      ELECTRON_RUN_AS_NODE: '1',
      NODE_ENV: 'production',
      PORT: '3000',
      HOSTNAME: '127.0.0.1',
      NEXT_PUBLIC_BACKEND_URL: 'http://127.0.0.1:7000',
      SYN_BACKEND_URL: 'http://127.0.0.1:7000',
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
      log.warn(`? : ${code}`);
    });
  }


  async startBackend(env) {
    if (this.backendProcess) {
      return;
    }
    if (await this.isPortInUse(7000)) {
      log.warn('Backend already running on port 7000; skipping start.');
      return;
    }
    const backendDir = this.getBackendDir();
    const backendExe = this.getServiceExe('backend');
    const pythonPath = this.getPythonPath();
    const mainScript = path.join(backendDir, 'fastapi_app', 'run.py');

    log.info('🔄 启动 FastAPI 后端...');
    log.info('  - Backend Dir:', backendDir);
    log.info('  - Backend Dir exists:', fs.existsSync(backendDir));
    log.info('  - Backend Exe:', backendExe || 'N/A');
    log.info('  - Python Path:', pythonPath);
    log.info('  - Python exists:', fs.existsSync(pythonPath));
    log.info('  - Main Script:', mainScript);
    log.info('  - Script exists:', fs.existsSync(mainScript));

    return new Promise((resolve, reject) => {
      if (!backendExe && !fs.existsSync(mainScript)) {
        log.error(`❌ FastAPI 脚本未找到: ${mainScript}`);
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
          PYTHONPATH: backendDir
        },
        windowsHide: true
      });

      this.backendProcess.stdout?.on('data', (data) => {
        const output = data.toString();
        log.info('[Backend]', output);
        if (output.includes('Uvicorn running') || output.includes('Application startup complete')) {
          log.info('✅ FastAPI 后端启动成功');
          resolve();
        }
      });

      this.backendProcess.stderr?.on('data', (data) => {
        log.error('[Backend Error]', data.toString());
      });

      this.backendProcess.on('error', (error) => {
        log.error('❌ 后端进程启动失败:', error);
        reject(error);
      });

      this.backendProcess.on('exit', (code) => {
        log.warn(`⚠️ 后端进程退出，退出码: ${code}`);
      });

      setTimeout(() => {
        log.warn('⚠️ 后端启动超时，继续启动应用');
        resolve();
      }, 10000);
    });
  }

  createLauncherWindow() {
    log.info('🚀 创建启动管理器窗口...');

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

    // 加载启动管理器页面
    const launcherPath = path.join(__dirname, '../launcher/launcher.html');
    log.info('📦 加载启动管理器:', launcherPath);
    this.launcherWindow.loadFile(launcherPath);

    // 窗口关闭事件
    this.launcherWindow.on('closed', () => {
      this.launcherWindow = null;
      log.info('🚀 启动管理器已关闭');
    });

    this.launcherWindow.show();
  }

  createSettingsWindow() {
    log.info('⚙️ 创建设置窗口...');

    // 如果设置窗口已存在，直接显示
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
        webSecurity: false // 允许访问 localhost API
      }
    });

    // 加载设置页面
    const settingsPath = path.join(__dirname, '../settings/settings.html');
    log.info('📦 加载设置页面:', settingsPath);
    this.settingsWindow.loadFile(settingsPath);

    // 窗口关闭事件
    this.settingsWindow.on('closed', () => {
      this.settingsWindow = null;
      log.info('⚙️ 设置窗口已关闭');
    });

    this.settingsWindow.show();
  }

  createMainWindow() {
    log.info('🪟 创建主窗口...');

    this.mainWindow = new BrowserWindow({
      width: 1400,
      height: 900,
      minWidth: 1200,
      minHeight: 700,
      show: false,
      backgroundColor: '#ffffff',
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

    // 加载前端页面
    // 始终加载本地 Shell 页面，由 Shell 页面负责加载 Web App (localhost:3000)
    const indexPath = path.join(__dirname, '../renderer/index.html');
    log.info('📦 加载应用 Shell:', indexPath);
    this.mainWindow.loadFile(indexPath);

    // 窗口准备好后显示
    this.mainWindow.once('ready-to-show', () => {
      this.mainWindow.show();
      log.info('✅ 主窗口显示完成');
    });

    // 窗口关闭事件
    this.mainWindow.on('closed', () => {
      this.mainWindow = null;
      log.info('🪟 主窗口已关闭');
    });
  }

  setupIPC() {
    log.info('🔗 设置 IPC 通信...');

    // 获取 Playwright 浏览器路径
    ipcMain.handle('playwright:getBrowserPath', () => {
      return this.playwrightBrowserPath;
    });

    // 创建可视化浏览器窗口（用于调试和预览）
    ipcMain.handle('browser:createVisual', async (event, url, options = {}) => {
      log.info('🌐 创建可视化浏览器窗口:', url);

      const browserWindow = new BrowserWindow({
        width: options.width || 1200,
        height: options.height || 800,
        show: true,
        icon: this.appIconPath || undefined,
        title: options.title || '浏览器预览',
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

    // 关闭可视化浏览器窗口
    ipcMain.handle('browser:closeVisual', (event, windowId) => {
      const win = this.visualBrowserWindows.get(windowId);
      if (win && !win.isDestroyed()) {
        win.close();
        return true;
      }
      return false;
    });

    // 获取应用信息
    ipcMain.handle('app:getInfo', () => {
      return {
        version: app.getVersion(),
        name: app.getName(),
        isPackaged: app.isPackaged,
        resourcesPath: process.resourcesPath,
        playwrightBrowserPath: this.playwrightBrowserPath
      };
    });

    // 设置 Session Cookies
    ipcMain.handle('session:setCookies', async (event, partition, cookies) => {
      log.info(`🍪 为分区 ${partition} 设置 ${cookies.length} 个 Cookies`);
      const { session } = require('electron');
      const sess = session.fromPartition(partition);

      const promises = cookies.map(cookie => {
        // Playwright cookie 格式转 Electron cookie 格式
        const url = `${cookie.secure ? 'https' : 'http'}://${cookie.domain.startsWith('.') ? cookie.domain.substring(1) : cookie.domain}${cookie.path}`;
        return sess.cookies.set({
          url: url,
          name: cookie.name,
          value: cookie.value,
          domain: cookie.domain,
          path: cookie.path,
          secure: cookie.secure,
          httpOnly: cookie.httpOnly,
          expirationDate: cookie.expires
        });
      });

      try {
        await Promise.all(promises);
        log.info(`✅ 分区 ${partition} Cookies 设置成功`);
        return true;
      } catch (error) {
        log.error(`❌ 分区 ${partition} Cookies 设置失败:`, error);
        return false;
      }
    });

    // ========== 系统管理 IPC 处理器 ==========

    // 重启前端服务
    ipcMain.handle('system:restart-frontend', async () => {
      log.info('🔄 重启前端服务...');
      try {
        if (this.frontendProcess) {
          this.frontendProcess.kill();
          this.frontendProcess = null;
        }
        await this.startFrontend();
        log.info('✅ 前端服务重启成功');
        return { success: true };
      } catch (error) {
        log.error('❌ 前端服务重启失败:', error);
        return { success: false, error: error.message };
      }
    });

    // 重启后端服务
    ipcMain.handle('system:restart-backend', async () => {
      log.info('🔄 重启后端服务...');
      try {
        if (this.backendProcess) {
          this.backendProcess.kill();
          this.backendProcess = null;
        }
        await this.startBackend({});
        log.info('✅ 后端服务重启成功');
        return { success: true };
      } catch (error) {
        log.error('❌ 后端服务重启失败:', error);
        return { success: false, error: error.message };
      }
    });

    // 重启所有服务
    ipcMain.handle('system:restart-all', async () => {
      log.info('🔄 重启所有服务...');
      try {
        // 停止所有服务
        if (this.frontendProcess) {
          this.frontendProcess.kill();
          this.frontendProcess = null;
        }
        if (this.backendProcess) {
          this.backendProcess.kill();
          this.backendProcess = null;
        }

        // 等待一下确保进程完全停止
        await new Promise(resolve => setTimeout(resolve, 2000));

        // 重新启动
        await this.startServices();
        log.info('✅ 所有服务重启成功');
        return { success: true };
      } catch (error) {
        log.error('❌ 服务重启失败:', error);
        return { success: false, error: error.message };
      }
    });

    // 停止所有服务
    ipcMain.handle('system:stop-all', async () => {
      log.info('⏹️ 停止所有服务...');
      try {
        this.cleanup();
        log.info('✅ 所有服务已停止');
        return { success: true };
      } catch (error) {
        log.error('❌ 停止服务失败:', error);
        return { success: false, error: error.message };
      }
    });

    // 获取系统状态
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
        }
      };
    });

    // ========== Supervisor 管理 IPC (通过 HTTP API 与 supervisor 通信) ==========

    // 获取 supervisor 管理的服务状态
    ipcMain.handle('supervisor:get-status', async () => {
      try {
        const http = require('http');

        return new Promise((resolve, reject) => {
          const req = http.get('http://127.0.0.1:7002/api/status', (res) => {
            let data = '';

            res.on('data', (chunk) => {
              data += chunk;
            });

            res.on('end', () => {
              try {
                const result = JSON.parse(data);
                // 添加前端状态
                result.data.frontend = {
                  running: this.frontendProcess !== null && !this.frontendProcess.killed,
                  pid: this.frontendProcess?.pid
                };
                resolve(result.data);
              } catch (error) {
                reject(error);
              }
            });
          });

          req.on('error', (error) => {
            reject(error);
          });

          req.setTimeout(5000, () => {
            req.destroy();
            reject(new Error('Request timeout'));
          });
        });
      } catch (error) {
        log.error('获取 supervisor 状态失败:', error);
        throw error;
      }
    });

    // 启动所有服务
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
                // 同时启动前端
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
        log.error('启动服务失败:', error);
        return { success: false, error: error.message };
      }
    });

    // 停止所有服务
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
                // 同时停止前端
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
        log.error('停止服务失败:', error);
        return { success: false, error: error.message };
      }
    });

    // 重启所有服务
    ipcMain.handle('supervisor:restart-all', async () => {
      try {
        const http = require('http');

        return new Promise((resolve, reject) => {
          const req = http.request({
            hostname: '127.0.0.1',
            port: 7002,
            path: '/api/restart',
            method: 'POST'
          }, (res) => {
            let data = '';

            res.on('data', (chunk) => {
              data += chunk;
            });

            res.on('end', () => {
              try {
                const result = JSON.parse(data);
                // 重启前端
                if (this.frontendProcess) {
                  this.frontendProcess.kill();
                  this.frontendProcess = null;
                }
                setTimeout(() => {
                  this.startFrontend();
                }, 2000);
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
        log.error('重启服务失败:', error);
        return { success: false, error: error.message };
      }
    });

    // 启动主应用
    ipcMain.handle('supervisor:launch-main-app', async () => {
      try {
        // 关闭启动管理器窗口
        if (this.launcherWindow) {
          this.launcherWindow.close();
          this.launcherWindow = null;
        }

        // 创建主窗口
        if (!this.mainWindow) {
          this.createMainWindow();
        }

        return { success: true };
      } catch (error) {
        log.error('启动主应用失败:', error);
        return { success: false, error: error.message };
      }
    });

    // ========== 打开设置窗口 ==========
    ipcMain.handle('window:openSettings', () => {
      log.info('⚙️ 打开设置窗口');
      this.createSettingsWindow();
      return { success: true };
    });

    // ========== 数据清理 IPC ==========
    ipcMain.handle('system:clear-video-data', async (event, options = {}) => {
      log.info('🗑️ 清理视频数据...');
      try {
        const http = require('http');

        return new Promise((resolve, reject) => {
          const req = http.request({
            hostname: '127.0.0.1',
            port: 7000,  // 修复: FastAPI 默认端口是 7000 而非 8000
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
                  log.info('✅ 视频数据清理成功');
                  resolve(result);
                } else {
                  log.error('❌ 视频数据清理失败:', result);
                  reject(new Error(result.detail || '清理失败'));
                }
              } catch (error) {
                log.error('❌ 解析响应失败:', error);
                reject(error);
              }
            });
          });

          req.on('error', (error) => {
            log.error('❌ 请求失败:', error);
            reject(error);
          });

          req.setTimeout(30000, () => {
            req.destroy();
            reject(new Error('Request timeout'));
          });

          req.end();
        });
      } catch (error) {
        log.error('❌ 清理视频数据失败:', error);
        return { success: false, error: error.message };
      }
    });

    log.info('✅ IPC 通信设置完成');
  }

  setupAppEvents() {
    // 当第二个实例尝试启动时，激活已有的窗口
    app.on('second-instance', (event, commandLine, workingDirectory) => {
      log.info('⚠️ 检测到第二个实例尝试启动，激活现有窗口');
      if (this.mainWindow) {
        if (this.mainWindow.isMinimized()) {
          this.mainWindow.restore();
        }
        this.mainWindow.focus();
      }
    });

    // 所有窗口关闭时退出应用（macOS 除外）
    app.on('window-all-closed', () => {
      if (process.platform !== 'darwin') {
        this.cleanup();
        app.quit();
      }
    });

    // macOS 激活应用时重新创建窗口
    app.on('activate', () => {
      if (this.mainWindow === null) {
        this.createMainWindow();
      }
    });

    // 应用退出前清理
    app.on('before-quit', () => {
      log.info('🔄 应用即将退出，清理资源...');
      this.cleanup();
    });
  }

  cleanup() {
    log.info('🧹 清理资源...');

    // 关闭所有可视化浏览器窗口
    for (const [id, win] of this.visualBrowserWindows) {
      if (!win.isDestroyed()) {
        win.close();
      }
    }
    this.visualBrowserWindows.clear();

    const stopProcess = (proc, label) => {
      if (proc && !proc.killed) {
        log.info(`🛑 终止${label}进程...`);
        proc.kill();
      }
    };

    stopProcess(this.frontendProcess, '前端');
    this.frontendProcess = null;

    stopProcess(this.celeryProcess, 'Celery');
    this.celeryProcess = null;

    stopProcess(this.playwrightWorkerProcess, 'Playwright Worker');
    this.playwrightWorkerProcess = null;

    stopProcess(this.backendProcess, '后端');
    this.backendProcess = null;

    stopProcess(this.redisProcess, 'Redis');
    this.redisProcess = null;

    log.info('✅ 资源清理完成');
  }
}

// 启动应用
const synapseApp = new SynapseApp();

// 捕获未处理的错误
process.on('uncaughtException', (error) => {
  log.error('❌ 未捕获的异常:', error);
});

process.on('unhandledRejection', (reason, promise) => {
  log.error('❌ 未处理的 Promise 拒绝:', reason);
});

// 初始化应用
synapseApp.initialize().catch((error) => {
  log.error('❌ 应用初始化失败:', error);
  if (app && app.quit) {
    app.quit();
  } else {
    process.exit(1);
  }
});
