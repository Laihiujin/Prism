#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="/app/prism_backend:${PYTHONPATH:-}"
export FORKED_BY_MULTIPROCESSING="${FORKED_BY_MULTIPROCESSING:-1}"
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-7000}"
export PLAYWRIGHT_HEADLESS="${PLAYWRIGHT_HEADLESS:-true}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/ms-playwright}"
export PRISM_APP_ROOT="${PRISM_APP_ROOT:-/app}"
export PRISM_DATA_DIR="${PRISM_DATA_DIR:-/app/runtime-data}"
export CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-8}"
export PERSONA_ENABLED="${PERSONA_ENABLED:-true}"
export PERSONA_API_URL="${PERSONA_API_URL:-http://127.0.0.1:8787}"
export HERMES_ENABLED="${HERMES_ENABLED:-true}"
export HERMES_WEBUI_HOST="${HERMES_WEBUI_HOST:-0.0.0.0}"
# 9131 与 Prism 检查器默认一致（get_hermes_runtime_status 查 PRISM_HERMES_WEBUI_PORT=9131）
export HERMES_WEBUI_PORT="${HERMES_WEBUI_PORT:-9131}"
export HERMES_HOME="${HERMES_HOME:-${PRISM_DATA_DIR}/hermes-home}"
export HERMES_WEBUI_STATE_DIR="${HERMES_WEBUI_STATE_DIR:-${HERMES_HOME}/webui}"
# hermes 装在独立 /app/prismenv venv；检查器经此认解释器（agent_installed）
export PRISM_HERMES_PYTHON="${PRISM_HERMES_PYTHON:-/app/prismenv/bin/python}"

mkdir -p "${PRISM_DATA_DIR}/logs" "${PRISM_DATA_DIR}/db" "${PRISM_DATA_DIR}/uploads"

# 浏览器二进制：构建时 patchright install 装到 /root/.cache/ms-playwright，
# 而 compose 设 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright。软链对齐。
if [ -d /root/.cache/ms-playwright ] && [ ! -e /ms-playwright ]; then
  ln -s /root/.cache/ms-playwright /ms-playwright
  echo "[start-app] symlink /ms-playwright -> /root/.cache/ms-playwright"
fi

# 兼容：业务代码多处硬编码 Path(settings.BASE_DIR)/"db"（BASE_DIR=/app/prism_backend），
# 而数据在 PRISM_DATA_DIR。用软链把 BASE_DIR 下的数据目录指到数据目录。
for dir in db cookiesFile videoFile uploads browser_profiles fingerprints storage; do
  if [ ! -e "/app/prism_backend/${dir}" ] && [ -d "${PRISM_DATA_DIR}/${dir}" ]; then
    ln -s "${PRISM_DATA_DIR}/${dir}" "/app/prism_backend/${dir}"
    echo "[start-app] symlink /app/prism_backend/${dir} -> ${PRISM_DATA_DIR}/${dir}"
  else
    echo "[start-app] /app/prism_backend/${dir} exists: $(ls -ld /app/prism_backend/${dir} 2>&1 | awk '{print $1, $NF}')"
  fi
done

cd /app/prism_backend

cleanup() {
  local code=$?
  for pid in "${backend_pid:-}" "${worker_pid:-}" "${celery_pid:-}" "${persona_pid:-}" "${hermes_webui_pid:-}"; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
    fi
  done
  wait || true
  exit "${code}"
}

trap cleanup EXIT INT TERM

python -u -m celery -A fastapi_app.tasks.celery_app.celery_app worker \
  --loglevel=info \
  --pool=threads \
  --concurrency="${CELERY_CONCURRENCY}" \
  --hostname="prism-worker@docker" &
celery_pid=$!

# ── Persona Studio（Browser Identity 层）──
# persona serve 提供 HTTP API；默认引擎用 patchright（attach CDP 可用）
if [ "${PERSONA_ENABLED}" = "true" ] && command -v persona >/dev/null 2>&1; then
  echo "[start-app] 启动 Persona Studio: ${PERSONA_API_URL}"
  persona default-engine patchright >/dev/null 2>&1 || true
  persona serve --host 0.0.0.0 --port 8787 > "${PRISM_DATA_DIR}/logs/persona.log" 2>&1 &
  persona_pid=$!
else
  echo "[start-app] Persona Studio 未启用（PERSONA_ENABLED=${PERSONA_ENABLED} 或未安装）"
  persona_pid=""
fi

python -u automation_worker/worker.py &
worker_pid=$!

python -u fastapi_app/run.py &
backend_pid=$!

# ── Hermes WebUI（可选，默认启用；端口 9131 与 Prism 检查器一致）──
if [ "${HERMES_ENABLED}" = "true" ] && [ -f /app/prismenv/bin/python ] && [ -f /app/tools/hermes-webui/server.py ]; then
  echo "[start-app] 启动 Hermes WebUI: ${HERMES_WEBUI_HOST}:${HERMES_WEBUI_PORT}"
  mkdir -p "${HERMES_WEBUI_STATE_DIR}" "${HERMES_HOME}"
  HERMES_WEBUI_HOST="${HERMES_WEBUI_HOST}" \
  HERMES_WEBUI_PORT="${HERMES_WEBUI_PORT}" \
  HERMES_HOME="${HERMES_HOME}" \
  HERMES_WEBUI_STATE_DIR="${HERMES_WEBUI_STATE_DIR}" \
  HERMES_WEBUI_AGENT_DIR="/app/tools/hermes-agent" \
  /app/prismenv/bin/python /app/tools/hermes-webui/server.py \
    > "${PRISM_DATA_DIR}/logs/hermes-webui.log" 2>&1 &
  hermes_webui_pid=$!
else
  echo "[start-app] Hermes WebUI 未启用（HERMES_ENABLED=${HERMES_ENABLED}）"
  hermes_webui_pid=""
fi

wait -n "${celery_pid}" "${worker_pid}" "${backend_pid}" ${persona_pid:+} ${hermes_webui_pid:+}
