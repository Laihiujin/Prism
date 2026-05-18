#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="/app/syn_backend:${PYTHONPATH:-}"
export FORKED_BY_MULTIPROCESSING="${FORKED_BY_MULTIPROCESSING:-1}"
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-7000}"
export PLAYWRIGHT_HEADLESS="${PLAYWRIGHT_HEADLESS:-true}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/ms-playwright}"
export SYNAPSE_APP_ROOT="${SYNAPSE_APP_ROOT:-/app}"
export SYNAPSE_DATA_DIR="${SYNAPSE_DATA_DIR:-/app/runtime-data}"
export CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-8}"

mkdir -p "${SYNAPSE_DATA_DIR}/logs" "${SYNAPSE_DATA_DIR}/db" "${SYNAPSE_DATA_DIR}/uploads"

cd /app/syn_backend

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
  --hostname="synapse-worker@docker" &
celery_pid=$!

python -u playwright_worker/worker.py &
worker_pid=$!

python -u fastapi_app/run.py &
backend_pid=$!

wait -n "${celery_pid}" "${worker_pid}" "${backend_pid}"
