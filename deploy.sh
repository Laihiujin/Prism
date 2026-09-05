#!/usr/bin/env bash
# Prism 本地一键部署入口（macOS / Linux）—— 零依赖：不需要预装 Python。
#
# 用法（同一套子命令，交给 bootstrap.py 用自给到的 Python 运行）：
#   ./deploy.sh                # 完整一键部署（缺什么补什么 + PM2 启动整套）
#   ./deploy.sh start          # 环境就绪时快速启动（跳过浏览器）
#   ./deploy.sh stop           # 停止（pm2 delete all，保留数据）
#   ./deploy.sh status         # PM2 进程状态
#   ./deploy.sh webui          # 打开部署 Web UI（127.0.0.1:8440）
#   ./deploy.sh check          # 只探测环境、不改动
#
# 若系统没有 python3，这里会自动用仓库内嵌 micromamba 造一个 .deployenv 来跑，
# 全程不需要你手动安装 Python。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

log() { echo "[deploy] $*"; }

# --- 解析一个能跑 bootstrap.py 的 Python ------------------------------------
resolve_py() {
  # 1) 系统 python3 / python
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then
      if "$c" -c "import sys" >/dev/null 2>&1; then
        PY="$c"; return
      fi
    fi
  done
  # 2) 仓库内嵌 micromamba（macOS/arm64 随仓库附带；Linux/x86 需另见提示）
  local MM="$ROOT/scripts/packaging/provision/micromamba/micromamba"
  if [ -x "$MM" ]; then
    log "未找到系统 Python，用内嵌 micromamba 自给 deployenv ..."
    if "$MM" create -p "$ROOT/.deployenv" -c conda-forge python=3.11 -y >/dev/null 2>&1 \
       && "$MM" run -p "$ROOT/.deployenv" python -c "import sys" >/dev/null 2>&1; then
      PY="$MM -p $ROOT/.deployenv run python"; return
    fi
  fi
  # 3) 兜底：明确提示（不擅自改系统）。macOS 预装 python3，Win 见 deploy.cmd。
  echo "[ERROR] 未找到 Python，且内嵌 micromamba 不可用（仅支持 macOS/arm64 等）。" >&2
  echo "       macOS: 已预装 python3，若报错请安装 Xcode Command Line Tools。" >&2
  echo "       Linux:  sudo apt install python3.11   （或 brew install python@3.11）" >&2
  echo "       Windows: 直接运行  deploy.cmd  （PowerShell 会自动下载便携 Python）。" >&2
  exit 1
}
resolve_py

# --- 转发命令：默认/`full` 走引擎完整管线（自给运行时 + 组件环境 + 启动）；--- 
# --- 其余子命令走 bootstrap.py（快速启动/停止/状态/WebUI/只读探测）------------
CMD="${1:-full}"        # 不带参数 = 完整部署（引擎 full：自给 Python/Node/Redis + 重建组件环境 + PM2 启动）
shift || true
EXTRA=("$@")

case "$CMD" in
  start|stop|status|webui)
    if [ "${#EXTRA[@]}" -gt 0 ]; then
      exec $PY "$ROOT/bootstrap.py" "$CMD" "${EXTRA[@]}"
    else
      exec $PY "$ROOT/bootstrap.py" "$CMD"
    fi ;;
  check|plan)
    exec $PY "$ROOT/bootstrap.py" --check ;;
  bootstrap)
    # 显式 bootstrap = venv 路径完整部署（不重建组件环境，用于已装 Python 的轻量路径）
    exec $PY "$ROOT/bootstrap.py" bootstrap ;;
  *)
    # 默认 / `full` = 引擎完整管线（幂等）：探测 → 补齐工具 → micromamba 供给 prismenv + 组件环境
    # → 前端/根目录 npm 依赖 → .env → Redis → 浏览器 → PM2 启动整套
    exec $PY "$ROOT/deploy/deploy.py" full ;;
esac
