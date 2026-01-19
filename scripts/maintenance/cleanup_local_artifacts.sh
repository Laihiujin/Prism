#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

APPLY=false
for arg in "$@"; do
  case "${arg}" in
    --apply) APPLY=true ;;
    -h|--help)
      echo "Usage: $0 [--apply]"
      echo
      echo "Default is dry-run. Use --apply to actually delete local artifacts."
      exit 0
      ;;
  esac
done

targets=(
  "syn_frontend_react/.next"
  "syn_frontend_react/out"
  "syn_frontend_react/node_modules"
  "node_modules"
  "temp"
  "logs"
  "syn_backend/logs"
  "syn_backend/venv"
  "synenv"
  "syn_backend/syn_backend"
  "syn_backend/config/syn_backend"
)

echo "[cleanup] root: ${ROOT_DIR}"
echo "[cleanup] mode: $([ "${APPLY}" = true ] && echo APPLY || echo DRY-RUN)"
echo

for rel in "${targets[@]}"; do
  path="${ROOT_DIR}/${rel}"
  if [ ! -e "${path}" ]; then
    continue
  fi

  size="$(du -sh "${path}" 2>/dev/null | awk '{print $1}' || echo "?")"
  echo "[cleanup] target: ${rel} (${size})"

  if [ "${APPLY}" = true ]; then
    rm -rf "${path}"
    echo "[cleanup] removed: ${rel}"
  fi
  echo
done

if [ "${APPLY}" = false ]; then
  echo "[cleanup] dry-run complete."
  echo "[cleanup] re-run with --apply to actually delete."
fi
