const { contextBridge, ipcRenderer } = require('electron');

const invoke = (channel, ...args) => ipcRenderer.invoke(channel, ...args);

contextBridge.exposeInMainWorld('electronAPI', {
  playwright: {
    getBrowserPath: () => invoke('playwright:getBrowserPath')
  },
  browser: {
    createVisual: (url, options) => invoke('browser:createVisual', url, options),
    closeVisual: (windowId) => invoke('browser:closeVisual', windowId),
    openCreatorTab: (payload) => ipcRenderer.sendToHost('OPEN_CREATOR_TAB', payload)
  },
  session: {
    setCookies: (partition, cookies) => invoke('session:setCookies', partition, cookies)
  },
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
  system: {
    restartFrontend: () => invoke('system:restart-frontend'),
    restartBackend: () => invoke('system:restart-backend'),
    restartAll: () => invoke('system:restart-all'),
    restartApp: () => invoke('system:restart-app'),
    stopAll: () => invoke('system:stop-all'),
    quitApp: () => invoke('system:quit-app'),
    getStatus: () => invoke('system:get-status'),
    clearVideoData: (options) => invoke('system:clear-video-data', options)
  },
  supervisor: {
    getStatus: () => invoke('supervisor:get-status'),
    startAll: () => invoke('supervisor:start-all'),
    stopAll: () => invoke('supervisor:stop-all'),
    restartAll: () => invoke('supervisor:restart-all'),
    launchMainApp: () => invoke('supervisor:launch-main-app')
  }
});
