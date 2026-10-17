"""Compile a product-locked shot plan, and re-bind its scenes and characters without touching the product.

Product lock: any shot that shows the product (product shot, product in a scene, a person using the
product) carries the verified original product images as its first references, every time, and opens
its prompt with the same product block. Scenes and characters are slots. Re-binding a slot rewrites
only the scene and character lines; the product block of every shot stays byte-identical, which the
plan proves with a per-shot digest.

    python3 compile_product_lock.py plan.json
    python3 compile_product_lock.py plan.json --bind home=SCENE-B --bind lead=CHAR-C
    python3 compile_product_lock.py plan.json --matrix home=SCENE-B,SCENE-C --matrix lead=CHAR-C,CHAR-D

This file is shared between CineForge-Skills (scripts/) and Prism's social-asset-studio skill
(scripts/). Keep both copies identical. When the repository's product-logic compiler sits next to
this file it is used for the physics lines of each shot.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import itertools
import json
import sys
from pathlib import Path

PRODUCT_CLASSES = {"product", "product_in_scene", "interaction"}
SHOT_CLASSES = PRODUCT_CLASSES | {"no_product"}


class LockError(ValueError):
    """The plan or the product-lock card cannot be compiled."""


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _physics_compiler():
    """Return the sibling product-logic compiler, whichever repository this copy lives in."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    for name, func in (("compile_product_logic", "compile_shot"), ("compile_product_rules", "compile_scene")):
        try:
            module = importlib.import_module(name)
        except ImportError:
            continue
        return name, getattr(module, func)
    return None, None


def _physics(logic: dict | None, shot: dict) -> tuple[list[str], list[str]]:
    """Physics lines and acceptance from the product-logic card; raises LockError on an impossible shot."""
    if not logic or shot["class"] not in PRODUCT_CLASSES:
        return [], []
    name, compile_fn = _physics_compiler()
    if not compile_fn:
        return _fallback_physics(logic, shot)
    visible = shot.get("visible_units", [])
    liberty = shot.get("liberty") or None
    try:
        if name == "compile_product_logic":
            result = compile_fn(logic, visible, liberty, shot.get("path") or [], shot.get("barrier_state", "closed"))
            return result["prompt_constraints"], result["acceptance"]
        result = compile_fn(logic, visible, liberty)
        return result["prompt"], result["checklist"]
    except ValueError as exc:
        raise LockError(f"product logic: {exc}") from exc


def _fallback_physics(logic: dict, shot: dict) -> tuple[list[str], list[str]]:
    """Minimal side and barrier checks for hosts that ship this file without a product-logic compiler."""
    units = {u["id"]: u for u in logic.get("units", [])}
    visible = shot.get("visible_units", [])
    liberty = shot.get("liberty") or None
    together = any(set(visible) <= set(step.get("visible_units", [])) for step in logic.get("interaction", []))
    if len(visible) > 1 and not together and not liberty:
        raise LockError(f"product logic: {', '.join(visible)} never share one real view; use a liberty or one unit per shot")
    path = shot.get("path") or []
    if len(set(path)) > 1 and shot.get("barrier_state", "closed") != "open" and not liberty:
        raise LockError(f"product logic: camera path {' -> '.join(path)} crosses a closed barrier; cut or open it on screen")
    lines = [f"{units[u]['label']} on the {units[u].get('side', '')}, {units[u].get('orientation', '')}" for u in visible if u in units]
    lines += [c["prompt"] for c in logic.get("constraints", [])
              if "*" in c.get("applies_to", []) or set(c.get("applies_to", [])) & set(visible)]
    checks = [f"[{c['id']}] {c['check']}" for c in logic.get("constraints", [])
              if "*" in c.get("applies_to", []) or set(c.get("applies_to", [])) & set(visible)]
    checks += [f"[hidden] {u['label']} does not appear" for uid, u in units.items() if uid not in visible]
    return lines, checks


def check_card(card: dict) -> None:
    """Every product authority is an original; every original says which unit it governs."""
    if not card.get("originals"):
        raise LockError("product-lock card has no original product images")
    for original in card["originals"]:
        if original.get("provenance") != "original":
            raise LockError(
                f"{original.get('id')}: provenance is {original.get('provenance')!r}; only an original product "
                "image can govern the product, a generated image may only be a composition reference")
        if not original.get("governs_units"):
            raise LockError(f"{original.get('id')}: name the units this original governs")


def _originals_for(card: dict, units: list[str]) -> list[dict]:
    """Originals that govern the visible units, in card order; every visible unit must be covered."""
    chosen = [o for o in card["originals"] if set(o["governs_units"]) & set(units)]
    covered = {u for o in chosen for u in o["governs_units"]}
    missing = [u for u in units if u not in covered]
    if missing:
        raise LockError(f"no original product image governs {', '.join(missing)}")
    return chosen


def product_block(card: dict, shot: dict, slots: list[dict]) -> list[str]:
    """The product lines of a shot. Depends only on the card and the shot, never on scene or cast."""
    product = card["product"]
    lines = [f"Product memory: {card['memory']}"]
    for slot in slots:
        lines.append(f"{slot['slot']} is the exact {product['name']} ({slot['view']}), the authority for "
                     f"{', '.join(slot['governs'])}; reproduce it exactly as shown")
    keep = {item["unit"]: item["keep"] for item in card.get("identity", [])}
    for unit in shot.get("visible_units", []):
        if keep.get(unit):
            lines.append(f"{unit}: keep {'; '.join(keep[unit])}")
    return lines


def _digest(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:12]


def compile_shot(card: dict, logic: dict | None, plan: dict, shot: dict, binding: dict) -> dict:
    if shot.get("class") not in SHOT_CLASSES:
        raise LockError(f"{shot.get('id')}: class must be one of {', '.join(sorted(SHOT_CLASSES))}")
    refs: list[dict] = []
    prompt: list[str] = []
    acceptance: list[str] = []
    blockers: list[str] = []
    prerequisites: list[str] = []
    notes: list[str] = []
    product_lines: list[str] = []
    is_product = shot["class"] in PRODUCT_CLASSES

    def add_ref(role: str, ref: str, note: str, **extra) -> dict:
        entry = {"slot": f"Image {len(refs) + 1}", "role": role, "ref": ref, "note": note, **extra}
        refs.append(entry)
        return entry

    # 1. product originals first, every time
    if is_product:
        if not shot.get("visible_units"):
            raise LockError(f"{shot['id']}: a product shot must name its visible units")
        for original in _originals_for(card, shot["visible_units"]):
            add_ref("product_original", original["path"], "exact product, not a style suggestion",
                    view=original["view"], governs=original.get("governs", ["product identity"]),
                    sha256=original.get("sha256", ""))
        product_lines = product_block(card, shot, [r for r in refs if r["role"] == "product_original"])
        try:
            physics, physics_checks = _physics(logic, shot)
        except LockError as exc:
            physics, physics_checks = [], []
            blockers.append(str(exc))
        product_lines += physics
        acceptance += physics_checks
        acceptance += [f"[product-lock] {item['unit']}: {k}" for item in card.get("identity", [])
                       if item["unit"] in shot["visible_units"] for k in item["keep"]]
        acceptance += [f"[drift] {trap}" for trap in card.get("drift_traps", [])]
        acceptance.append("[product-lock] product region compared side by side with the attached originals")
        prompt += product_lines

    # 2. scene plate for the bound location
    location = shot.get("location")
    if location:
        scene_id = binding.get(location)
        scene = plan.get("scenes", {}).get(scene_id)
        if not scene:
            raise LockError(f"{shot['id']}: location slot {location!r} is bound to unknown scene {scene_id!r}")
        plate = scene.get("plates", {}).get(shot.get("plate", ""))
        if not plate:
            blockers.append(f"scene {scene_id} has no {shot.get('plate')!r} plate; add it to the scene first")
        else:
            if plate.get("status") == "to_generate":
                prerequisites.append(f"generate {scene_id} plate {shot['plate']!r} with the product originals attached "
                                     f"first: {plate['description']}")
            if is_product and logic and not shot.get("liberty"):
                sides = {u["id"]: u.get("viewed_from") for u in logic.get("units", [])}
                wrong = [u for u in shot["visible_units"] if sides.get(u) and plate.get("side") and sides[u] != plate["side"]]
                if wrong:
                    blockers.append(f"scene {scene_id} plate {shot['plate']!r} is on the {plate['side']} side, "
                                    f"but {', '.join(wrong)} is only visible from {sides[wrong[0]]}")
            entry = add_ref("scene_plate", plate["ref"], "place, architecture and light only")
            prompt.append(f"Setting: {entry['slot']} is {scene['label']}, {plate['description']}; keep its "
                          f"architecture, materials and light direction")
            if scene.get("light"):
                prompt.append(f"Light: {scene['light']}")
            mount = scene.get("mount", {}).get(plate.get("side", ""))
            if is_product and mount:
                prompt.append(f"Installation: {mount}")
            acceptance.append(f"[scene] matches {scene_id} plate {shot['plate']}")

    # 3. characters bound to the shot's roles
    for role in shot.get("roles", []):
        char_id = binding.get(role)
        character = plan.get("characters", {}).get(char_id)
        if not character:
            raise LockError(f"{shot['id']}: role {role!r} is bound to unknown character {char_id!r}")
        entry = add_ref("character", character["ref"], "identity and wardrobe only")
        prompt.append(f"{role}: {entry['slot']} is {character['label']}, {character['description']}")
        acceptance.append(f"[character] {role} is {char_id}: face, hair and wardrobe match {entry['slot']}")
        carry = dict(character.get("carry", {}))
        hand = shot.get("hand")
        if hand and shot["class"] == "interaction" and role == shot.get("actor", shot["roles"][0]) and hand in carry:
            free = [h for h in ("left", "right") if h not in carry]
            release = character.get("release", {})
            if free:
                notes.append(f"{char_id} uses the {free[0]} hand: the {hand} hand holds {carry[hand]}")
                hand = free[0]
            elif release:
                hand = hand if hand in release else next(iter(release))
                prompt.append(f"before touching the lock, {release[hand]}")
                notes.append(f"{char_id} frees the {hand} hand: {release[hand]}")
                carry.pop(hand)
            else:
                blockers.append(f"{char_id} carries something in both hands; give the character a release "
                                f"(how one hand is freed) or change the action")
        for held_hand, item in carry.items():
            prompt.append(f"{role} holds {item} in the {held_hand} hand throughout")
        if hand and shot["class"] == "interaction" and role == shot.get("actor", shot["roles"][0]):
            prompt.append(f"{role} operates the lock with the {hand} hand")

    # 4. composition reference: framing only, never product authority
    if shot.get("composition_ref"):
        entry = add_ref("composition", shot["composition_ref"], "framing and placement only")
        prompt.append(f"Framing follows {entry['slot']} for camera position, shot size and placement only; "
                      f"product, people and place come from the earlier images")
    if shot.get("action"):
        prompt.append(f"Action: {shot['action']}")
    if shot.get("camera"):
        prompt.append(f"Camera: {shot['camera']}")

    return {
        "id": shot["id"],
        "class": shot["class"],
        "references": refs,
        "prompt": prompt,
        "acceptance": acceptance,
        "blockers": blockers,
        "prerequisites": prerequisites,
        "notes": notes,
        "product_digest": _digest(product_lines) if is_product else None,
    }


def compile_plan(plan: dict, card: dict, logic: dict | None, overrides: dict | None = None) -> dict:
    check_card(card)
    binding = {**plan.get("bindings", {}), **(overrides or {})}
    shots = [compile_shot(card, logic, plan, shot, binding) for shot in plan["shots"]]
    return {"binding": binding, "product": card["product"]["name"], "shots": shots,
            "blocked": [s["id"] for s in shots if s["blockers"]]}


def compile_matrix(plan: dict, card: dict, logic: dict | None, axes: dict[str, list[str]]) -> dict:
    """Base plan plus every combination of the given slot values; product digests must not move."""
    base = compile_plan(plan, card, logic)
    keys = list(axes)
    variants = [compile_plan(plan, card, logic, dict(zip(keys, combo)))
                for combo in itertools.product(*(axes[k] for k in keys))]
    drift = []
    for variant in variants:
        for shot, ref in zip(variant["shots"], base["shots"]):
            if shot["product_digest"] != ref["product_digest"]:
                drift.append(f"{variant['binding']} {shot['id']}")
    return {"base": base, "variants": variants, "product_block_stable": not drift, "drift": drift}


def resolve(plan_path: Path) -> tuple[dict, dict, dict | None]:
    plan = _load(plan_path)
    base = plan_path.parent
    card = _load(base / plan["product_lock"])
    logic = _load(base / plan["product_logic"]) if plan.get("product_logic") else None
    return plan, card, logic


def render_plan(result: dict) -> str:
    binding = ", ".join(f"{k}={v}" for k, v in result["binding"].items())
    lines = [f"# 替换计划 · {binding}", ""]
    for shot in result["shots"]:
        status = "BLOCKER" if shot["blockers"] else "ready"
        digest = f" · product {shot['product_digest']}" if shot["product_digest"] else ""
        lines += [f"## {shot['id']} · {shot['class']} · {status}{digest}", "", "参考图（按顺序上传）："]
        lines += [f"- {r['slot']} · {r['role']} · {r['ref']} — {r['note']}" for r in shot["references"]]
        lines += ["", "Prompt:", *[f"- {p}" for p in shot["prompt"]]]
        if shot["prerequisites"]:
            lines += ["", "先补场景图：", *[f"- {p}" for p in shot["prerequisites"]]]
        if shot["notes"]:
            lines += ["", "自动调整：", *[f"- {n}" for n in shot["notes"]]]
        if shot["blockers"]:
            lines += ["", "Blockers:", *[f"- {b}" for b in shot["blockers"]]]
        lines += ["", "验收：", *[f"- [ ] {a}" for a in shot["acceptance"]], ""]
    return "\n".join(lines)


def render_matrix(result: dict) -> str:
    lines = ["# 产品锁定替换矩阵", "",
             f"产品块在所有组合中保持一致：{'是' if result['product_block_stable'] else '否'}", "",
             "| 组合 | 镜头数 | 就绪 | 阻塞镜头 |", "| --- | ---: | ---: | --- |"]
    for item in [result["base"], *result["variants"]]:
        binding = ", ".join(f"{k}={v}" for k, v in item["binding"].items())
        ready = len(item["shots"]) - len(item["blocked"])
        lines.append(f"| {binding} | {len(item['shots'])} | {ready} | {', '.join(item['blocked']) or '—'} |")
    if result["drift"]:
        lines += ["", "产品块漂移：", *[f"- {d}" for d in result["drift"]]]
    for item in result["variants"]:
        lines += ["", "---", "", render_plan(item)]
    return "\n".join(lines)


def _pairs(values: list[str]) -> dict[str, str]:
    out = {}
    for value in values:
        key, _, rest = value.partition("=")
        if not key or not rest:
            raise LockError(f"expected slot=value, got {value!r}")
        out[key] = rest
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--bind", action="append", default=[], help="slot=id, e.g. home=SCENE-B or lead=CHAR-C")
    parser.add_argument("--matrix", action="append", default=[], help="slot=id1,id2 to expand into every combination")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, help="write the rendered plan here instead of stdout")
    args = parser.parse_args(argv)
    try:
        plan, card, logic = resolve(args.plan)
        if args.matrix:
            axes = {k: v.split(",") for k, v in _pairs(args.matrix).items()}
            result = compile_matrix(plan, card, logic, axes)
            text = json.dumps(result, ensure_ascii=False, indent=2) if args.json else render_matrix(result)
            ok = result["product_block_stable"]
        else:
            result = compile_plan(plan, card, logic, _pairs(args.bind))
            text = json.dumps(result, ensure_ascii=False, indent=2) if args.json else render_plan(result)
            ok = True
    except (OSError, ValueError, KeyError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
