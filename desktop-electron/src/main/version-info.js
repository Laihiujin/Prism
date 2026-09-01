'use strict';

/**
 * 双版本体系（参考 dsh-desktop version-info.ts）：
 * - 桌面壳版本：package.json / app.getVersion()
 * - 内置服务版本：prism_backend/VERSION + tools/hermes-agent + frontend standalone
 *   服务随桌面壳一起更新（"Harness 随 DSH Desktop 更新"的 Prism 版本）
 */

const fs = require('node:fs');
const path = require('node:path');

function readJsonVersion(filePath) {
  try {
    if (!filePath || !fs.existsSync(filePath)) return null;
    const parsed = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    return typeof parsed.version === 'string' && parsed.version ? parsed.version : null;
  } catch (error) {
    return null;
  }
}

function readTextVersion(filePath) {
  try {
    if (!filePath || !fs.existsSync(filePath)) return null;
    const value = fs.readFileSync(filePath, 'utf8').trim();
    return value || null;
  } catch (error) {
    return null;
  }
}

/**
 * 收集内置服务版本。resourcesRoot（打包后 process.resourcesPath）
 * 与 repoRoot（开发时项目根）都探测，取先命中的。
 */
function bundledServiceVersions(resourcesRoot, repoRoot) {
  const roots = [resourcesRoot, repoRoot].filter(Boolean);

  let backend = null;
  let hermes = null;
  let frontend = null;

  for (const root of roots) {
    if (backend === null) {
      backend = readTextVersion(path.join(root, 'prism_backend', 'VERSION'));
    }
    if (hermes === null) {
      hermes = readJsonVersion(path.join(root, 'tools', 'hermes-agent', 'package.json'));
    }
    if (frontend === null) {
      frontend = readJsonVersion(path.join(root, 'frontend', 'standalone', 'package.json'));
    }
    if (backend !== null && hermes !== null && frontend !== null) break;
  }

  return { backend, hermes, frontend };
}

function getVersionInfo(appVersion, resourcesRoot, repoRoot) {
  return {
    desktop: appVersion,
    bundled: bundledServiceVersions(resourcesRoot, repoRoot)
  };
}

function aboutDetail(versionInfo, locale = 'zh') {
  const desktop = versionInfo?.desktop ?? '?';
  const bundled = versionInfo?.bundled || {};
  const fmt = (value) => value || (locale === 'zh' ? '未知' : 'Unknown');
  if (locale === 'zh') {
    return [
      `Prism 桌面版版本：${desktop}`,
      `内置后端版本：${fmt(bundled.backend)}`,
      `内置 Hermes Agent 版本：${fmt(bundled.hermes)}`,
      `内置前端版本：${fmt(bundled.frontend)}`,
      '',
      '内置服务随 Prism 桌面版一起更新。'
    ].join('\n');
  }
  return [
    `Prism Desktop version: ${desktop}`,
    `Bundled backend version: ${fmt(bundled.backend)}`,
    `Bundled Hermes Agent version: ${fmt(bundled.hermes)}`,
    `Bundled frontend version: ${fmt(bundled.frontend)}`,
    '',
    'Bundled services are updated with Prism Desktop.'
  ].join('\n');
}

module.exports = { getVersionInfo, bundledServiceVersions, aboutDetail };
