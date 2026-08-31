// Prism macOS PM2 配置（用 .venv 的 python）
// 启动: PM2_HOME=./runtime-data/pm2 ./prism_frontend/node_modules/.bin/pm2 start ecosystem-mac.config.js
module.exports = {
  apps: [
    {
      name: 'prism-backend',
      cwd: './prism_backend',
      script: '/Users/laihiujin/Documents/siuyechu/Prism/.venv/bin/python',
      args: 'fastapi_app/run.py',
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      env: {
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '/Users/laihiujin/Documents/siuyechu/Prism/prism_backend',
        PLAYWRIGHT_BROWSERS_PATH: '/Users/laihiujin/Documents/siuyechu/Prism/browsers',
        PRISM_BROWSER_BACKEND_DEFAULT: 'persona',
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
    }
  ]
}
