const fs = require('fs');
const path = require('path');

module.exports = async function afterPack(context) {
  const resources = context.electronPlatformName === 'darwin'
    ? path.join(context.appOutDir, `${context.packager.appInfo.productFilename}.app`, 'Contents', 'Resources')
    : path.join(context.appOutDir, 'resources');
  const runtime = path.join(resources, 'prismenv');
  if (fs.existsSync(runtime)) throw new Error('Do not bundle a Python environment; provision on first launch');
  if (!fs.existsSync(path.join(resources, 'scripts/runtime/ensure-runtime.cjs'))) throw new Error('Missing first-run runtime installer');
  const crawlers = path.join(resources, 'prism_backend', 'douyin_tiktok_api', 'crawlers');
  for (const [target, template] of [
    ['douyin/web', 'douyin/web'], ['tiktok/web', 'tiktok/web'],
    ['tiktok/app', 'tiktok/web'], ['bilibili/web', 'bilibili/web'],
  ]) {
    const destination = path.join(crawlers, target, 'config.yaml');
    fs.mkdirSync(path.dirname(destination), { recursive: true });
    fs.copyFileSync(path.join(crawlers, template, 'config.example.yaml'), destination);
  }
};
