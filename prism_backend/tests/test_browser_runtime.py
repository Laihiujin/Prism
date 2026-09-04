import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi_app.services.browser_runtime import (
    get_browser_runtime_snapshot,
    get_default_browser_backend,
    resolve_browser_backend,
)
from fastapi_app.services.browser_backend import BrowserBackendManager
from utils.automation_provider import get_automation_runtime_registry


def test_runtime_file_changes_are_visible_without_module_reload():
    with tempfile.TemporaryDirectory() as directory:
        settings_file = Path(directory) / "runtime-settings.json"
        with patch.dict(os.environ, {"PRISM_RUNTIME_SETTINGS_PATH": str(settings_file)}, clear=True):
            settings_file.write_text(json.dumps({"browserBackendDefault": "patchright"}))
            assert get_default_browser_backend() == "patchright"
            settings_file.write_text(json.dumps({"browserBackendDefault": "persona"}))
            assert get_default_browser_backend() == "persona"


def test_runtime_snapshot_exposes_persisted_generation():
    with tempfile.TemporaryDirectory() as directory:
        settings_file = Path(directory) / "runtime-settings.json"
        settings_file.write_text(
            json.dumps({"browserBackendDefault": "persona", "browserBackendGeneration": 7})
        )
        with patch.dict(os.environ, {"PRISM_RUNTIME_SETTINGS_PATH": str(settings_file)}, clear=True):
            assert get_browser_runtime_snapshot() == {"backend": "persona", "generation": 7}


def test_account_binding_wins_over_live_default():
    with patch.dict(os.environ, {"PRISM_BROWSER_BACKEND_DEFAULT": "persona"}, clear=True):
        assert resolve_browser_backend({"browser_backend": "patchright"}) == "patchright"
        assert resolve_browser_backend({}) == "persona"


def test_invalid_runtime_value_falls_back_safely():
    with patch.dict(os.environ, {"PRISM_BROWSER_BACKEND_DEFAULT": "unknown"}, clear=True):
        assert get_default_browser_backend() == "patchright"


def test_provider_manifests_expose_capabilities():
    providers = BrowserBackendManager.describe()
    assert "persistent_context" in providers["patchright"]["capabilities"]
    assert "identity" in providers["persona"]["capabilities"]
    runtimes = get_automation_runtime_registry()
    assert runtimes["patchright"]["installed"] is True
