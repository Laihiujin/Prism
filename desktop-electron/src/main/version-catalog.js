'use strict';

/**
 * 版本目录（适配 GitHub Releases 更新通道）。
 *
 * - 主更新通道：electron-updater 的 github provider（package.json build.publish），
 *   自动指向 GitHub Releases 最新版本资产（latest.yml / 安装包 / blockmap）。
 * - 回滚/历史版本：GitHub API 拉 release 列表 + generic feed 指向
 *   https://github.com/<owner>/<repo>/releases/download/<tag>/（allowDowngrade 可回滚）。
 *
 * 仓库可通过 env PRISM_GITHUB_REPO（默认 Laihiujin/Prism）覆盖。
 */

const REPOSITORY = (process.env.PRISM_GITHUB_REPO || 'Laihiujin/Prism').replace(/^https?:\/\/github\.com\//, '').replace(/\.git$/, '');
const [OWNER, REPO] = REPOSITORY.split('/').map((part) => part.trim()).filter(Boolean);
const GH_API_RELEASES = `https://api.github.com/repos/${OWNER}/${REPO}/releases?per_page=100`;
const GH_RELEASES_DOWNLOAD = `https://github.com/${OWNER}/${REPO}/releases/download`;
const INDEX_TIMEOUT_MS = 8000;

function archiveFeedUrl(version) {
  // GitHub Release 的 tag 约定为 v<version>（见 build-version-index.mjs / 发布流程）
  const tag = /^v\d/.test(version) ? version : `v${version}`;
  return `${GH_RELEASES_DOWNLOAD}/${tag}/`;
}

function splitVersion(value) {
  const [core = '', ...preParts] = String(value || '').trim().split('-');
  const nums = core.split('.').map((part) => {
    const parsed = Number.parseInt(part, 10);
    return Number.isFinite(parsed) ? parsed : 0;
  });
  while (nums.length < 3) nums.push(0);
  return { nums, pre: preParts.join('-') };
}

function compareVersions(a, b) {
  const left = splitVersion(a);
  const right = splitVersion(b);
  for (let i = 0; i < Math.max(left.nums.length, right.nums.length); i += 1) {
    const diff = (left.nums[i] ?? 0) - (right.nums[i] ?? 0);
    if (diff !== 0) return diff < 0 ? -1 : 1;
  }
  if (left.pre === right.pre) return 0;
  if (!left.pre) return 1; // release > prerelease
  if (!right.pre) return -1;
  return left.pre < right.pre ? -1 : 1;
}

/**
 * 从 GitHub API release 列表解析可用版本（跳过 draft；prerelease 标记保留）。
 */
async function fetchAvailableReleases(currentVersion, fetchImpl = globalThis.fetch) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), INDEX_TIMEOUT_MS);
  try {
    const response = await fetchImpl(GH_API_RELEASES, {
      signal: controller.signal,
      headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'Prism-Desktop' }
    });
    if (!response.ok) {
      throw new Error(`GitHub releases request failed: ${response.status}`);
    }
    const releases = await response.json();
    if (!Array.isArray(releases)) {
      return [];
    }

    const available = [];
    for (const release of releases) {
      if (!release || release.draft) continue;
      const tag = String(release.tag_name || '');
      const version = tag.replace(/^v/i, '');
      if (!version || !/^\d+\.\d+\.\d+/.test(version)) continue;
      available.push({
        version,
        tag,
        archiveUrl: `${GH_RELEASES_DOWNLOAD}/${tag}/`,
        prerelease: Boolean(release.prerelease),
        publishedAt: release.published_at || null
      });
    }

    return available
      .filter((release) => compareVersions(release.version, currentVersion) !== 0)
      .sort((a, b) => compareVersions(b.version, a.version));
  } finally {
    clearTimeout(timer);
  }
}

module.exports = {
  OWNER,
  REPO,
  GH_API_RELEASES,
  GH_RELEASES_DOWNLOAD,
  archiveFeedUrl,
  compareVersions,
  fetchAvailableReleases
};
