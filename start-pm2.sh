#!/usr/bin/env bash
# Prism 一键启动（PM2，macOS）
# 用法: ./start-pm2.sh
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PM2_HOME="$ROOT/runtime-data/pm2"
PM2="$ROOT/prism_frontend/node_modules/.bin/pm2"
mkdir -p "$PM2_HOME" "$ROOT/logs"

# 先清掉残留进程，避免端口占用
pkill -f "fastapi_app/run.py" 2>/dev/null
pkill -f "automation_worker/worker.py" 2>/dev/null
pkill -f "celery -A fastapi_app" 2>/dev/null
pkill -f "persona.*serve" 2>/dev/null
pkill -f "tools/persona-studio/dashboard/node_modules/.bin/vite" 2>/dev/null
pkill -f "persona-studio/proxies/mihomo" 2>/dev/null
sleep 1

echo "============================================"
echo "  Prism 启动 (PM2)"
echo "============================================"
"$PM2" start ecosystem-mac.config.js
echo
"$PM2" list
echo
echo "访问:"
echo "  前端        http://localhost:3000"
echo "  后端        http://127.0.0.1:7000/api/docs"
echo "  Worker      http://127.0.0.1:7001/health"
echo "  Persona API http://127.0.0.1:8787"
echo "  代理网关     http://127.0.0.1:7771-7776 (sg/jp/us/de/tw/hk)"

echo
echo "常用: PM2_HOME=$PM2_HOME $PM2 logs / restart all / stop all"
