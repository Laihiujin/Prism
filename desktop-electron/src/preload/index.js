const { contextBridge, ipcRenderer } = require('electron');

// 暴露安全的 API 给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // Playwright 相关
  playwright: {
    getBrowserPath: () => ipcRenderer.invoke('playwright:getBrowserPath')
  },

  // 浏览器窗口管理
  browser: {
    createVisual: (url, options) => ipcRenderer.invoke('browser:createVisual', url, options),
    closeVisual: (windowId) => ipcRenderer.invoke('browser:closeVisual', windowId)
  },

  // 会话管理
  session: {
    setCookies: (partition, cookies) => ipcRenderer.invoke('session:setCookies', partition, cookies)
  },

  // 应用信息
  app: {
    getInfo: () => ipcRenderer.invoke('app:getInfo')
  },

  // 系统管理
  system: {
    restartFrontend: () => ipcRenderer.invoke('system:restart-frontend'),
    restartBackend: () => ipcRenderer.invoke('system:restart-backend'),
    restartAll: () => ipcRenderer.invoke('system:restart-all'),
    stopAll: () => ipcRenderer.invoke('system:stop-all'),
    quitApp: () => ipcRenderer.invoke('system:quit-app'),
    getStatus: () => ipcRenderer.invoke('system:get-status'),
    clearVideoData: (options) => ipcRenderer.invoke('system:clear-video-data', options)
  },

  // Supervisor 管理（用于启动管理器）
  supervisor: {
    getStatus: () => ipcRenderer.invoke('supervisor:get-status'),
    startAll: () => ipcRenderer.invoke('supervisor:start-all'),
    stopAll: () => ipcRenderer.invoke('supervisor:stop-all'),
    restartAll: () => ipcRenderer.invoke('supervisor:restart-all'),
    launchMainApp: () => ipcRenderer.invoke('supervisor:launch-main-app')
  },

  // 窗口管理
  window: {
    openSettings: () => ipcRenderer.invoke('window:openSettings')
  }
});

// 日志输出（开发模式）
console.log('🔧 Preload script loaded');
