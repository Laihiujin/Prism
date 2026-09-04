import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi_app.core import runtime
from scripts import prism_runtime


class RuntimeEndpointTests(unittest.TestCase):
    def test_explicit_port_wins_over_runtime_file(self):
        with tempfile.TemporaryDirectory() as directory:
            state_file = Path(directory) / "runtime.json"
            state_file.write_text(json.dumps({"backend_port": 7009}), encoding="utf-8")
            with patch.object(runtime, "RUNTIME_FILE", state_file), patch.dict(
                os.environ, {"PRISM_BACKEND_PORT": "7042"}, clear=True
            ):
                self.assertEqual(runtime.get_backend_url(), "http://127.0.0.1:7042")

    def test_explicit_url_wins(self):
        with patch.dict(os.environ, {"PRISM_BACKEND_URL": "http://127.0.0.1:7055/"}, clear=True):
            self.assertEqual(runtime.get_backend_url(), "http://127.0.0.1:7055")
            self.assertEqual(runtime.get_backend_port(), 7055)

    def test_coordinator_skips_an_occupied_port(self):
        with tempfile.TemporaryDirectory() as directory:
            state_file = Path(directory) / "runtime.json"
            with patch.object(prism_runtime, "RUNTIME_FILE", state_file), patch.object(
                prism_runtime, "port_available", side_effect=lambda _host, port: port != 7000
            ), patch.dict(os.environ, {}, clear=True):
                state = prism_runtime.select_endpoint()
            self.assertEqual(state["backend_port"], 7001)
            self.assertEqual(json.loads(state_file.read_text())["backend_url"], "http://127.0.0.1:7001")

    def test_invalid_explicit_port_is_rejected(self):
        with patch.dict(os.environ, {"PRISM_BACKEND_PORT": "70000"}, clear=True):
            with self.assertRaisesRegex(ValueError, "between 1 and 65535"):
                prism_runtime.select_endpoint()


if __name__ == "__main__":
    unittest.main()
