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
const runtimePython = path.join(root, 'prismenv', platform === 'win32' ? 'python.exe' : 'bin/python');
const python = fs.existsSync(runtimePython) ? runtimePython : (process.env.PRISM_BUILD_PYTHON || (platform === 'win32' ? 'python' : 'python3'));
function run(command, argv, cwd = root) {
  const result = spawnSync(command, argv, { cwd, stdio: 'inherit', windowsHide: true });
  if (result.error || result.status !== 0) throw result.error || new Error(`${command} failed: ${result.status}`);
}
function npm(argv, cwd) {
  if (!process.env.npm_execpath) throw new Error('Use npm run build to execute this pipeline');
  run(process.execPath, [process.env.npm_execpath, ...argv], cwd);
}
async function main() {
  run(python, ['scripts/packaging/provision/provision.py', '--skip-inject']);
  const frontend = path.join(root, 'prism_frontend');
  if (!fs.existsSync(path.join(frontend, 'node_modules'))) npm(['ci'], frontend);
  process.env.NEXT_PUBLIC_BACKEND_URL = 'http://127.0.0.1:9200';
  process.env.PRISM_BACKEND_URL = 'http://127.0.0.1:9200';
  npm(['run', 'build:desktop'], frontend);
  const resources = path.join(desktop, 'resources');
  if (!fs.existsSync(path.join(resources, 'node_modules'))) npm(['ci'], resources);
  const staging = fs.mkdtempSync(path.join(os.tmpdir(), 'prism-native-build-'));
  try {
    const runtime = path.join(staging, 'prismenv');
    run(runtimePython, ['scripts/packaging/prepare_runtime.py', runtime]);
    const config = structuredClone(require('../package.json').build);
    config.extraResources.find(resource => resource.to === 'prismenv').from = runtime;
    if (platform === 'darwin') {
      const icon = path.join(staging, 'icon.png');
      run(runtimePython, ['-c',
        'from PIL import Image; import sys; Image.open(sys.argv[1]).convert("RGBA").resize((1024,1024)).save(sys.argv[2])',
        path.join(desktop, 'build', 'icon.ico'), icon]);
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
