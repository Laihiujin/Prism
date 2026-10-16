// One native build pipeline for Windows and macOS. Never publishes implicitly.
const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawnSync } = require('child_process');
const desktop = path.resolve(__dirname, '..');
const root = path.dirname(desktop);
const args = process.argv.slice(2);
const value = flag => args.find(arg => arg.startsWith(`${flag}=`))?.split('=')[1];
const platform = value('--platform') || process.platform;
const arch = value('--arch') || process.arch;
if (platform !== process.platform || arch !== process.arch || !['win32', 'darwin'].includes(platform)) {
  throw new Error('Build each OS/architecture on its matching native runner');
}
function run(command, argv, cwd = root) {
  const result = spawnSync(command, argv, { cwd, stdio: 'inherit', windowsHide: true });
  if (result.error || result.status !== 0) throw result.error || new Error(`${command} failed: ${result.status}`);
}
function npm(argv, cwd) {
  if (!process.env.npm_execpath) throw new Error('Use npm run build to execute this pipeline');
  run(process.execPath, [process.env.npm_execpath, ...argv], cwd);
}
async function main() {
  const frontend = path.join(root, 'prism_frontend');
  if (!fs.existsSync(path.join(frontend, 'node_modules'))) npm(['ci'], frontend);
  process.env.NEXT_PUBLIC_BACKEND_URL = 'http://127.0.0.1:9200';
  process.env.PRISM_BACKEND_URL = 'http://127.0.0.1:9200';
  npm(['run', 'build:desktop'], frontend);
  const resources = path.join(desktop, 'resources');
  if (!fs.existsSync(path.join(resources, 'node_modules'))) npm(['ci'], resources);
  const staging = fs.mkdtempSync(path.join(os.tmpdir(), 'prism-native-build-'));
  try {
    const config = structuredClone(require('../package.json').build);
    if (platform === 'darwin') {
      const icon = path.join(staging, 'icon.png');
      run('sips', ['-s', 'format', 'png', path.join(desktop, 'build', 'icon.ico'), '--out', icon]);
      run('sips', ['-z', '1024', '1024', icon]);
      config.mac.icon = icon;
    }
    const { build, Platform, Arch } = require('electron-builder');
    await build({ projectDir: desktop, targets: Platform.current().createTarget(args.includes('--dir') ? 'dir' : null, Arch[arch]),
      config, publish: 'never' });
  } finally {
    // Only our newly-created temporary build stage, never the source runtime/data.
    fs.rmSync(staging, { recursive: true, force: true });
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
