// PM2 进程管理配置文件
// 使用方法：pm2 start ecosystem.config.js
const backendPort = process.env.PRISM_BACKEND_PORT || '7000';
const backendHost = process.env.PRISM_BACKEND_HOST || '127.0.0.1';
const backendUrl = process.env.PRISM_BACKEND_URL || `http://${backendHost}:${backendPort}`;
const backendEnv = {
  PRISM_BACKEND_HOST: backendHost,
  PRISM_BACKEND_PORT: backendPort,
  PRISM_BACKEND_URL: backendUrl,
  NEXT_PUBLIC_BACKEND_URL: backendUrl,
};

module.exports = {
  apps: [
    // 前端服务（Next.js）
    {
      name: 'prism-frontend',
      cwd: './prism_frontend',
      script: 'npm',
      args: 'start',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        ...backendEnv,
        NODE_ENV: 'production',
        PORT: 3000
      },
      error_file: './logs/frontend-error.log',
      out_file: './logs/frontend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },

    // 后端API服务（FastAPI + Uvicorn）
    {
      name: 'prism-backend',
      cwd: './prism_backend',
      script: 'fastapi_app/run.py',
      args: '',
      interpreter: 'python',  // 修改为你的Python路径，如 '/opt/conda/envs/prism/bin/python'
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      env: {
        ...backendEnv,
        PYTHONUNBUFFERED: '1',
        REDIS_HOST: 'localhost',
        REDIS_PORT: '6379'
      },
      error_file: './logs/backend-error.log',
      out_file: './logs/backend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },

    // Celery Worker（异步任务处理）
    {
      name: 'prism-celery',
      cwd: './prism_backend',
      script: 'celery',
      args: '-A fastapi_app.celery_app worker -l info -P threads --concurrency=4',
      interpreter: 'python',  // 修改为你的Python路径
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      env: {
        ...backendEnv,
        PYTHONUNBUFFERED: '1',
        C_FORCE_ROOT: 'true',  // 允许root用户运行（生产环境建议使用专用用户）
        REDIS_HOST: 'localhost',
        REDIS_PORT: '6379'
      },
      error_file: './logs/celery-error.log',
      out_file: './logs/celery-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ],

  // 部署配置（可选）
  deploy: {
    production: {
      user: 'deploy',
      host: 'your-server.com',
      ref: 'origin/master',
      repo: 'git@github.com:your-username/Prism.git',
      path: '/opt/Prism',
      'post-deploy': 'npm install && pm2 reload ecosystem.config.js --env production'
    }
  }
}
