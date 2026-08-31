# Prism Docker 部署指南

完整项目容器化，一键启动全栈：**FastAPI + Celery + Automation Worker + Next.js + Redis**。
不依赖本机 Python/Node 环境，数据通过卷持久化，账号登录态不丢失。

## 架构

```
┌─────────── docker compose ───────────┐
│  prism-frontend (:3000)  Next.js     │
│        │ NEXT_PUBLIC_BACKEND_URL     │
│  prism-app (:7000)  FastAPI          │
│    ├── Celery worker (同容器)        │
│    └── Automation Worker (:7001 内部)│
│        │ REDIS_URL                   │
│  prism-redis (:6379)  Redis          │
└──────────────────────────────────────┘
```

- `prism-app` 单容器内由 `docker/start-app.sh` 同时托管：
  Celery worker + automation_worker(7001) + FastAPI(7000)，supervisor 式 shutdown。
- `prism-frontend` Next.js standalone 产物，三阶段构建。
- 数据挂载 `./runtime-data/app:/app/runtime-data`。

## 快速开始

```bash
# 1. 准备 .env（compose env_file）
cp .env.example .env   # 或按需编辑

# 2. 构建并启动
docker compose up -d --build

# 3. 验证
docker compose ps                  # 三个服务均 healthy
curl http://127.0.0.1:7000/health # {"status":"healthy",...}
open http://127.0.0.1:3000        # 前端

# 4. 日志
docker compose logs -f app frontend
```

## 数据持久化

| 本地目录 | 容器内 | 内容 |
|---|---|---|
| `./runtime-data/app/db` | `/app/runtime-data/db` | SQLite（cookie_store.db / database.db / ai_logs.db） |
| `./runtime-data/app/cookiesFile` | `/app/runtime-data/cookiesFile` | 账号 Cookie |
| `./runtime-data/app/videoFile` | `/app/runtime-data/videoFile` | 视频素材 |
| `./runtime-data/app/uploads` | `/app/runtime-data/uploads` | 上传文件 |
| `./runtime-data/app/browser_profiles` | `/app/runtime-data/browser_profiles` | Patchright/Persona Profile |
| `./runtime-data/app/logs` | `/app/runtime-data/logs` | 日志 |

> 首次迁移：把现有 `prism_backend/db`、`prism_backend/cookiesFile` 等复制到
> `runtime-data/app/` 对应目录即可保留账号登录态。

## 兼容说明（容器特有）

- **BASE_DIR 数据软链**：业务代码多处硬编码 `Path(settings.BASE_DIR)/"db"`，
  `docker/start-app.sh` 启动时把 `/app/prism_backend/{db,cookiesFile,...}` 软链到
  `PRISM_DATA_DIR`，容器/本地行为一致，无需改业务代码。
- **frontend lockfile**：macOS 生成的 package-lock 含 darwin 专属可选依赖（fsevents），
  Dockerfile 用 `npm ci --force` 跳过平台校验。
- **镜像源**：若 Docker Hub 拉取失败（网络受限），配置 registry mirror：
  ```json
  // ~/.docker/daemon.json
  { "registry-mirrors": ["https://docker.1ms.run"] }
  ```

## 关键配置

| 变量 | 默认 | 说明 |
|---|---|---|
| `REDIS_URL` | `redis://redis:6379/0` | 锁 + 缓存 |
| `CELERY_BROKER_URL` | `redis://redis:6379/1` | Celery broker |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/2` | Celery results |
| `PRISM_RUNTIME_LOCK_ENABLED` | `true` | Account Runtime 分布式锁 |
| `PERSONA_ENABLED` | `false` | Persona Studio（默认关闭，回退 Patchright） |
| `PRISM_BROWSER_BACKEND_DEFAULT` | `patchright` | 默认浏览器后端 |
| `CELERY_CONCURRENCY` | `8` | Celery 并发 |

## 常用运维

```bash
docker compose down          # 停止（保留数据卷）
docker compose down -v       # 停止并删除卷（数据会丢！）
docker compose up -d --build # 重新构建
docker compose restart app   # 重启后端
docker exec -it prism-app-1 sh  # 进容器调试
```
