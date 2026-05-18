import json
import os
from pathlib import Path

from fastapi_app.agent import hermes_config


def _norm(path: Path | str) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def test_build_hermes_pythonpath_excludes_backend_root_and_children(monkeypatch, tmp_path):
    hermes_dir = tmp_path / "tools" / "hermes-agent"
    backend_root = tmp_path / "syn_backend"
    nested_backend_dir = backend_root / "utils"
    external_dir = tmp_path / "external"
    base_dir = tmp_path / "base"

    for path in (hermes_dir, nested_backend_dir, external_dir, base_dir):
        path.mkdir(parents=True, exist_ok=True)

    pythonpath = hermes_config.build_hermes_pythonpath(
        hermes_dir,
        base=str(base_dir) + ";" + str(backend_root) + ";" + str(nested_backend_dir) + ";" + str(external_dir),
        exclude=(backend_root,),
    ).split(";")

    normalized = [_norm(path) for path in pythonpath]

    assert normalized[0] == _norm(hermes_dir.resolve())
    assert _norm(base_dir.resolve()) in normalized
    assert _norm(external_dir.resolve()) in normalized
    assert _norm(backend_root.resolve()) not in normalized
    assert _norm(nested_backend_dir.resolve()) not in normalized


def test_get_gateway_platform_status_uses_isolated_subprocess(monkeypatch, tmp_path):
    hermes_dir = tmp_path / "tools" / "hermes-agent"
    backend_root = tmp_path / "syn_backend"
    nested_backend_dir = backend_root / "utils"
    python_exe = tmp_path / "synenv" / "Scripts" / "python.exe"
    extra_dir = tmp_path / "extra"

    for path in (hermes_dir, nested_backend_dir, python_exe.parent, extra_dir):
        path.mkdir(parents=True, exist_ok=True)
    python_exe.write_text("", encoding="utf-8")

    monkeypatch.setenv(
        "PYTHONPATH",
        str(backend_root) + ";" + str(nested_backend_dir) + ";" + str(extra_dir),
    )
    monkeypatch.setattr(hermes_config, "get_hermes_source_path", lambda: hermes_dir)
    monkeypatch.setattr(hermes_config, "get_backend_root", lambda: backend_root)
    monkeypatch.setattr(hermes_config, "get_hermes_python_path", lambda: python_exe)

    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["cwd"] = kwargs["cwd"]
        captured["env"] = kwargs["env"]

        class Result:
            stdout = json.dumps({"platforms": ["discord"]}, ensure_ascii=False)

        return Result()

    monkeypatch.setattr(hermes_config.subprocess, "run", fake_run)

    status = hermes_config.get_gateway_platform_status()
    pythonpath = str(captured["env"]["PYTHONPATH"]).split(";")

    assert status == {"configured": True, "platforms": ["discord"], "reason": ""}
    normalized = [_norm(path) for path in pythonpath]

    assert captured["cwd"] == str(hermes_dir)
    assert normalized[0] == _norm(hermes_dir.resolve())
    assert _norm(extra_dir.resolve()) in normalized
    assert _norm(backend_root.resolve()) not in normalized
    assert _norm(nested_backend_dir.resolve()) not in normalized
