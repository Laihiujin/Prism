// Prism 桌面端 PM2 ecosystem 配置（跨平台 macOS / Windows）。
// 由 Electron 主进程启动的 pm2_controller.js 用它来统一起停/重启/监控全部服务，
// 替代原先的 supervisor.py。路径均相对本文件目录（__dirname）解析，
// 因此在打包的 Resources 目录或源码 desktop-electron/resources 下都能直接运行。
const path = require('path');
const fs = require('fs');
const { spawnSync } = require('child_process');

const CONTROLLER_DIR = __dirname;                 // .../Resources/supervisor
const RESOURCES = path.dirname(CONTROLLER_DIR);   // .../Resources (打包) 或 desktop-electron/resources (dev)
const REPO_ROOT = path.dirname(path.dirname(RESOURCES)); // 源码仓库根（dev 时向前两级）

// 在 dev 下（desktop-electron/resources 存在 repo 内），prismenv/tools 位于仓库根；
// 在打包下（Resources 目录），prismenv/tools 也复制进了 Resources。依次探测。
function resolveIn(root, rel) {
  const candidate = path.join(root, rel);
  return candidate;
}
function firstExisting(candidates) {
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return null;
}

function prismenvPython() {
  const win = process.platform === 'win32';
  const relPython = win ? path.join('prismenv', 'Scripts', 'python.exe') : path.join('prismenv', 'bin', 'python');
  const candidates = [resolveIn(RESOURCES, relPython), resolveIn(REPO_ROOT, relPython)];
  return firstExisting(candidates) || path.join(RESOURCES, relPython);
}

function resolveRel(rel) {
  const candidates = [resolveIn(RESOURCES, rel), resolveIn(REPO_ROOT, rel)];
  return firstExisting(candidates) || resolveIn(RESOURCES, rel);
}

// 记录端口：与 supervisor 默认一致，后端/worker/dashboard/webui 由 Electron 主进程经
// PRISM_*_PORT 传入，可按需被 process.env 覆盖。
const envInt = (names, fallback) => {
  for (const n of names) {
    const v = Number.parseInt(process.env[n] || '', 10);
    if (Number.isInteger(v) && v > 0) return v;
  }
  return fallback;
};

const BACKEND_PORT = envInt(['BACKEND_PORT', 'PRISM_BACKEND_PORT'], 9200);
const WORKER_PORT = envInt(['AUTOMATION_WORKER_PORT', 'PRISM_AUTOMATION_WORKER_PORT'], 7001);
const DASHBOARD_PORT = envInt(['PRISM_HERMES_DASHBOARD_PORT'], 9119);
const WEBUI_PORT = envInt(['PRISM_HERMES_WEBUI_PORT'], 9131);
const HARNESS_PORT = envInt(['PRISM_DEEPSEEK_HARNESS_PORT'], 3080);
const FRONTEND_PORT = envInt(['PRISM_FRONTEND_PORT', 'FRONTEND_PORT', 'PORT'], 3000);

const PY = prismenvPython();
const BACKEND = resolveRel('prism_backend');
const HERMES_AGENT = resolveRel(path.join('tools', 'hermes-agent'));
const HERMES_WEBUI = resolveRel(path.join('tools', 'hermes-webui'));
const DEEPSEEK_HARNESS = resolveRel(path.join('tools', 'deepseek-harness'));
const FRONTEND_STANDALONE = resolveRel(path.join('frontend', 'standalone'));
const FRONTEND_SERVER = path.join(FRONTEND_STANDALONE, 'server.js');

const pythonDir = path.dirname(PY);
const sitePackages = path.join(pythonDir, process.platform === 'win32' ? 'Lib' : 'lib', 'python3.11', 'site-packages');

function which(command, fallback) {
  try {
    const res = spawnSync(process.platform === 'win32' ? 'where' : 'which', [command], { encoding: 'utf8' });
    if (res.status === 0 && res.stdout.trim()) return res.stdout.trim().split(/\r?\n/)[0];
  } catch (_) { /* ignore */ }
  return fallback || command;
}
const REDIS = which('redis-server', process.platform === 'win32' ? 'redis-server' : '/opt/homebrew/bin/redis-server');

// 前端 standalone / DSH CLI 的运行时：用“当前运行 controller 的运行时”来执行。
// 在 Electron 打包下 process.execPath 即 Electron 二进制，设置 ELECTRON_RUN_AS_NODE=1 让其以 node 模式
// 运行 server.js / bin.js；在纯 node 环境则等价于 node。
const frontendExe = process.env.PRISM_FRONTEND_EXEC || process.execPath;

// 服务共享的基础环境：继承 Electron 主进程注入的 PRISM_* / PLAYWRIGHT_* / HERMES_* 等，
// 并补齐 Python 运行时与端口。
const baseEnv = {
  ...process.env,
  PYTHONUTF8: '1',
  PYTHONIOENCODING: 'utf-8',
  PYTHONPATH: [BACKEND, sitePackages].filter(Boolean).join(path.delimiter),
  PRISM_APP_ROOT: RESOURCES,
  PRISM_RESOURCES_PATH: RESOURCES,
  BACKEND_PORT: String(BACKEND_PORT),
  PRISM_BACKEND_PORT: String(BACKEND_PORT),
  AUTOMATION_WORKER_PORT: String(WORKER_PORT),
  PRISM_AUTOMATION_WORKER_PORT: String(WORKER_PORT),
  PRISM_HERMES_DASHBOARD_PORT: String(DASHBOARD_PORT),
  PRISM_HERMES_WEBUI_PORT: String(WEBUI_PORT),
  PRISM_DEEPSEEK_HARNESS_PORT: String(HARNESS_PORT),
  PRISM_FRONTEND_PORT: String(FRONTEND_PORT),
  NEXT_PUBLIC_BACKEND_URL: `http://127.0.0.1:${BACKEND_PORT}`,
  PRISM_BACKEND_URL: `http://127.0.0.1:${BACKEND_PORT}`,
  NEXT_PUBLIC_API_URL: `http://127.0.0.1:${BACKEND_PORT}`,
};

function webuiPyLaunch() {
  // 与 supervisor 的 _build_run_path_launch 等价：runpy 运行 hermes-webui/server.py，
  // 并把 hermes-agent 与 hermes-webui 目录加入 sys.path。
  const code = `import runpy,sys;sys.path.insert(0,${JSON.stringify(HERMES_WEBUI)});sys.path.insert(0,${JSON.stringify(HERMES_AGENT)});runpy.run_path(${JSON.stringify(path.join(HERMES_WEBUI, 'server.py'))},run_name='__main__')`;
  return ['-c', code];
}

function dashboardLaunch() {
  return ['-m', 'hermes_cli.main', 'dashboard', '--host', '127.0.0.1', '--port', String(DASHBOARD_PORT), '--no-open', '--skip-build'];
}

// PM2 app 定义。所有进程都由 PM2 托管（start/stop/restart/restart-count/logs）。
const apps = [
  {
    name: 'prism-redis',
    script: REDIS,
    exec_interpreter: 'none',
    args: '--bind 127.0.0.1 --port 6379 --save "" --appendonly no',
    cwd: RESOURCES,
    autorestart: true,
    restart_delay: 2000,
    max_restarts: 10,
    env: { ...baseEnv, REDIS_HOST: '127.0.0.1', REDIS_PORT: '6379' },
  },
  {
    name: 'prism-backend',
    script: PY,
    args: path.join('fastapi_app', 'run.py'),
    cwd: BACKEND,
    interpreter: PY,
    autorestart: true,
    restart_delay: 2000,
    max_restarts: 10,
    env: { ...baseEnv, PYTHONPATH: [BACKEND, sitePackages].filter(Boolean).join(path.delimiter), PRISM_BACKEND_URL: `http://127.0.0.1:${BACKEND_PORT}` },
  },
  {
    name: 'prism-worker',
    script: PY,
    args: path.join('automation_worker', 'worker.py'),
    cwd: BACKEND,
    interpreter: PY,
    autorestart: true,
    restart_delay: 2000,
    max_restarts: 10,
    env: { ...baseEnv, PYTHONPATH: [BACKEND, sitePackages].filter(Boolean).join(path.delimiter) },
  },
  {
    name: 'prism-celery',
    script: PY,
    args: ['-m', 'celery', '-A', 'fastapi_app.celery_app', 'worker', '-l', 'info', '-P', 'threads', '--concurrency=4'].join(' '),
    cwd: BACKEND,
    interpreter: PY,
    autorestart: true,
    restart_delay: 2000,
    max_restarts: 10,
    env: { ...baseEnv, PYTHONPATH: [BACKEND, sitePackages].filter(Boolean).join(path.delimiter), C_FORCE_ROOT: 'true', REDIS_HOST: '127.0.0.1', REDIS_PORT: '6379' },
  },
  {
    name: 'hermes-dashboard',
    script: PY,
    args: dashboardLaunch().join(' '),
    cwd: HERMES_AGENT,
    interpreter: PY,
    autorestart: true,
    restart_delay: 3000,
    max_restarts: 5,
    env: {
      ...baseEnv,
      PYTHONPATH: [HERMES_AGENT, sitePackages].filter(Boolean).join(path.delimiter),
      HERMES_WEB_DIST: path.join(HERMES_AGENT, 'hermes_cli', 'web_dist'),
      HERMES_WEBUI_AGENT_DIR: HERMES_AGENT,
    },
  },
  {
    name: 'hermes-webui',
    script: PY,
    args: webuiPyLaunch().join(' '),
    cwd: HERMES_WEBUI,
    interpreter: PY,
    autorestart: true,
    restart_delay: 3000,
    max_restarts: 5,
    env: {
      ...baseEnv,
      PYTHONPATH: [HERMES_AGENT, sitePackages].filter(Boolean).join(path.delimiter),
      HERMES_WEBUI_AGENT_DIR: HERMES_AGENT,
      HERMES_WEBUI_PYTHON: PY,
      HERMES_WEBUI_HOST: '127.0.0.1',
      HERMES_WEBUI_PORT: String(WEBUI_PORT),
      HERMES_WEBUI_STATE_DIR: process.env.PRISM_HERMES_WEBUI_STATE_DIR || path.join(RESOURCES, '..', 'hermes', 'webui'),
      HERMES_WEBUI_DEFAULT_WORKSPACE: process.env.PRISM_HERMES_WORKSPACE || path.join(RESOURCES, '..', 'hermes', 'workspace'),
      HERMES_SKIP_CHMOD: '1',
    },
  },
  {
    name: 'deepseek-harness',
    script: frontendExe,
    args: path.join(DEEPSEEK_HARNESS, 'apps', 'cli', 'lib', 'bin.js'),
    exec_interpreter: 'none',
    cwd: DEEPSEEK_HARNESS,
    autorestart: true,
    restart_delay: 3000,
    max_restarts: 5,
    env: { ...baseEnv, DSH_HOST: '127.0.0.1', DSH_PORT: String(HARNESS_PORT), PRISM_DEEPSEEK_HARNESS_ROOT: DEEPSEEK_HARNESS, ELECTRON_RUN_AS_NODE: '1' },
  },
  {
    name: 'prism-frontend',
    script: frontendExe,
    args: [FRONTEND_SERVER],
    exec_interpreter: 'none',
    cwd: FRONTEND_STANDALONE,
    autorestart: true,
    restart_delay: 2000,
    max_restarts: 10,
    env: {
      ...baseEnv,
      NODE_ENV: 'production',
      PORT: String(FRONTEND_PORT),
      HOSTNAME: '127.0.0.1',
      NEXT_TELEMETRY_DISABLED: '1',
      ELECTRON_RUN_AS_NODE: '1',
    },
  },
];

module.exports = {
  apps,
  // 供 pm2_controller 使用的服务元数据：supervisor 服务名 -> PM2 进程名
  _prism: {
    resourceRoot: RESOURCES,
    servicePorts: {
      backend: BACKEND_PORT,
      'automation-worker': WORKER_PORT,
      'hermes-dashboard': DASHBOARD_PORT,
      'hermes-webui': WEBUI_PORT,
      'deepseek-harness': HARNESS_PORT,
      'prism-frontend': FRONTEND_PORT,
    },
    // supervisor 的 /api/status 用的 service key（连字符转下划线）
    serviceKeys: ['backend', 'automation-worker', 'celery-worker', 'hermes-gateway', 'hermes-dashboard', 'hermes-webui'],
  },
};
