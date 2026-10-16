#!/usr/bin/env bash
# Same lifecycle and readiness checks as start.bat; no duplicate PM2 stack.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
NODE="$(command -v node || true)"
if [ -n "$NODE" ] && [ "$("$NODE" -p 'process.versions.node.split(".")[0]')" -lt 22 ]; then NODE=""; fi
if [ -z "$NODE" ]; then
  ARCH="$(uname -m)"; [ "$ARCH" != x86_64 ] || ARCH=x64
  STORE="$ROOT/runtime-data/node"; mkdir -p "$STORE"
  NODE="$(find "$STORE" -type f -name node -perm -111 | head -1)"
  if [ -z "$NODE" ]; then
    for BASE in https://nodejs.org/dist/latest-v22.x https://npmmirror.com/mirrors/node/latest-v22.x; do
      if curl -fsSL --connect-timeout 15 --max-time 60 "$BASE/SHASUMS256.txt" -o "$STORE/SHASUMS256.txt"; then
        ENTRY="$(grep "darwin-$ARCH.tar.gz$" "$STORE/SHASUMS256.txt" | head -1)"
        FILE="${ENTRY##* }"; HASH="${ENTRY%% *}"
        if [ -n "$FILE" ] && curl -fsSL --connect-timeout 15 --max-time 180 "$BASE/$FILE" -o "$STORE/$FILE" && (cd "$STORE" && echo "$HASH  $FILE" | shasum -a 256 -c -); then
          tar -xzf "$STORE/$FILE" -C "$STORE"
          rm "$STORE/$FILE"
          NODE="$STORE/${FILE%.tar.gz}/bin/node"; break
        fi
      fi
    done
  fi
fi
[ -n "$NODE" ] || { echo 'All Node download sources failed' >&2; exit 1; }
export PATH="$(dirname "$NODE"):$PATH"
exec "$NODE" "$ROOT/scripts/runtime/ensure-runtime.cjs" "${@:-start}"
