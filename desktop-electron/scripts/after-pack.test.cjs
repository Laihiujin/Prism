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
  fs.mkdirSync(path.join(resources, 'scripts/runtime'), { recursive: true });
  fs.writeFileSync(path.join(resources, 'scripts/runtime/ensure-runtime.cjs'), '// installer');
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
  test(`desktop runtime ${subdir} creates empty configs without bundling an environment`, async t => {
    const f = fixture(t, platform, arch, subdir);
    await afterPack(f.context);
    assert.equal(fs.existsSync(f.runtime), false);
    const config = path.join(f.resources, 'prism_backend', 'douyin_tiktok_api', 'crawlers', 'tiktok', 'app', 'config.yaml');
    assert.equal(fs.readFileSync(config, 'utf8'), 'Cookie: ""\n');
  });
}

test('rejects a bundled environment', async t => {
  const f = fixture(t, 'win32', 1, 'osx-arm64');
  fs.mkdirSync(f.runtime);
  await assert.rejects(afterPack(f.context), /Do not bundle/);
});
