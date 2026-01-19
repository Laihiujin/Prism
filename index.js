const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const log = require('electron-log');
const fs = require('fs');

// Log configuration
log.transports.file.level = 'info';
log.transports.console.level = 'debug';
try {
  const userLogDir = path.join(app.getPath('userData'), 'logs');
  fs.mkdirSync(userLogDir, { recursive: true });
  log.transports.file.resolvePathFn = () => path.join(userLogDir, 'main.log');
} catch (error) {
  // ignore log path setup errors, fallback to default
}

class SynapseApp {
  constructor() {
    this.mainWindow = null;
    this.backendProcess = null;
    this.celeryProcess = null;
    this.redisProcess = null;
    this.playwrightWorkerProcess = null;
    this.frontendProcess = null;
    this.playwrightBrowserPath = null;
    this.visualBrowserWindows = new Map();
    this.servicesStarted = false;
  }

  async initialize() {
    log.info('🚀 SynapseAutomation 启动..');

    // 等待 Electron 准备就绪
    await app.whenReady();
    this.isDev = !app.isPackaged;
    this.repoRoot = path.join(__dirname, '../../../');

    // 1. 设置 Playwright 浏览器路
    this.setupPlaywrightPath();

    // 2. 启动后端/前端服务（生产默认启动，开发可SYNAPSE_START_SERVICES=1 强制
    const shouldStartServices = process.env.SYNAPSE_START_SERVICES === '1' || !this.isDev;
    if (shouldStartServices) {
      await this.startServices();
    }

    // 3. 创建主窗
    this.createMainWindow();

    // 4. 设置 IPC 处理
    this.setupIPC();

    // 5. 设置应用事件
    this.setupAppEvents();

    log.info('SynapseAutomation 启动完成');
  }

  setupPlaywrightPath() {
    // 获取打包后的资源路径
    const isDev = !app.isPackaged;

    if (isDev) {
      // 开发环境：使用项目根目录的浏览
      this.playwrightBrowserPath = path.join(__dirname, '../../../browsers');
      log.info('🔧 开发模- 浏览器路', this.playwrightBrowserPath);
    } else {
      // 生产环境：使用打包后的浏览器
      this.playwrightBrowserPath = path.join(process.resourcesPath, 'browsers');
      log.info('📦 生产模式 - 浏览器路', this.playwrightBrowserPath);
    }

    // 设置环境变量，让 Playwright 使用指定的浏览器
    process.env.PLAYWRIGHT_BROWSERS_PATH = this.playwrightBrowserPath;

    // 验证浏览器是否存
    if (fs.existsSync(this.playwrightBrowserPath)) {
      log.info('Playwright 浏览器路径已设置');
    } else {
      log.warn('⚠️ Playwright 浏览器路径不存在，自动化功能可能无法使用');
    }
  }

  getResourcesRoot() {
    return this.isDev  this.repoRoot : process.resourcesPath;
  }

  getBackendDir() {
    return this.isDev
       path.join(this.repoRoot, 'syn_backend')
      : path.join(process.resourcesPath, 'backend');
  }

  getPythonPath() {
    const pythonPath = path.join(this.getResourcesRoot(), 'synenv', 'Scripts', 'python.exe');
    if (fs.existsSync(pythonPath)) {
      return pythonPath;
    }
    return 'python';
  }

  getBrowsersRoot() {
    return this.isDev
       path.join(this.repoRoot, 'browsers')
      : path.join(process.resourcesPath, 'browsers');
  }

  resolveFirstPath(candidates) {
    return candidates.find((candidate) => candidate && fs.existsSync(candidate));
  }

  getServiceExe(name) {
    if (this.isDev) {
      return null;
    }
    const exePath = path.join(process.resourcesPath, 'services', `${name}.exe`);
    return fs.existsSync(exePath)  exePath : null;
  }

  buildServiceEnv() {
    const browsersRoot = this.getBrowsersRoot();
    const chromiumRoot = path.join(browsersRoot, 'chromium');
    const env = {
      ...process.env,
      PYTHONUTF8: '1',
      PYTHONIOENCODING: 'utf-8',
      PLAYWRIGHT_BROWSERS_PATH: chromiumRoot
    };

    const chromePath = this.resolveFirstPath([
      path.join(chromiumRoot, 'chromium-1161', 'chrome-win', 'chrome.exe'),
      path.join(browsersRoot, 'chrome-for-testing', 'chrome-143.0.7499.169', 'chrome-win64', 'chrome.exe')
    ]);
    if (chromePath) {
      env.LOCAL_CHROME_PATH = chromePath;
    }

    const firefoxPath = this.resolveFirstPath([
      path.join(browsersRoot, 'firefox', 'firefox-1495', 'firefox', 'firefox.exe')
    ]);
    if (firefoxPath) {
      env.LOCAL_FIREFOX_PATH = firefoxPath;
    }

    return env;
  }

  async startServices() {
    if (this.servicesStarted) {
      return;
    }
    const env = this.buildServiceEnv();
    this.startRedis(env);
    this.startPlaywrightWorker(env);
    await this.startBackend(env);
    this.startCelery(env);
    this.startFrontend(env);
    this.servicesStarted = true;
  }

  startRedis(env) {
    if (this.redisProcess) {
      return;
    }
    const redisPath = this.isDev
       'redis-server'
      : path.join(process.resourcesPath, 'redis', 'redis-server.exe');
    if (!this.isDev && !fs.existsSync(redisPath)) {
      log.warn(`⚠️ Redis 未找 ${redisPath}`);
      return;
    }
    log.info('🧩 启动 Redis...');
    this.redisProcess = spawn(redisPath, [], {
      env,
      cwd: this.getResourcesRoot(),
      windowsHide: true
    });
    this.redisProcess.stdout.on('data', (data) => log.info('[Redis]', data.toString()));
    this.redisProcess.stderr.on('data', (data) => log.error('[Redis Error]', data.toString()));
    this.redisProcess.on('exit', (code) => {
      log.warn(`⚠️ Redis 退出，退出码: ${code}`);
    });
  }

  startPlaywrightWorker(env) {
    if (this.playwrightWorkerProcess) {
      return;
    }
    const backendDir = this.getBackendDir();
    const workerExe = this.getServiceExe('playwright-worker');
    const workerScript = path.join(backendDir, 'playwright_worker', 'worker.py');
    if (!workerExe && !fs.existsSync(workerScript)) {
      log.warn(`⚠️ Playwright Worker 未找 ${workerScript}`);
      return;
    }
    const pythonPath = this.getPythonPath();
    log.info('🧩 启动 Playwright Worker...');
    const launchCmd = workerExe || pythonPath;
    const launchArgs = workerExe  [] : [workerScript];
    this.playwrightWorkerProcess = spawn(launchCmd, launchArgs, {
      env: { ...env, PYTHONPATH: backendDir },
      cwd: backendDir,
      windowsHide: true
    });
    this.playwrightWorkerProcess.stdout.on('data', (data) => log.info('[Worker]', data.toString()));
    this.playwrightWorkerProcess.stderr.on('data', (data) => log.error('[Worker Error]', data.toString()));
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
    const launchCmd = celeryExe || pythonPath;
    const launchArgs = celeryExe
       []
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
    this.celeryProcess = spawn(launchCmd, launchArgs, {
      env: { ...env, PYTHONPATH: backendDir },
      cwd: backendDir,
      windowsHide: true
    });
    this.celeryProcess.stdout.on('data', (data) => log.info('[Celery]', data.toString()));
    this.celeryProcess.stderr.on('data', (data) => log.error('[Celery Error]', data.toString()));
    this.celeryProcess.on('exit', (code) => {
      log.warn(`⚠️ Celery 退出，退出码: ${code}`);
    });
  }

  startFrontend(env) {
    if (this.frontendProcess || this.isDev) {
      if (this.isDev) {
        log.info('ℹ️ 开发模式未自动启动前端');
      }
      return;
    }
    const frontendDir = path.join(process.resourcesPath, 'frontend', 'standalone');
    const serverJs = path.join(frontendDir, 'server.js');
    if (!fs.existsSync(serverJs)) {
      log.warn(`⚠️ 前端服务器未找到: ${serverJs}`);
      return;
    }
    log.info('🧩 启动前端服务...');
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
    this.frontendProcess.stdout.on('data', (data) => log.info('[Frontend]', data.toString()));
    this.frontendProcess.stderr.on('data', (data) => log.error('[Frontend Error]', data.toString()));
    this.frontendProcess.on('exit', (code) => {
      log.warn(`⚠️ 前端服务退出，退出码: ${code}`);
    });
  }

  async startBackend(env) {
    if (this.backendProcess) {
      return;
    }
    const backendDir = this.getBackendDir();
    const backendExe = this.getServiceExe('backend');
    const pythonPath = this.getPythonPath();
    const mainScript = path.join(backendDir, 'fastapi_app', 'run.py');

    log.info('🔄 启动 FastAPI 后端...');
    log.info('Python 路径:', pythonPath);
    log.info('主脚', mainScript);

    return new Promise((resolve, reject) => {
      if (!backendExe && !fs.existsSync(mainScript)) {
        log.warn(`⚠️ FastAPI 脚本未找 ${mainScript}`);
        resolve();
        return;
      }

      const launchCmd = backendExe || pythonPath;
      const launchArgs = backendExe  [] : [mainScript];
      this.backendProcess = spawn(launchCmd, launchArgs, {
        cwd: backendDir,
        env: {
          ...env,
          PYTHONPATH: backendDir
        },
        windowsHide: true
      });

      this.backendProcess.stdout.on('data', (data) => {
        const output = data.toString();
        log.info('[Backend]', output);
        if (output.includes('Uvicorn running') || output.includes('Application startup complete')) {
          log.info('FastAPI 后端启动成功');
          resolve();
        }
      });

      this.backendProcess.stderr.on('data', (data) => {
        log.error('[Backend Error]', data.toString());
      });

      this.backendProcess.on('error', (error) => {
        log.error('后端进程启动失败:', error);
        reject(error);
      });

      this.backendProcess.on('exit', (code) => {
        log.warn(`⚠️ 后端进程退出，退出码: ${code}`);
      });

      setTimeout(() => {
        log.warn('⚠️ 后端启动超时，继续启动应');
        resolve();
      }, 10000);
    });
  }

  createMainWindow() {
    log.info('🪟 创建主窗..');

    this.mainWindow = new BrowserWindow({
      width: 1400,
      height: 900,
      minWidth: 1200,
      minHeight: 700,
      show: false,
      backgroundColor: '#ffffff',
      titleBarStyle: 'default',
      autoHideMenuBar: true,
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
      log.info('主窗口显示完');
    });

    // 窗口关闭事件
    this.mainWindow.on('closed', () => {
      this.mainWindow = null;
      log.info('🪟 主窗口已关闭');
    });
  }

  setupIPC() {
    log.info('🔗 设置 IPC 通信...');

    // 获取 Playwright 浏览器路

    ipcMain.handle('playwright:getBrowserPath', () => {
      return this.playwrightBrowserPath;
    });

    // 创建可视化浏览器窗口（用于调试和预览
    ipcMain.handle('browser:createVisual', async (event, url, options = {}) => {
      log.info('🌐 创建可视化浏览器窗口:', url);

      const browserWindow = new BrowserWindow({
        width: options.width || 1200,
        height: options.height || 800,
        show: true,
        title: options.title || '浏览器预',
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
      log.info(`🍪 为分${partition} 设置 ${cookies.length} Cookies`);
      const { session } = require('electron');
      const sess = session.fromPartition(partition);

      const promises = cookies.map(cookie => {
        // Playwright cookie 格式Electron cookie 格式
        const url = `${cookie.secure  'https' : 'http'}://${cookie.domain.startsWith('.')  cookie.domain.substring(1) : cookie.domain}${cookie.path}`;
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
        log.info(`分区 ${partition} Cookies 设置成功`);
        return true;
      } catch (error) {
        log.error(`分区 ${partition} Cookies 设置失败:`, error);
        return false;
      }
    });

    log.info('IPC 通信设置完成');
  }

  setupAppEvents() {
    // 所有窗口关闭时退出应用（macOS 除外
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

    // 关闭所有可视化浏览器窗
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

    log.info('资源清理完成');
  }
}

// Log configuration
const synapseApp = new SynapseApp();

// Log configuration
process.on('uncaughtException', (error) => {
  log.error('未捕获的异常:', error);
});

process.on('unhandledRejection', (reason, promise) => {
  log.error('未处理的 Promise 拒绝:', reason);
});

// Initialize app
synapseApp.initialize().catch((error) => {
  log.error('App initialization failed', error);
  app.quit();
});