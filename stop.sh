#!/usr/bin/env bash
# Prism 停止（PM2，macOS/Linux）。保留数据与日志，下次用 ./start-mac.sh 重新拉起。
# 用法: ./stop.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PM2_HOME="$ROOT/runtime-data/pm2"

PM2="$ROOT/node_modules/.bin/pm2"
if [ ! -x "$PM2" ] && [ -x "$ROOT/prism_frontend/node_modules/.bin/pm2" ]; then
  PM2="$ROOT/prism_frontend/node_modules/.bin/pm2"
fi
if [ ! -x "$PM2" ]; then
  PM2="$(command -v pm2 || true)"
fi
if [ -z "$PM2" ] || [ ! -x "$PM2" ]; then
  echo "[ERROR] 未找到 pm2" >&2
  exit 1
fi

echo "[STOP] 停止 Prism PM2 栈 ..."
"$PM2" delete all
echo
echo "[OK] 完成。(数据与日志保留在 $PM2_HOME)"
