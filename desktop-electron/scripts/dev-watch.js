const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const watchRoots = [path.join(root, 'src', 'main'), path.join(root, 'src', 'preload'), path.join(root, 'src', 'renderer')];
let child;
let restartTimer;

function start() {
  child = spawn(process.execPath, ['.'], {
    cwd: root,
    stdio: 'inherit',
    env: { ...process.env, PRISM_START_SERVICES: '1', PRISM_START_FRONTEND: '1' },
  });
  child.on('exit', (code, signal) => {
    if (!restartTimer && !signal) process.exit(code ?? 0);
  });
}

function restart() {
  clearTimeout(restartTimer);
  restartTimer = setTimeout(() => {
    if (child && !child.killed) child.kill();
    setTimeout(start, 250);
  }, 150);
}

for (const dir of watchRoots) {
  fs.watch(dir, { recursive: true }, (_event, filename) => {
    if (filename && !String(filename).includes('node_modules')) restart();
  });
}

process.on('SIGINT', () => { if (child) child.kill(); process.exit(0); });
start();
