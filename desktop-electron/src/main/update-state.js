'use strict';

/**
 * 更新状态机（参考 dsh-desktop update-state.ts）。
 * phase: idle | checking | available | downloading | downloaded | up-to-date | error | unsupported
 */

function initialUpdateStatus(currentVersion) {
  return { phase: 'idle', currentVersion, manual: false };
}

function clampPercent(value) {
  if (!Number.isFinite(value)) return 0;
  return Math.round(Math.min(100, Math.max(0, value)) * 10) / 10;
}

function reduceUpdateStatus(current, event) {
  const base = {
    currentVersion: current.currentVersion,
    manual: current.manual,
    downgrade: current.downgrade
  };

  switch (event.type) {
    case 'check':
      return { ...base, phase: 'checking', manual: event.manual };
    case 'available':
      return { ...base, phase: 'available', availableVersion: event.version };
    case 'progress':
      return { ...current, phase: 'downloading', percent: clampPercent(event.percent) };
    case 'downloaded':
      return { ...base, phase: 'downloaded', availableVersion: event.version };
    case 'not-available':
      return { ...base, phase: 'up-to-date' };
    case 'error':
      return { ...base, phase: 'error', message: event.message };
    case 'unsupported':
      return { ...base, phase: 'unsupported', message: event.message };
    case 'reset':
      return initialUpdateStatus(current.currentVersion);
    default:
      return current;
  }
}

module.exports = { initialUpdateStatus, reduceUpdateStatus, clampPercent };
