// Prism macOS PM2 配置（统一使用 prismenv，路径按项目目录相对解析）
// 启动: PM2_HOME=./runtime-data/pm2 ./prism_frontend/node_modules/.bin/pm2 start ecosystem-mac.config.js
//
// 说明：
// - 所有 Python 解释器统一取 <repo>/prismenv/bin/python（不再用 .venv）。
// - 所有绝对路径都相对本文件目录（__dirname）计算，因此整个仓库移到任意路径都能直接跑，
//   不再依赖某台机器上的 /Users/<user>/... 硬编码路径。
const path = require('path');
const fs = require('fs');
const { spawnSync } = require('child_process');

const ROOT = __dirname;                       // 本文件所在目录 = 项目根
const PRISMENV = path.join(ROOT, 'prismenv');
const PY = path.join(PRISMENV, 'bin', 'python');
const BACKEND = path.join(ROOT, 'prism_backend');
const BROWSERS = path.join(ROOT, 'browsers');
const HERMES_AGENT = path.join(ROOT, 'tools', 'hermes-agent');
const HERMES_WEBUI = path.join(ROOT, 'tools', 'hermes-webui');
const HERMES_HOME = path.join(ROOT, 'tools', 'hermes-home', 'webui');
const PERSONA_PROXY = path.join(ROOT, 'tools', 'persona-studio', 'proxies', 'mihomo');
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
const REDIS = which('redis-server', '/opt/homebrew/bin/redis-server');

function pyCli(name) {
  // 优先 prismenv/bin/<console-script>（带 shebang，PM2 可直接跑）；
  // 不存在则退回 prismenv/bin/python -m <name>。
  const exe = path.join(PRISMENV, 'bin', name);
  if (fs.existsSync(exe)) return { script: exe, preArgs: [] };
  return { script: PY, preArgs: ['-m', name] };
}
function pyCliArgs(name, extraArgs) {
  const c = pyCli(name);
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
        PRISM_HERMES_WEBUI_PORT: '8788',
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
      script: 'npm',
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
      script: pyCliArgs('persona', ['--data-dir', 'tools/persona-studio/data', 'serve']).script,
      interpreter: 'none', // 按 shebang 直接运行 Python CLI
      args: pyCliArgs('persona', ['--data-dir', 'tools/persona-studio/data', 'serve']).args,
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
      script: 'npm',
      args: 'run dev -- --host 127.0.0.1 --port 5173',
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
      script: pyCliArgs('hermes', ['dashboard', '--host', '127.0.0.1', '--port', '9119', '--no-open', '--skip-build']).script,
      interpreter: 'none',
      args: pyCliArgs('hermes', ['dashboard', '--host', '127.0.0.1', '--port', '9119', '--no-open', '--skip-build']).args,
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
        HERMES_WEBUI_PORT: '8788',
        HERMES_WEBUI_AGENT_DIR: HERMES_AGENT,
        HERMES_WEBUI_STATE_DIR: HERMES_HOME,
      },
      error_file: './logs/hermes-webui-error.log',
      out_file: './logs/hermes-webui-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
};
