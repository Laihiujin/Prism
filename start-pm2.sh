#!/usr/bin/env bash
# Prism 一键启动（PM2，macOS）
# 用法: ./start-pm2.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PM2_HOME="$ROOT/runtime-data/pm2"
mkdir -p "$PM2_HOME" "$ROOT/logs"

# pm2 是根目录 npm 依赖（package.json devDependencies）；依次从根 node_modules、
# prism_frontend node_modules、系统 PATH 解析，找不到则提示先引导。
PM2="$ROOT/node_modules/.bin/pm2"
if [ ! -x "$PM2" ] && [ -x "$ROOT/prism_frontend/node_modules/.bin/pm2" ]; then
  PM2="$ROOT/prism_frontend/node_modules/.bin/pm2"
fi
if [ ! -x "$PM2" ]; then
  PM2="$(command -v pm2 || true)"
fi
if [ -z "$PM2" ] || [ ! -x "$PM2" ]; then
  echo "[ERROR] 未找到 pm2。请先运行引导: python3 bootstrap.py（会安装根目录 npm 依赖）" >&2
  exit 1
fi

# Stop the previous managed stack before probing ports. Otherwise PM2 may
# immediately restart an old backend between the probe and the new bind.
"$PM2" delete all >/dev/null 2>&1 || true

# 先清掉残留进程，避免端口占用
pkill -f "fastapi_app/run.py" 2>/dev/null || true
pkill -f "automation_worker/worker.py" 2>/dev/null || true
pkill -f "celery -A fastapi_app" 2>/dev/null || true
pkill -f "persona.*serve" 2>/dev/null || true
pkill -f "tools/persona-studio/dashboard/node_modules/.bin/vite" 2>/dev/null || true
pkill -f "persona-studio/proxies/mihomo" 2>/dev/null || true
sleep 1

# Resolve one endpoint after old processes are gone. Explicit
# PRISM_BACKEND_PORT/URL values remain authoritative.
"$ROOT/prismenv/bin/python" "$ROOT/scripts/prism_runtime.py" prepare >/dev/null

echo "============================================"
echo "  Prism 启动 (PM2)"
echo "============================================"
"$PM2" start ecosystem.config.js --only prism-redis,prism-backend --update-env
if ! "$ROOT/prismenv/bin/python" "$ROOT/scripts/prism_runtime.py" health --timeout 60; then
  echo "[WARN] 后端未能绑定所选端口，重新选择端口并重试一次..." >&2
  "$PM2" delete prism-backend >/dev/null 2>&1 || true
  "$ROOT/prismenv/bin/python" "$ROOT/scripts/prism_runtime.py" prepare >/dev/null
  "$PM2" start ecosystem.config.js --only prism-backend --update-env
  "$ROOT/prismenv/bin/python" "$ROOT/scripts/prism_runtime.py" health --timeout 60
fi
"$PM2" start ecosystem.config.js --only prism-worker,prism-celery,prism-frontend,persona-api,persona-proxy,persona-dashboard,hermes-dashboard,hermes-webui,deepseek-harness --update-env
PRISM_BACKEND_URL="$("$ROOT/prismenv/bin/python" -c 'import json, pathlib; print(json.loads(pathlib.Path("runtime-data/runtime.json").read_text())["backend_url"])')"
echo
"$PM2" list
echo
echo "访问:"
echo "  前端        http://localhost:3000"
echo "  后端        $PRISM_BACKEND_URL/api/docs"
echo "  Worker      http://127.0.0.1:7001/health"
echo "  Persona API http://127.0.0.1:8787"
echo "  代理网关     http://127.0.0.1:7771-7776 (sg/jp/us/de/tw/hk)"

# 明确打开 Prism 主前端，避免浏览器停留在 Persona Dashboard:5173。
# 统一使用 localhost，避免浏览器把 localhost 与 127.0.0.1 视为两个独立站点。
# 等待前端就绪后再打开，避免浏览器先弹 5173（Persona）或加载到"无法连接"。
FRONTEND_URL="http://localhost:3000/"
if command -v open >/dev/null 2>&1; then
  if command -v curl >/dev/null 2>&1; then
    for _ in $(seq 1 60); do
      code="$(curl -s -o /dev/null -w '%{http_code}' "$FRONTEND_URL" 2>/dev/null || true)"
      case "$code" in
        20[0-9]) break ;;
      esac
      sleep 1
    done
  fi
  open "$FRONTEND_URL"
fi

echo
echo "常用: PM2_HOME=$PM2_HOME $PM2 logs / restart all / stop all"
