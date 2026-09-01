'use strict';

/**
 * 更新管理器（CJS 移植自 dsh-desktop update-manager.ts）。
 *
 * 策略：
 * - autoDownload=false：发现更新只提示，用户确认后才下载
 * - 启动延迟 + 抖动后首次检查，之后按 UPDATE_CHECK_INTERVAL_MS 定时检查；
 *   系统从睡眠恢复时若距上次检查超过间隔也补查一次
 * - skipped-version：跳过的版本不再提示（手动检查可收回）
 * - 下载完成后 quitAndInstall；安装前回调 prepareToInstall（如停掉后端服务）
 * - 版本索引（versions.json）+ 归档 feed：可安装任意历史版本（含回滚，allowDowngrade）
 */

const { app, BrowserWindow, ipcMain, powerMonitor } = require('electron');
const electronUpdater = require('electron-updater');
const {
  AUTO_INSTALL_ON_APP_QUIT,
  shouldCheckAfterResume,
  supportsAutoUpdates,
  UPDATE_CHECK_INTERVAL_MS,
  UPDATE_STARTUP_DELAY_MS,
  UPDATE_STARTUP_JITTER_MS
} = require('./update-policy');
const { initialUpdateStatus, reduceUpdateStatus } = require('./update-state');
const {
  readSkippedVersion,
  shouldOfferUpdate,
  skippedVersionPath,
  writeSkippedVersion
} = require('./skipped-version');
const {
  archiveFeedUrl,
  compareVersions,
  fetchAvailableReleases,
  OWNER,
  REPO
} = require('./version-catalog');

const { autoUpdater } = electronUpdater;
const TRANSIENT_STATUS_MS = 8000;

let status = initialUpdateStatus(app.getVersion());
let prepareToInstall = undefined;
let startupTimer = undefined;
let intervalTimer = undefined;
let resetTimer = undefined;
let checkPromise = undefined;
let lastCheckedAt = 0;
let installing = false;
let downloading = false;
let started = false;
let handlersRegistered = false;
let skippedVersion = undefined;
let skipLoaded = false;
let manualCheck = false;
let pendingDowngrade = false;

function getUpdateStatus() {
  return { ...status };
}

function registerUpdateHandlers() {
  if (handlersRegistered) return;
  handlersRegistered = true;
  ipcMain.handle('updates:status', () => getUpdateStatus());
  ipcMain.handle('updates:check', () => checkForUpdates(true));
  ipcMain.handle('updates:install', () => installDownloadedUpdate());
  ipcMain.handle('updates:skip', (_event, version) => skipUpdate(version));
  ipcMain.handle('updates:download', () => downloadAvailableUpdate());
  ipcMain.handle('updates:list-versions', () => fetchAvailableReleases(app.getVersion()));
  ipcMain.handle('updates:install-version', (_event, version) => installSpecificVersion(version));
}

function skipFile() {
  return skippedVersionPath(app.getPath('userData'));
}

function currentSkippedVersion() {
  if (!skipLoaded) {
    skippedVersion = readSkippedVersion(skipFile());
    skipLoaded = true;
  }
  return skippedVersion;
}

function skipUpdate(version) {
  if (typeof version !== 'string' || !version) return getUpdateStatus();
  skippedVersion = version;
  skipLoaded = true;
  writeSkippedVersion(skipFile(), version);
  transition({ type: 'reset' });
  return getUpdateStatus();
}

function startUpdateManager(options) {
  prepareToInstall = options.prepareToInstall;
  if (started) return;
  started = true;

  if (!supportsUpdates()) {
    transition({
      type: 'unsupported',
      message: '仅安装版（macOS/Windows）支持自动更新。'
    });
    return;
  }

  configureUpdater();
  registerUpdaterEvents();
  startupTimer = setTimeout(
    () => void checkForUpdates(),
    UPDATE_STARTUP_DELAY_MS + Math.random() * UPDATE_STARTUP_JITTER_MS
  );
  intervalTimer = setInterval(() => void checkForUpdates(), UPDATE_CHECK_INTERVAL_MS);
  powerMonitor.on('resume', checkAfterResume);
}

async function checkForUpdates(manual = false) {
  if (!supportsUpdates()) {
    transition(
      {
        type: 'unsupported',
        message: '仅安装版（macOS/Windows）支持自动更新。'
      },
      manual
    );
    if (manual) scheduleReset();
    return getUpdateStatus();
  }

  if (checkPromise || ['available', 'downloading', 'downloaded'].includes(status.phase)) {
    return getUpdateStatus();
  }

  transition({ type: 'check', manual });
  manualCheck = manual;
  lastCheckedAt = Date.now();
  checkPromise = autoUpdater.checkForUpdates();

  try {
    await checkPromise;
  } catch (error) {
    transition({ type: 'error', message: errorMessage(error) });
    if (manual) scheduleReset();
  } finally {
    checkPromise = undefined;
  }

  return getUpdateStatus();
}

async function downloadAvailableUpdate() {
  if (status.phase !== 'available' || downloading) return getUpdateStatus();
  downloading = true;

  try {
    await autoUpdater.downloadUpdate();
  } catch (error) {
    transition({ type: 'error', message: errorMessage(error) });
    if (status.manual) scheduleReset();
  } finally {
    downloading = false;
  }

  return getUpdateStatus();
}

async function installSpecificVersion(version) {
  if (typeof version !== 'string' || !version) return getUpdateStatus();
  if (!supportsUpdates()) return getUpdateStatus();
  if (checkPromise || ['checking', 'downloading', 'downloaded'].includes(status.phase)) {
    return getUpdateStatus();
  }

  pendingDowngrade = compareVersions(version, app.getVersion()) < 0;
  autoUpdater.setFeedURL({ provider: 'generic', url: archiveFeedUrl(version) });
  autoUpdater.allowDowngrade = true;
  manualCheck = true;
  transition({ type: 'check', manual: true });
  lastCheckedAt = Date.now();
  checkPromise = autoUpdater.checkForUpdates();

  try {
    await checkPromise;
    if (status.phase === 'available' && status.availableVersion === version) {
      await downloadAvailableUpdate();
    } else if (status.phase !== 'downloading' && status.phase !== 'downloaded') {
      transition({ type: 'error', message: '在更新源未找到该版本' });
      scheduleReset();
    }
  } catch (error) {
    transition({ type: 'error', message: errorMessage(error) });
    scheduleReset();
  } finally {
    checkPromise = undefined;
    configureUpdater(); // 恢复 GitHub Releases 主通道
    pendingDowngrade = false;
  }

  return getUpdateStatus();
}

async function installDownloadedUpdate() {
  if (status.phase !== 'downloaded' || installing) return;
  installing = true;

  try {
    await prepareToInstall?.();
    autoUpdater.quitAndInstall(false, true);
  } catch (error) {
    installing = false;
    transition({ type: 'error', message: errorMessage(error) }, true);
    scheduleReset();
  }
}

function stopUpdateManager() {
  if (startupTimer) clearTimeout(startupTimer);
  if (intervalTimer) clearInterval(intervalTimer);
  if (resetTimer) clearTimeout(resetTimer);
  startupTimer = undefined;
  intervalTimer = undefined;
  resetTimer = undefined;
  if (started && app.isReady()) powerMonitor.removeListener('resume', checkAfterResume);
}

function configureUpdater() {
  autoUpdater.autoDownload = false;
  autoUpdater.allowDowngrade = false;
  autoUpdater.autoInstallOnAppQuit = AUTO_INSTALL_ON_APP_QUIT;
  autoUpdater.allowPrerelease = false;
  // 主通道：GitHub Releases（与 package.json build.publish 一致）。
  // electron-builder 打包时也会写入 app-update.yml，这里显式设置保证开发/测试一致。
  autoUpdater.setFeedURL({ provider: 'github', owner: OWNER, repo: REPO, private: false });
  autoUpdater.logger = {
    info: (...args) => console.info('[updater]', ...args),
    warn: (...args) => console.warn('[updater]', ...args),
    error: (...args) => console.error('[updater]', ...args),
    debug: (...args) => console.debug('[updater]', ...args)
  };
}

let updaterEventsRegistered = false;

function registerUpdaterEvents() {
  if (updaterEventsRegistered) return;
  updaterEventsRegistered = true;
  autoUpdater.on('checking-for-update', () => transition({ type: 'check', manual: status.manual }));
  autoUpdater.on('update-available', (info) => {
    if (!shouldOfferUpdate(info.version, currentSkippedVersion(), manualCheck)) {
      console.info('[updater] skipping', info.version, 'at the user request');
      transition({ type: 'reset' });
      return;
    }
    transition({ type: 'available', version: info.version });
  });
  autoUpdater.on('download-progress', (progress) =>
    transition({ type: 'progress', percent: progress.percent })
  );
  autoUpdater.on('update-not-available', () => {
    transition({ type: 'not-available' });
    scheduleReset();
  });
  autoUpdater.on('update-downloaded', (info) =>
    transition({ type: 'downloaded', version: info.version })
  );
  autoUpdater.on('error', (error) => {
    transition({ type: 'error', message: errorMessage(error) });
    if (status.manual) scheduleReset();
  });
}

function transition(event, manualOverride) {
  if (event.type !== 'reset' && resetTimer) {
    clearTimeout(resetTimer);
    resetTimer = undefined;
  }

  status = reduceUpdateStatus(status, event);
  if (manualOverride !== undefined) status.manual = manualOverride;
  if (pendingDowngrade && event.type !== 'reset') status.downgrade = true;

  console.info('[updater] status', status.phase, status.percent ?? '');
  for (const window of BrowserWindow.getAllWindows()) {
    if (!window.isDestroyed()) window.webContents.send('updates:status-changed', getUpdateStatus());
  }
}

function scheduleReset() {
  if (!status.manual) return;
  if (resetTimer) clearTimeout(resetTimer);
  resetTimer = setTimeout(() => transition({ type: 'reset' }), TRANSIENT_STATUS_MS);
}

function checkAfterResume() {
  if (shouldCheckAfterResume(lastCheckedAt)) void checkForUpdates();
}

function supportsUpdates() {
  return supportsAutoUpdates(app.isPackaged, process.platform);
}

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}

module.exports = {
  getUpdateStatus,
  registerUpdateHandlers,
  startUpdateManager,
  stopUpdateManager,
  checkForUpdates,
  downloadAvailableUpdate,
  installSpecificVersion,
  installDownloadedUpdate,
  skipUpdate
};
