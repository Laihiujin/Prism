const { contextBridge, ipcRenderer } = require('electron');

const invoke = (channel, ...args) => ipcRenderer.invoke(channel, ...args);

const isMissingRestartAllHandler = (error) =>
  String(error?.message || error || '').includes("No handler registered for 'system:restart-all'");

const restartAllWithFallback = async () => {
  try {
    return await invoke('system:restart-all');
  } catch (error) {
    if (!isMissingRestartAllHandler(error)) {
      throw error;
    }
    return invoke('pm2:restart-all');
  }
};

// 暴露安全的 API 给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // 浏览器自动化运行时
  automation: {
    getBrowserPath: () => invoke('automation:getBrowserPath')
  },

  // 浏览器窗口管理
  browser: {
    createVisual: (url, options) => invoke('browser:createVisual', url, options),
    closeVisual: (windowId) => invoke('browser:closeVisual', windowId)
  },

  // 会话管理
  session: {
    setCookies: (partition, cookies) => invoke('session:setCookies', partition, cookies)
  },

  // 应用信息
  app: {
    getInfo: () => invoke('app:getInfo')
  },

  settings: {
    get: () => invoke('settings:get'),
    update: (settings) => invoke('settings:update', settings)
  },

  browserRuntime: {
    getStatus: () => invoke('browserRuntime:getStatus'),
    install: (target) => invoke('browserRuntime:install', target),
    uninstall: (target) => invoke('browserRuntime:uninstall', target)
  },

  // 系统管理
  system: {
    restartFrontend: () => invoke('system:restart-frontend'),
    restartBackend: () => invoke('system:restart-backend'),
    restartAll: () => restartAllWithFallback(),
    restartApp: () => invoke('system:restart-app'),
    stopAll: () => invoke('system:stop-all'),
    quitApp: () => invoke('system:quit-app'),
    getStatus: () => invoke('system:get-status'),
    clearVideoData: (options) => invoke('system:clear-video-data', options)
  },

  // PM2 管理（用于启动管理器）
  pm2: {
    getStatus: () => invoke('pm2:get-status'),
    startAll: () => invoke('pm2:start-all'),
    stopAll: () => invoke('pm2:stop-all'),
    restartAll: () => invoke('pm2:restart-all'),
    launchMainApp: () => invoke('pm2:launch-main-app'),
    getDiagnostics: () => invoke('pm2:get-diagnostics')
  },

  // 自托管更新（electron-updater generic feed）
  updates: {
    getStatus: () => invoke('updates:status'),
    check: () => invoke('updates:check'),
    download: () => invoke('updates:download'),
    install: () => invoke('updates:install'),
    skip: (version) => invoke('updates:skip', version),
    listVersions: () => invoke('updates:list-versions'),
    installVersion: (version) => invoke('updates:install-version', version),
    onStatusChanged: (callback) => {
      const listener = (_event, status) => callback(status);
      ipcRenderer.on('updates:status-changed', listener);
      return () => ipcRenderer.removeListener('updates:status-changed', listener);
    }
  },

  // 窗口管理
  window: {
    openSettings: () => invoke('window:openSettings')
  }
});

// 日志输出（开发模式）
console.log('🔧 Preload script loaded');
