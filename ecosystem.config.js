// Prism PM2 配置（跨平台：macOS / Windows / Linux，统一使用 prismenv，路径按项目目录相对解析）
// 启动: PM2_HOME=./runtime-data/pm2 ./node_modules/.bin/pm2 start ecosystem.config.js
//
// 说明：
// - 所有 Python 解释器统一取 <repo>/prismenv/bin/python（macOS/Linux）
//   或 <repo>/prismenv/Scripts/python.exe（Windows），不再用 .venv。
// - npm 在 Windows 下解析为 npm.cmd，console-script 在 Windows 下解析为 Scripts/*.exe。
// - 所有绝对路径都相对本文件目录（__dirname）计算，因此整个仓库移到任意路径都能直接跑，
//   不再依赖某台机器上的 /Users/<user>/... 硬编码路径。
const path = require('path');
const fs = require('fs');
const { spawnSync } = require('child_process');

const ROOT = __dirname;                       // 本文件所在目录 = 项目根
const PRISMENV = path.join(ROOT, 'prismenv');
const IS_WIN = process.platform === 'win32';
const PY = IS_WIN
  ? path.join(PRISMENV, 'Scripts', 'python.exe')
  : path.join(PRISMENV, 'bin', 'python');
const NPM = IS_WIN ? 'npm.cmd' : 'npm';
const COMPONENT_ENV_ROOT = path.join(ROOT, 'prism_components');
const BACKEND = path.join(ROOT, 'prism_backend');
const RUNTIME_DATA = process.env.PRISM_RUNTIME_DATA_DIR || path.join(ROOT, 'runtime-data');
const BROWSERS = path.join(RUNTIME_DATA, 'components', 'browsers', 'patchright', 'versions', 'current');
const HERMES_AGENT = path.join(ROOT, 'tools', 'hermes-agent');
const HERMES_WEBUI = path.join(ROOT, 'tools', 'hermes-webui');
const HERMES_HOME = path.join(ROOT, 'tools', 'hermes-home', 'webui');
const PERSONA_PROXY = path.join(ROOT, 'tools', 'persona-studio', 'proxies', 'mihomo');
const DEEPSEEK_HARNESS = path.join(ROOT, 'tools', 'deepseek-harness');
const DSH_CLI = path.join(DEEPSEEK_HARNESS, 'apps', 'cli', 'lib', 'bin.js');
const runtime = JSON.parse(fs.readFileSync(path.join(ROOT, 'runtime-data', 'runtime.json'), 'utf8'));
const backendEnv = {
  PRISM_BACKEND_HOST: String(runtime.backend_host),
  PRISM_BACKEND_PORT: String(runtime.backend_port),
  PRISM_BACKEND_URL: runtime.backend_url,
  NEXT_PUBLIC_BACKEND_URL: runtime.backend_url,
};

// redis-server 从 PATH 解析，便于换机器/换安装位置也能用
function which(command, fallback) {
  try {
    const res = spawnSync('which', [command], { encoding: 'utf8' });
    if (res.status === 0 && res.stdout.trim()) return res.stdout.trim();
  } catch (_) { /* ignore */ }
  return fallback || command;
}
const REDIS = which('redis-server', IS_WIN ? 'redis-server' : '/opt/homebrew/bin/redis-server');

function pyCliIn(envDir, name) {
  // 优先 <envDir>/bin/<console-script>（macOS，带 shebang，PM2 可直接跑）
  // 或 <envDir>/Scripts/<name>.exe（Windows）；不存在则退回 解释器 -m <name>。
  const binDir = IS_WIN ? 'Scripts' : 'bin';
  const exeName = IS_WIN ? (name + '.exe') : name;
  const exe = path.join(envDir, binDir, exeName);
  if (fs.existsSync(exe)) return { script: exe, preArgs: [] };
  return { script: PY, preArgs: ['-m', name] };
}
function pyCli(name) { return pyCliIn(PRISMENV, name); }
function pyCliArgs(name, extraArgs) {
  const c = pyCli(name);
  return { script: c.script, args: c.preArgs.concat(extraArgs).join(' ') };
}
// 隔离组件：每个组件有自己的 prism_components/<component> 环境，入口在其 bin/ 下。
function compPyCliArgs(component, name, extraArgs) {
  const c = pyCliIn(path.join(COMPONENT_ENV_ROOT, component), name);
  return { script: c.script, args: c.preArgs.concat(extraArgs).join(' ') };
}

module.exports = {
  apps: [
    {
      name: 'prism-redis',
      cwd: '.',
      script: REDIS,
      interpreter: 'none',
      args: '--bind 127.0.0.1 --port 6379 --save "" --appendonly no',
      autorestart: true,
      watch: false,
      restart_delay: 2000,
      error_file: './logs/redis-error.log',
      out_file: './logs/redis-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'prism-backend',
      cwd: './prism_backend',
      script: PY,
      args: 'fastapi_app/run.py',
      autorestart: true,
      // 后端会持续写入日志、数据库和运行时状态；交给 PM2 守护即可，不监听运行时文件。
      watch: false,
      ignore_watch: [
        'db', 'logs', 'data', 'storage', 'uploads', 'videoFile',
        'cookies', 'cookiesFile', 'browser_profiles', 'fingerprints',
        '**/__pycache__', '**/*.pyc', '.git',
      ],
      max_memory_restart: '2G',
      env: {
        ...backendEnv,
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: BACKEND,
        PLAYWRIGHT_BROWSERS_PATH: BROWSERS,
        PRISM_BROWSER_BACKEND_DEFAULT: process.env.PRISM_BROWSER_BACKEND_DEFAULT || 'patchright',
        PRISM_HERMES_DASHBOARD_PORT: '9119',
        PRISM_HERMES_WEBUI_PORT: '9131',
      },
      error_file: './logs/backend-error.log',
      out_file: './logs/backend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'prism-worker',
      cwd: './prism_backend',
      script: PY,
      args: 'automation_worker/worker.py',
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      env: {
        ...backendEnv,
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: BACKEND,
        PLAYWRIGHT_BROWSERS_PATH: BROWSERS,
      },
      error_file: './logs/worker-error.log',
      out_file: './logs/worker-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'prism-celery',
      cwd: './prism_backend',
      script: PY,
      args: '-m celery -A fastapi_app.tasks.celery_app worker -l info -P threads --concurrency=8',
      autorestart: true,
      watch: false,
      env: {
        ...backendEnv,
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: BACKEND,
      },
      error_file: './logs/celery-error.log',
      out_file: './logs/celery-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'prism-frontend',
      cwd: './prism_frontend',
      script: NPM,
      args: 'run dev',
      autorestart: true,
      watch: false,
      env: {
        PORT: '3000',
        ...backendEnv,
      },
      error_file: './logs/frontend-error.log',
      out_file: './logs/frontend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'persona-api',
      cwd: '.',
      script: compPyCliArgs('persona', 'persona', ['--data-dir', 'tools/persona-studio/data', 'serve']).script,
      interpreter: 'none', // 按 shebang 直接运行 Python CLI
      args: compPyCliArgs('persona', 'persona', ['--data-dir', 'tools/persona-studio/data', 'serve']).args,
      autorestart: true,
      watch: false,
      env: { PLAYWRIGHT_BROWSERS_PATH: BROWSERS },
      error_file: './logs/persona-error.log',
      out_file: './logs/persona-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      // Persona per-country 代理网关：独立官方 mihomo，提供 7771-7776
      // 绑定各国家节点(见 tools/persona-studio/proxies/config.yaml)
      name: 'persona-proxy',
      cwd: '.',
      script: PERSONA_PROXY,
      interpreter: 'none', // 原生二进制
      args: '-d tools/persona-studio/proxies -f tools/persona-studio/proxies/config.yaml',
      autorestart: true,
      watch: false,
      error_file: './logs/persona-proxy-error.log',
      out_file: './logs/persona-proxy-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'persona-dashboard',
      cwd: './tools/persona-studio/dashboard',
      script: NPM,
      // server.open=true 会让 Vite 自动弹浏览器到 5173；用 --no-open 覆盖，
      // 避免启动时浏览器抢走焦点（应停留/打开到主前端 http://localhost:3000）。
      args: 'run dev -- --host 127.0.0.1 --port 5173 --no-open',
      autorestart: true,
      watch: false,
      restart_delay: 2000,
      error_file: './logs/persona-dashboard-error.log',
      out_file: './logs/persona-dashboard-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'hermes-dashboard',
      cwd: '.',
      script: compPyCliArgs('hermes', 'hermes', ['dashboard', '--host', '127.0.0.1', '--port', '9119', '--no-open', '--skip-build']).script,
      interpreter: 'none',
      args: compPyCliArgs('hermes', 'hermes', ['dashboard', '--host', '127.0.0.1', '--port', '9119', '--no-open', '--skip-build']).args,
      autorestart: true,
      watch: false,
      restart_delay: 2000,
      max_restarts: 20,
      env: {
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: HERMES_AGENT,
      },
      error_file: './logs/hermes-dashboard-error.log',
      out_file: './logs/hermes-dashboard-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'hermes-webui',
      cwd: './tools/hermes-webui',
      script: PY,
      interpreter: 'none',
      args: 'server.py',
      autorestart: true,
      watch: false,
      restart_delay: 2000,
      env: {
        PYTHONUNBUFFERED: '1',
        HERMES_WEBUI_HOST: '127.0.0.1',
        HERMES_WEBUI_PORT: '9131',
        HERMES_WEBUI_AGENT_DIR: HERMES_AGENT,
        HERMES_WEBUI_STATE_DIR: HERMES_HOME,
      },
      error_file: './logs/hermes-webui-error.log',
      out_file: './logs/hermes-webui-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      // DeepSeek Harness：CLI 启动器会挂载 API 与 3080 Web UI，三者共享同一进程/配置。
      name: 'deepseek-harness',
      cwd: DEEPSEEK_HARNESS,
      script: DSH_CLI,
      interpreter: process.execPath,
      args: 'web --host 127.0.0.1 --port 3080 --no-open',
      autorestart: true,
      watch: false,
      restart_delay: 3000,
      max_restarts: 5,
      env: {
        NODE_ENV: process.env.NODE_ENV || 'production',
        DSH_HOST: '127.0.0.1',
        DSH_PORT: '3080',
        PRISM_DEEPSEEK_HARNESS_ROOT: DEEPSEEK_HARNESS,
      },
      error_file: './logs/deepseek-harness-error.log',
      out_file: './logs/deepseek-harness-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
};
