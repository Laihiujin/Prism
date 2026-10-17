"""Validate local delivery evidence, not aesthetic quality or provider truthfulness."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve(base: Path, path: str) -> Path:
    value = Path(path).expanduser()
    return value if value.is_absolute() else base / value


def check(manifest: dict, base: Path, require_approved: bool = False) -> list[str]:
    errors: list[str] = []
    assets = {}
    for item in manifest.get('assets', []):
        aid = item['id']
        if aid in assets:
            errors.append(f'duplicate asset: {aid}')
        assets[aid] = item
        source = resolve(base, item['path'])
        if not source.is_file():
            errors.append(f'{aid}: original file missing')
        elif sha256(source) != item.get('sha256'):
            errors.append(f'{aid}: original hash mismatch')
    covers = manifest.get('covers', [])
    if not covers:
        errors.append('no covers')
    if len(covers) != manifest.get('expected_count'):
        errors.append('cover count differs from expected_count')
    matrix = set()
    concepts = {}
    for cover in covers:
        cid = cover['id']
        key = (cover['platform'], cover['version'], cover['ratio'])
        if key in matrix:
            errors.append(f'{cid}: duplicate platform/version/ratio')
        matrix.add(key)
        concept = cover.get('concept_key')
        if not concept:
            errors.append(f'{cid}: missing concept_key')
        else:
            group = concepts.setdefault(concept, set())
            group.add((cover['platform'], cover['version']))
        required = set(cover.get('required_product_ids', []))
        for aid in required:
            if assets.get(aid, {}).get('role') != 'product_original':
                errors.append(f'{cid}: invalid original product reference {aid}')
        attempts = cover.get('attempts', [])
        if not attempts:
            errors.append(f'{cid}: missing generation/edit call evidence')
        for i, attempt in enumerate(attempts):
            refs = set(attempt.get('original_asset_ids', []))
            if not required <= refs:
                errors.append(f'{cid}: attempt {i} missing original product references')
            if not refs <= assets.keys():
                errors.append(f'{cid}: attempt {i} unknown asset references')
            if not attempt.get('tool') or not attempt.get('provider_record'):
                errors.append(f'{cid}: attempt {i} missing tool/provider record')
        path = resolve(base, cover['path'])
        if not path.is_file():
            errors.append(f'{cid}: output missing')
            continue
        header = path.read_bytes()[:24]
        if len(header) != 24 or header[:8] != b'\x89PNG\r\n\x1a\n' or header[12:16] != b'IHDR':
            errors.append(f'{cid}: expected PNG output for this checker')
            continue
        width, height = struct.unpack('>II', header[16:24])
        rw, rh = map(int, cover['ratio'].split(':'))
        if min(width, height, rw, rh) <= 0 or width * rh != height * rw:
            errors.append(f'{cid}: aspect ratio mismatch')
        if cover.get('visual_review') != 'pass':
            errors.append(f'{cid}: visual review not passed')
        if require_approved and (not cover.get('approved_by_user') or cover.get('approved_sha256') != sha256(path)):
            errors.append(f'{cid}: missing current-file user approval')
    for concept, groups in concepts.items():
        if len(groups) > 1:
            errors.append(f'{concept}: reused concept across platforms or versions; review substantive differences')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--require-approved', action='store_true')
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding='utf-8'))
        errors = check(data, args.manifest.resolve().parent, args.require_approved)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f'FAIL: invalid manifest or inaccessible file: {exc}')
        return 1
    for error in errors:
        print('FAIL:', error)
    if errors:
        return 1
    print('PASS: local evidence and PNG ratio checks; visual/provider assertions still require real review.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
