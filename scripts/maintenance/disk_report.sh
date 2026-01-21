#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "[disk_report] root: ${ROOT_DIR}"
echo

echo "[disk_report] top directories (depth=2):"
du -h --max-depth=2 "${ROOT_DIR}" 2>/dev/null | sort -h | tail -n 40
echo

if command -v git >/dev/null 2>&1 && [ -d "${ROOT_DIR}/.git" ]; then
  echo "[disk_report] git objects:"
  (cd "${ROOT_DIR}" && git count-objects -vH) || true
  echo
fi

echo "[disk_report] largest files (excluding .git, top 25):"
find "${ROOT_DIR}" \
  -path "${ROOT_DIR}/.git" -prune -o \
  -type f -printf "%s\t%p\n" 2>/dev/null \
  | sort -n \
  | tail -n 25 \
  | awk 'BEGIN{split("B KB MB GB TB",u," ")} {s=$1; i=1; while (s>=1024 && i<5) {s/=1024; i++} printf "%.2f %s\t%s\n", s, u[i], $2}'
