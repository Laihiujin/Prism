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

mkdir -p "${PRISM_DATA_DIR}/logs" "${PRISM_DATA_DIR}/db" "${PRISM_DATA_DIR}/uploads"

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
  for pid in "${backend_pid:-}" "${worker_pid:-}" "${celery_pid:-}"; do
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

python -u automation_worker/worker.py &
worker_pid=$!

python -u fastapi_app/run.py &
backend_pid=$!

wait -n "${celery_pid}" "${worker_pid}" "${backend_pid}"
