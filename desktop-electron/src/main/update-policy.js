'use strict';

/**
 * 更新策略（参考 dsh-desktop update-policy.ts）：
 * - 定时检查（启动延迟 + 抖动，之后按间隔）
 * - 仅打包后的 macOS/Windows 构建支持自动更新
 * - autoDownload=false：发现更新只提示，用户确认才下载
 */

const UPDATE_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000; // 6 小时
const UPDATE_STARTUP_DELAY_MS = 15000;
const UPDATE_STARTUP_JITTER_MS = 15000;
const AUTO_INSTALL_ON_APP_QUIT = false;

function supportsAutoUpdates(isPackaged, platform) {
  return isPackaged && (platform === 'darwin' || platform === 'win32');
}

function shouldCheckAfterResume(lastCheckedAt, now = Date.now()) {
  return now - lastCheckedAt >= UPDATE_CHECK_INTERVAL_MS;
}

module.exports = {
  UPDATE_CHECK_INTERVAL_MS,
  UPDATE_STARTUP_DELAY_MS,
  UPDATE_STARTUP_JITTER_MS,
  AUTO_INSTALL_ON_APP_QUIT,
  supportsAutoUpdates,
  shouldCheckAfterResume
};
