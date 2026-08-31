#!/usr/bin/env bash
# Prism macOS 一键启动脚本（等效 Windows 的 start.bat）
# 用法: ./start-mac.sh
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
LOGS="$ROOT/logs"
mkdir -p "$LOGS"

export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
export PYTHONPATH="$ROOT/prism_backend"
export PLAYWRIGHT_BROWSERS_PATH="$ROOT/browsers"
export NEXT_PUBLIC_BACKEND_URL="http://127.0.0.1:7000"

echo "============================================"
echo "  Prism 启动 (macOS)"
echo "============================================"

# 1) Redis
if command -v redis-cli >/dev/null 2>&1 && redis-cli ping >/dev/null 2>&1; then
  echo "[1/5] Redis 已在运行"
else
  echo "[1/5] 启动 Redis ..."
  (redis-server --daemonize yes >/dev/null 2>&1 || echo "  [warn] 请手动启动: redis-server") || true
  sleep 1
fi

# 2) FastAPI 后端 (7000)
echo "[2/5] 启动 FastAPI 后端 (http://127.0.0.1:7000) ..."
nohup "$PY" prism_backend/fastapi_app/run.py > "$LOGS/backend.log" 2>&1 &

# 3) Automation Worker (7001)
echo "[3/5] 启动 Automation Worker (http://127.0.0.1:7001) ..."
nohup "$PY" prism_backend/automation_worker/worker.py > "$LOGS/worker.log" 2>&1 &

# 4) Celery
echo "[4/5] 启动 Celery Worker ..."
(cd "$ROOT/prism_backend" && nohup "$PY" -m celery -A fastapi_app.tasks.celery_app worker --loglevel=info --pool=threads --concurrency=8 > "$ROOT/logs/celery.log" 2>&1 &)

# 5) 前端 (3000)
echo "[5/5] 启动前端 (http://localhost:3000) ..."
(cd "$ROOT/prism_frontend" && nohup npm run dev > "$ROOT/logs/frontend.log" 2>&1 &)

echo
echo "============================================"
echo "  服务已启动:"
echo "    前端    http://localhost:3000"
echo "    后端    http://127.0.0.1:7000/api/docs"
echo "    Worker  http://127.0.0.1:7001/health"
echo "  日志目录: $LOGS"
echo "============================================"
