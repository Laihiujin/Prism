"""Compile a product logic sheet into prompt constraints and a review checklist for one scene."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


class SceneError(ValueError):
    """The requested scene breaks the product logic sheet."""


def _units(sheet: dict) -> dict:
    return {unit['id']: unit for unit in sheet.get('units', [])}


def _liberty(sheet: dict, liberty_id: str | None) -> dict | None:
    if not liberty_id or liberty_id == 'none':
        return None
    for liberty in sheet.get('liberties', []):
        if liberty['id'] == liberty_id:
            return liberty
    raise SceneError(f'unknown liberty: {liberty_id}')


def _allowed_together(sheet: dict, visible: list[str]) -> bool:
    """Units may share a literal view only if one interaction step shows them together."""
    wanted = set(visible)
    return any(wanted <= set(step.get('visible_units', [])) for step in sheet.get('interaction', []))


def compile_scene(sheet: dict, visible: list[str], liberty_id: str | None = None) -> dict:
    units = _units(sheet)
    unknown = [unit_id for unit_id in visible if unit_id not in units]
    if unknown:
        raise SceneError(f'unknown units: {", ".join(unknown)}')
    if not visible:
        raise SceneError('choose at least one visible unit')
    liberty = _liberty(sheet, liberty_id)
    if len(visible) > 1 and not _allowed_together(sheet, visible):
        if not liberty or not set(visible) <= set(liberty.get('allows_units', [])):
            raise SceneError(
                f'{", ".join(visible)} never appear in one real view; use a liberty that allows them '
                '(e.g. packshot or split frame) or show one unit per image')

    applicable = [c for c in sheet.get('constraints', [])
                  if '*' in c.get('applies_to', ['*']) or set(c.get('applies_to', [])) & set(visible)]
    hidden = [unit for unit_id, unit in units.items() if unit_id not in visible]

    prompt_lines = []
    product = sheet.get('product', {})
    prompt_lines.append(f"Product: {product.get('name', '')} {product.get('variant', '')}".strip())
    for unit_id in visible:
        unit = units[unit_id]
        parts = ', '.join(unit.get('visible_parts', []))
        if liberty and liberty['id'] == 'packshot':
            prompt_lines.append(f"{unit['label']}: {unit.get('orientation', '')}; visible parts: {parts}")
        else:
            prompt_lines.append(
                f"{unit['label']} mounted on the {unit.get('side', '')}, {unit.get('orientation', '')}, "
                f"{unit.get('height', '')}; visible parts: {parts}; setting: {unit.get('environment', '')}")
    if liberty:
        prompt_lines.append(liberty['prompt'])
    for constraint in applicable:
        if not liberty or constraint.get('applies_to') != ['*']:
            prompt_lines.append(constraint['prompt'])
    negatives = [f"no {unit['label']}" for unit in hidden]
    negatives += [item['negative'] for item in sheet.get('forbidden', []) if item.get('negative')]

    checklist = [f"[{c['id']}] {c['check']}" for c in applicable]
    checklist += [f'[hidden] {unit["label"]} does not appear' for unit in hidden]
    checklist += [f'[forbidden] {item["text"]}' for item in sheet.get('forbidden', [])]
    if not product.get('model_specific_found', False):
        checklist.append('[provisional] sheet is not confirmed by model-specific sources; recheck before final delivery')

    blocked = [u['question'] for u in sheet.get('unknowns', [])]
    return {'prompt': prompt_lines, 'negative': negatives, 'checklist': checklist, 'unknowns': blocked}


def render(result: dict) -> str:
    lines = ['## Prompt constraints', *[f'- {line}' for line in result['prompt']]]
    if result['negative']:
        lines += ['', '## Avoid', '- ' + '; '.join(result['negative'])]
    lines += ['', '## Review checklist', *[f'- [ ] {item}' for item in result['checklist']]]
    if result['unknowns']:
        lines += ['', '## Open unknowns (check the concept does not depend on them)',
                  *[f'- {item}' for item in result['unknowns']]]
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sheet', type=Path)
    parser.add_argument('--visible', required=True, help='comma-separated unit ids visible in this scene')
    parser.add_argument('--liberty', default='none', help='liberty id from the sheet, or none')
    parser.add_argument('--json', action='store_true', help='print JSON instead of Markdown')
    args = parser.parse_args()
    try:
        sheet = json.loads(args.sheet.read_text(encoding='utf-8'))
        visible = [item.strip() for item in args.visible.split(',') if item.strip()]
        result = compile_scene(sheet, visible, args.liberty)
    except (OSError, ValueError, KeyError) as exc:
        print(f'FAIL: {exc}')
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
