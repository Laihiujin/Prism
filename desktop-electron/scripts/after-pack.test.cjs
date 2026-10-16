const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const afterPack = require('./after-pack.cjs');

function fixture(t, platform, arch, subdir) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'prism-pack-test-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const resources = platform === 'darwin' ? path.join(root, 'Prism.app', 'Contents', 'Resources') : path.join(root, 'resources');
  const runtime = path.join(resources, 'prismenv');
  fs.mkdirSync(path.join(runtime, 'conda-meta'), { recursive: true });
  fs.writeFileSync(path.join(runtime, 'conda-meta', 'python-3.11-test.json'), JSON.stringify({ subdir }));
  fs.writeFileSync(path.join(runtime, 'prism-runtime.json'), JSON.stringify({ manager: 'micromamba', python: '/build-machine/python', envDir: '/build-machine' }));
  for (const target of ['douyin/web', 'tiktok/web', 'bilibili/web']) {
    const folder = path.join(resources, 'prism_backend', 'douyin_tiktok_api', 'crawlers', target);
    fs.mkdirSync(folder, { recursive: true });
    fs.writeFileSync(path.join(folder, 'config.example.yaml'), 'Cookie: ""\n');
  }
  return { resources, runtime, context: { appOutDir: root, electronPlatformName: platform, arch,
    packager: { appInfo: { productFilename: 'Prism' } } } };
}

for (const [platform, arch, subdir, python] of [
  ['win32', 1, 'win-64', 'python.exe'], ['darwin', 3, 'osx-arm64', 'bin/python'],
  ['darwin', 1, 'osx-64', 'bin/python'], ['linux', 1, 'linux-64', 'bin/python'],
]) {
  test(`desktop runtime ${subdir} uses portable paths and empty configs`, async t => {
    const f = fixture(t, platform, arch, subdir);
    await afterPack(f.context);
    const manifest = JSON.parse(fs.readFileSync(path.join(f.runtime, 'prism-runtime.json'), 'utf8'));
    assert.equal(manifest.python, python);
    assert.equal(manifest.envDir, '.');
    const config = path.join(f.resources, 'prism_backend', 'douyin_tiktok_api', 'crawlers', 'tiktok', 'app', 'config.yaml');
    assert.equal(fs.readFileSync(config, 'utf8'), 'Cookie: ""\n');
  });
}

test('rejects a runtime built for a different system', async t => {
  const f = fixture(t, 'win32', 1, 'osx-arm64');
  await assert.rejects(afterPack(f.context), /does not match desktop/);
});
