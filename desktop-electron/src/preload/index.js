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
    return invoke('supervisor:restart-all');
  }
};

// 暴露安全的 API 给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // Playwright 相关
  playwright: {
    getBrowserPath: () => invoke('playwright:getBrowserPath')
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

  // Supervisor 管理（用于启动管理器）
  supervisor: {
    getStatus: () => invoke('supervisor:get-status'),
    startAll: () => invoke('supervisor:start-all'),
    stopAll: () => invoke('supervisor:stop-all'),
    restartAll: () => invoke('supervisor:restart-all'),
    launchMainApp: () => invoke('supervisor:launch-main-app')
  },

  // 窗口管理
  window: {
    openSettings: () => invoke('window:openSettings')
  }
});

// 日志输出（开发模式）
console.log('🔧 Preload script loaded');
