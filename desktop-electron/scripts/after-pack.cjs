const fs = require('fs');
const path = require('path');

module.exports = async function afterPack(context) {
  const resources = context.electronPlatformName === 'darwin'
    ? path.join(context.appOutDir, `${context.packager.appInfo.productFilename}.app`, 'Contents', 'Resources')
    : path.join(context.appOutDir, 'resources');
  const runtime = path.join(resources, 'prismenv');
  const metadata = path.join(runtime, 'conda-meta');
  if (!fs.existsSync(metadata)) throw new Error('Desktop packaging requires a micromamba conda prismenv');
  const pythonMetadata = fs.readdirSync(metadata).find(name => /^python-\d.*\.json$/.test(name));
  if (!pythonMetadata) throw new Error('Missing conda Python metadata');
  const pythonPackage = JSON.parse(fs.readFileSync(path.join(metadata, pythonMetadata), 'utf8'));
  const platform = { win32: 'win', darwin: 'osx', linux: 'linux' }[context.electronPlatformName];
  const arch = context.arch === 3 ? (platform === 'linux' ? 'aarch64' : 'arm64') : '64';
  if (pythonPackage.subdir !== `${platform}-${arch}`) {
    throw new Error(`Runtime ${pythonPackage.subdir} does not match desktop ${platform}-${arch}`);
  }
  const crawlers = path.join(resources, 'prism_backend', 'douyin_tiktok_api', 'crawlers');
  for (const [target, template] of [
    ['douyin/web', 'douyin/web'], ['tiktok/web', 'tiktok/web'],
    ['tiktok/app', 'tiktok/web'], ['bilibili/web', 'bilibili/web'],
  ]) {
    const destination = path.join(crawlers, target, 'config.yaml');
    fs.mkdirSync(path.dirname(destination), { recursive: true });
    fs.copyFileSync(path.join(crawlers, template, 'config.example.yaml'), destination);
  }
  const manifestPath = path.join(runtime, 'prism-runtime.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  fs.writeFileSync(manifestPath, JSON.stringify({ ...manifest, envDir: '.',
    python: platform === 'win' ? 'python.exe' : 'bin/python' }, null, 2));
};
