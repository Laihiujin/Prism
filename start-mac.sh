#!/usr/bin/env bash
# Prism macOS/Linux 一键启动：先引导环境，再用 PM2 托管所有进程。
# 用法: ./start-mac.sh
#
# 说明：
# - macOS 上所有进程由 PM2 统一托管（见 start-pm2.sh / ecosystem-mac.config.js），
#   本脚本只负责把环境准备好（幂等），然后交给 PM2 启动整套服务。
# - 环境准备复用跨平台入口 bootstrap.py（创建 prismenv + pip 依赖 + 前端依赖 + .env + 检查 Redis）。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

export PLAYWRIGHT_BROWSERS_PATH="$ROOT/browsers"
export PLAYWRIGHT_AUTO_INSTALL=0

log() { echo "==> $*"; }

# ── 0) 环境引导（幂等）─────────────────────────────────────────────
log "环境引导 (bootstrap.py)..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] 未找到 python3。请先安装 Python 3.11：brew install python@3.11" >&2
  exit 1
fi
python3 "$ROOT/bootstrap.py" --no-browsers || {
  echo "[ERROR] 环境引导失败（详见上方输出）" >&2
  exit 1
}

# ── 1) 确认 prismenv 解释器 ───────────────────────────────────────
if [ ! -x "$ROOT/prismenv/bin/python" ]; then
  echo "[ERROR] prismenv 解释器不存在: $ROOT/prismenv/bin/python" >&2
  echo "        请先运行: python3 bootstrap.py" >&2
  exit 1
fi

# ── 2) 确认 Redis（PM2 通过 ecosystem-mac.config.js 的 prism-redis 启动它）────
if ! command -v redis-server >/dev/null 2>&1; then
  echo "[ERROR] 未检测到 redis-server，Prism 无法运行（Celery 队列与账号锁依赖它）。" >&2
  echo "        安装: brew install redis && redis-server --daemonize yes" >&2
  exit 1
fi

# ── 3) 交给 PM2 托管所有进程 ─────────────────────────────────────
log "交给 PM2 托管所有进程 ..."
exec ./start-pm2.sh
