from __future__ import annotations

import ast
import json
import os
from pathlib import Path


def _load_writer():
    source_path = Path(__file__).parents[1] / "fastapi_app" / "api" / "v1" / "auth" / "router.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8-sig"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_write_private_json")
    module = ast.Module(body=[function], type_ignores=[])
    namespace = {"Path": Path, "Any": object, "os": os, "tempfile": __import__("tempfile"), "json": json}
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace["_write_private_json"]


def test_private_json_writer_is_atomic_and_owner_only(tmp_path):
    writer = _load_writer()
    target = tmp_path / "account.json"
    writer(target, {"cookies": [{"name": "session", "value": "runtime"}]})

    assert json.loads(target.read_text(encoding="utf-8"))["cookies"][0]["name"] == "session"
    if os.name != "nt":
        assert target.stat().st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob(".account.json.*"))
