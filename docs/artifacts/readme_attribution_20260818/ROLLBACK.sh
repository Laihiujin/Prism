#!/bin/sh
set -eu
ROOT="${1:-$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)}"
ART="$ROOT/docs/artifacts/readme_attribution_20260818/original"
cp "$ART/README.md" "$ROOT/README.md"
cp "$ART/NOTICE.txt" "$ROOT/NOTICE.txt"
echo 'ROLLBACK_OK branch=README project-support-and-license field=upstream-attributions restored=generic-acknowledgement'
