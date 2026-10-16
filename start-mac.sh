#!/usr/bin/env bash
# Same lifecycle and readiness checks as start.bat; no duplicate PM2 stack.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [ -x "$ROOT/prismenv/bin/python" ]; then
  PY="$ROOT/prismenv/bin/python"
else
  PY="$(command -v python3 || true)"
fi
if [ -z "$PY" ]; then
  echo "Python bootstrap interpreter missing; run ./deploy.sh first." >&2
  exit 1
fi
exec "$PY" "$ROOT/bootstrap.py" "${@:-start}"
