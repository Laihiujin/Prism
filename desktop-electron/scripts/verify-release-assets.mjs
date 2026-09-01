import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { open, readFile, readdir, stat } from 'node:fs/promises';
import { basename, join, resolve } from 'node:path';

/**
 * 发布产物校验（参考 dsh-desktop verify-release-assets.mjs，Prism Windows 优先）。
 *
 * 校验：
 * - 必需产物存在：<version>-setup.exe / .exe.blockmap / latest.yml
 * - 文件头（MZ）与最小体积（防止截断/损坏）
 * - latest.yml 中的 sha512 / size 与安装包一致
 * - blockmap 存在且非空
 *
 * 用法：node scripts/verify-release-assets.mjs <release-dir> <semver>
 */
const MIN_BYTES = {
  exe: 50 * 1024 * 1024,
  blockmap: 1024,
  yml: 64
};

function requiredAssets(version) {
  return [
    `Prism-${version}-setup.exe`,
    `Prism-${version}-setup.exe.blockmap`,
    'latest.yml'
  ];
}

function assetKind(name) {
  if (name.endsWith('.exe.blockmap')) return 'blockmap';
  if (name.endsWith('.exe')) return 'exe';
  if (name.endsWith('.yml')) return 'yml';
  return null;
}

/**
 * 极简 YAML 解析，仅覆盖 electron-builder latest.yml 的固定结构：
 *   version / files(- url,sha512,size) / path / sha512 / size / releaseDate
 */
function parseLatestYaml(text) {
  const out = {};
  const lines = String(text || '').split(/\r?\n/);
  let currentList = null;
  for (const rawLine of lines) {
    const line = rawLine.replace(/\s+$/, '');
    if (!line.trim() || line.trim().startsWith('#')) continue;
    const indent = (line.match(/^\s*/) || [''])[0].length;

    if (indent === 0) {
      const m = line.match(/^([A-Za-z0-9_.-]+):\s*(.*)$/);
      if (!m) continue;
      const value = m[2].trim().replace(/^"|"$/g, '');
      out[m[1]] = value;
      currentList = m[1] === 'files' ? [] : null;
      if (m[1] === 'files') out.files = currentList;
    } else if (currentList && indent === 2 && line.trim().startsWith('-')) {
      currentList.push({});
    } else if (currentList && currentList.length > 0) {
      const m = line.match(/^\s*([A-Za-z0-9_.-]+):\s*(.*)$/);
      if (m) {
        currentList[currentList.length - 1][m[1]] = m[2].trim().replace(/^"|"$/g, '');
      }
    }
  }
  return out;
}

async function sha512(file) {
  const hash = createHash('sha512');
  await new Promise((resolvePromise, rejectPromise) => {
    const stream = createReadStream(file);
    stream.on('data', (chunk) => hash.update(chunk));
    stream.on('error', rejectPromise);
    stream.on('end', resolvePromise);
  });
  return hash.digest('base64');
}

async function assertExeHeader(file) {
  const handle = await open(file, 'r');
  try {
    const header = Buffer.alloc(2);
    const { bytesRead } = await handle.read(header, 0, header.length, 0);
    if (bytesRead !== header.length || !header.equals(Buffer.from('MZ'))) {
      throw new Error(`${basename(file)}: 文件头不是有效的 PE 可执行文件（MZ）`);
    }
  } finally {
    await handle.close();
  }
}

async function verifyRelease(releaseDir, version) {
  const errors = [];
  const entries = await readdir(releaseDir, { withFileTypes: true });

  for (const assetName of requiredAssets(version)) {
    const assetPath = join(releaseDir, assetName);
    const kind = assetKind(assetName);
    if (!entries.some((entry) => entry.isFile() && entry.name === assetName)) {
      errors.push(`缺失产物: ${assetName}`);
      continue;
    }
    const info = await stat(assetPath);
    const minBytes = MIN_BYTES[kind] || 0;
    if (info.size < minBytes) {
      errors.push(`${assetName}: 体积异常（${info.size} < ${minBytes}）`);
    }
    if (kind === 'exe') {
      await assertExeHeader(assetPath);
    }
  }

  const ymlPath = join(releaseDir, 'latest.yml');
  const yml = parseLatestYaml(await readFile(ymlPath, 'utf8'));
  const installerName = yml.path;
  if (!installerName) {
    errors.push('latest.yml: 缺少 path 字段');
  } else {
    const installerPath = join(releaseDir, installerName);
    if (!entries.some((entry) => entry.isFile() && entry.name === installerName)) {
      errors.push(`latest.yml 引用的安装包不存在: ${installerName}`);
    } else {
      const info = await stat(installerPath);
      if (String(yml.sha512) !== (await sha512(installerPath))) {
        errors.push('latest.yml sha512 与安装包不一致');
      }
      if (Number(yml.size) !== info.size) {
        errors.push(`latest.yml size(${yml.size}) 与安装包(${info.size})不一致`);
      }
    }
  }

  if (errors.length > 0) {
    throw new Error(`发布产物校验失败:\n${errors.map((e) => ` - ${e}`).join('\n')}`);
  }
  console.log(`Release assets verified OK for ${version}: exe + blockmap + latest.yml`);
}

const [releaseDirArg, version] = process.argv.slice(2);
if (!releaseDirArg || !/^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/.test(version ?? '')) {
  throw new Error('Usage: verify-release-assets.mjs <release-dir> <semver>');
}

await verifyRelease(resolve(releaseDirArg), version);
