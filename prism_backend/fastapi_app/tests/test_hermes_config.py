import json
import os
from pathlib import Path

from fastapi_app.agent import hermes_config


def _norm(path: Path | str) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def test_sync_project_skill_includes_nested_references_and_license(monkeypatch, tmp_path):
    source_dir = tmp_path / "docs" / "hermes-skills" / "baoyu-cover-image"
    reference = source_dir / "references" / "palettes" / "warm.md"
    reference.parent.mkdir(parents=True)
    (source_dir / "SKILL.md").write_text("cover entry", encoding="utf-8")
    (source_dir / "LICENSE").write_text("MIT copyright", encoding="utf-8")
    reference.write_text("warm palette", encoding="utf-8")
    (source_dir / "not-installed.py").write_text("raise RuntimeError", encoding="utf-8")
    monkeypatch.setattr(hermes_config, "get_repo_root", lambda: tmp_path)
    monkeypatch.setattr(hermes_config, "get_source_repo_root", lambda: tmp_path)

    hermes_config.sync_prism_project_skill()
    for root in hermes_config._PROJECT_SKILL_ROOTS:
        target = tmp_path / root / "creative" / "baoyu-cover-image"
        assert (target / "SKILL.md").read_text(encoding="utf-8") == "cover entry"
        assert (target / "LICENSE").read_text(encoding="utf-8") == "MIT copyright"
        copied = target / "references" / "palettes" / "warm.md"
        assert copied.read_text(encoding="utf-8") == "warm palette"
        assert not (target / "not-installed.py").exists()
        modified = copied.stat().st_mtime_ns
        hermes_config.sync_prism_project_skill()
        assert copied.stat().st_mtime_ns == modified
    reference.write_text("updated palette", encoding="utf-8")
    hermes_config.sync_prism_project_skill()
    for root in hermes_config._PROJECT_SKILL_ROOTS:
        copied = tmp_path / root / "creative" / "baoyu-cover-image" / "references" / "palettes" / "warm.md"
        assert copied.read_text(encoding="utf-8") == "updated palette"


def test_build_hermes_pythonpath_excludes_backend_root_and_children(monkeypatch, tmp_path):
    hermes_dir = tmp_path / "tools" / "hermes-agent"
    backend_root = tmp_path / "prism_backend"
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
    backend_root = tmp_path / "prism_backend"
    nested_backend_dir = backend_root / "utils"
    python_exe = tmp_path / "prismenv" / "Scripts" / "python.exe"
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
