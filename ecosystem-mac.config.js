// Prism macOS PM2 配置（用 .venv 的 python）
// 启动: PM2_HOME=./runtime-data/pm2 ./prism_frontend/node_modules/.bin/pm2 start ecosystem-mac.config.js
module.exports = {
  apps: [
    {
      name: 'prism-redis',
      cwd: '.',
      script: '/opt/homebrew/bin/redis-server',
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
      script: '/Users/laihiujin/Documents/siuyechu/Prism/.venv/bin/python',
      args: 'fastapi_app/run.py',
      autorestart: true,
      // 热重载：监视代码目录，改动后自动重启（uvicorn 本身只 reload fastapi_app，
      // 这里覆盖 myUtils/utils/scripts 等全部后端代码）
      // 后端会持续写入日志、数据库和运行时状态；开启 watch 会触发自重启，
      // 造成前端短暂断开。交给 PM2 守护即可，不监听运行时文件。
      watch: false,
      ignore_watch: [
        'db', 'logs', 'data', 'storage', 'uploads', 'videoFile',
        'cookies', 'cookiesFile', 'browser_profiles', 'fingerprints',
        '**/__pycache__', '**/*.pyc', '.git',
      ],
      max_memory_restart: '2G',
      env: {
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '/Users/laihiujin/Documents/siuyechu/Prism/prism_backend',
        PLAYWRIGHT_BROWSERS_PATH: '/Users/laihiujin/Documents/siuyechu/Prism/browsers',
        PRISM_BROWSER_BACKEND_DEFAULT: 'persona',
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
      script: '/Users/laihiujin/Documents/siuyechu/Prism/.venv/bin/python',
      args: 'automation_worker/worker.py',
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      env: {
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '/Users/laihiujin/Documents/siuyechu/Prism/prism_backend',
        PLAYWRIGHT_BROWSERS_PATH: '/Users/laihiujin/Documents/siuyechu/Prism/browsers',
      },
      error_file: './logs/worker-error.log',
      out_file: './logs/worker-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'prism-celery',
      cwd: './prism_backend',
      script: '/Users/laihiujin/Documents/siuyechu/Prism/.venv/bin/python',
      args: '-m celery -A fastapi_app.tasks.celery_app worker -l info -P threads --concurrency=8',
      autorestart: true,
      watch: false,
      env: {
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '/Users/laihiujin/Documents/siuyechu/Prism/prism_backend',
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
        NEXT_PUBLIC_BACKEND_URL: 'http://127.0.0.1:7000',
      },
      error_file: './logs/frontend-error.log',
      out_file: './logs/frontend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'persona-api',
      cwd: '.',
      script: '/Users/laihiujin/Documents/siuyechu/Prism/.venv/bin/persona',
      interpreter: 'none', // 按 shebang 直接运行 Python CLI
      args: '--data-dir tools/persona-studio/data serve',
      autorestart: true,
      watch: false,
      env: { PLAYWRIGHT_BROWSERS_PATH: '/Users/laihiujin/Documents/siuyechu/Prism/browsers' },
      error_file: './logs/persona-error.log',
      out_file: './logs/persona-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      // Persona per-country 代理网关：独立官方 mihomo，提供 7771-7776
      // 绑定各国家节点(见 tools/persona-studio/proxies/config.yaml)
      name: 'persona-proxy',
      cwd: '.',
      script: '/Users/laihiujin/Documents/siuyechu/Prism/tools/persona-studio/proxies/mihomo',
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
      script: '/Users/laihiujin/Documents/siuyechu/Prism/prismenv/bin/hermes',
      interpreter: 'none',
      args: 'dashboard --host 127.0.0.1 --port 9119 --no-open --skip-build',
      autorestart: true,
      watch: false,
      restart_delay: 2000,
      max_restarts: 20,
      env: {
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '/Users/laihiujin/Documents/siuyechu/Prism/tools/hermes-agent',
      },
      error_file: './logs/hermes-dashboard-error.log',
      out_file: './logs/hermes-dashboard-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'hermes-webui',
      cwd: './tools/hermes-webui',
      script: '/Users/laihiujin/Documents/siuyechu/Prism/prismenv/bin/python',
      interpreter: 'none',
      args: 'server.py',
      autorestart: true,
      watch: false,
      restart_delay: 2000,
      env: {
        PYTHONUNBUFFERED: '1',
        HERMES_WEBUI_HOST: '127.0.0.1',
        HERMES_WEBUI_PORT: '8788',
        HERMES_WEBUI_AGENT_DIR: '/Users/laihiujin/Documents/siuyechu/Prism/tools/hermes-agent',
        HERMES_WEBUI_STATE_DIR: '/Users/laihiujin/Documents/siuyechu/Prism/tools/hermes-home/webui',
      },
      error_file: './logs/hermes-webui-error.log',
      out_file: './logs/hermes-webui-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
}
