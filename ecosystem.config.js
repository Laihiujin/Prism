// PM2 进程管理配置文件
// 使用方法：pm2 start ecosystem.config.js

module.exports = {
  apps: [
    // 前端服务（Next.js）
    {
      name: 'synapse-frontend',
      cwd: './syn_frontend_react',
      script: 'npm',
      args: 'start',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production',
        PORT: 3000
      },
      error_file: './logs/frontend-error.log',
      out_file: './logs/frontend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },

    // 后端API服务（FastAPI + Uvicorn）
    {
      name: 'synapse-backend',
      cwd: './syn_backend',
      script: 'uvicorn',
      args: 'fastapi_app.main:app --host 0.0.0.0 --port 7000 --workers 4',
      interpreter: 'python',  // 修改为你的Python路径，如 '/opt/conda/envs/syn/bin/python'
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      env: {
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
      name: 'synapse-celery',
      cwd: './syn_backend',
      script: 'celery',
      args: '-A fastapi_app.celery_app worker -l info -P threads --concurrency=4',
      interpreter: 'python',  // 修改为你的Python路径
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      env: {
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
      repo: 'git@github.com:your-username/SynapseAutomation.git',
      path: '/opt/SynapseAutomation',
      'post-deploy': 'npm install && pm2 reload ecosystem.config.js --env production'
    }
  }
}
