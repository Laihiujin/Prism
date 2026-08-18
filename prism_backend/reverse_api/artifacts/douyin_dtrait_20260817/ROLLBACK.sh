#!/bin/sh
set -eu
ROOT="${1:-$(CDPATH= cd -- "$(dirname -- "$0")/../../../.." && pwd)}"
ART="$ROOT/prism_backend/reverse_api/artifacts/douyin_dtrait_20260817/original"
cp "$ART/douyin_abogus_runner.js" "$ROOT/prism_backend/reverse_api/signing/douyin_abogus_runner.js"
cp "$ART/douyin_abogus_signer.py" "$ROOT/prism_backend/reverse_api/signing/douyin_abogus_signer.py"
cp "$ART/douyin_http.py" "$ROOT/prism_backend/app_new/platforms/douyin_http.py"
python3 - "$ROOT" <<'PY'
import pathlib, sys
root=pathlib.Path(sys.argv[1])
for name in ('dtrait-1.0.0.16.js','zero-trust-1.0.0.381.js','zero-trust-rsa-414.330fdc91.js','verifycenter-1.0.0.399.js'):
 p=root/'prism_backend/reverse_api/signing/vendor'/name
 if p.exists(): p.unlink()
PY
echo 'ROLLBACK_OK branch=poll_status field=x-tt-session-dtrait restored=legacy_a_bogus_only'
