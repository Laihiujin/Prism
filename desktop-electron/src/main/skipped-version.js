'use strict';

const { readFileSync, writeFileSync } = require('node:fs');
const { join } = require('node:path');

/**
 * 用户跳过某个版本的持久化记录（参考 dsh-desktop skipped-version.ts）。
 * 手动检查会忽略 skip —— 这是用户主动收回跳过的途径。
 */

function skippedVersionPath(userDataPath) {
  return join(userDataPath, 'update-skip.json');
}

function shouldOfferUpdate(version, skippedVersion, manual) {
  return manual || version !== skippedVersion;
}

function readSkippedVersion(filePath) {
  try {
    const value = JSON.parse(readFileSync(filePath, 'utf8'));
    return typeof value.version === 'string' && value.version ? value.version : undefined;
  } catch (error) {
    return undefined;
  }
}

function writeSkippedVersion(filePath, version) {
  try {
    writeFileSync(filePath, `${JSON.stringify({ version }, undefined, 2)}\n`, 'utf8');
    return true;
  } catch (error) {
    return false;
  }
}

module.exports = {
  skippedVersionPath,
  shouldOfferUpdate,
  readSkippedVersion,
  writeSkippedVersion
};
