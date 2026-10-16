"""Regression checks for runtime migration and platform selection (no downloads)."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("provision", ROOT / "scripts/packaging/provision/provision.py")
provision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)


class MicromambaRuntimeTests(unittest.TestCase):
    def test_platform_matrix(self):
        for system, arch, expected in [
            ("Windows", "AMD64", "win-64"), ("Darwin", "arm64", "osx-arm64"),
            ("Darwin", "x86_64", "osx-64"), ("Linux", "aarch64", "linux-aarch64"),
            ("Linux", "x86_64", "linux-64"),
        ]:
            with self.subTest(system=system, arch=arch), patch.object(provision.platform, "system", return_value=system), patch.object(provision.platform, "machine", return_value=arch):
                self.assertEqual(provision.micromamba_platform(), expected)

    @unittest.skipUnless(provision.os.name == "nt", "Windows binary selection")
    def test_windows_does_not_select_unix_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "micromamba").touch()
            with patch.object(provision, "EMBED_MICROMAMBA_DIR", root), patch.object(provision, "micromamba_platform", return_value="win-64"), patch.object(provision.os, "name", "nt"), patch.dict(provision.os.environ, {"PRISM_MICROMAMBA": ""}), patch.object(provision.shutil, "which", return_value=None):
                with self.assertRaises(RuntimeError):
                    provision.resolve_micromamba()

    def test_dry_run_does_not_create_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            env = Path(temp) / "prismenv"
            reqs = Path(temp) / "requirements.txt"
            reqs.write_text("")
            provision.create_env(env, "micromamba", {"channels": ["conda-forge"]}, ["python=3.11"], reqs, dry_run=True)
            self.assertFalse(env.exists())

    def test_legacy_environment_is_not_reused_or_backed_up(self):
        with tempfile.TemporaryDirectory() as temp:
            env = Path(temp) / "prismenv"
            env.mkdir()
            (env / "pyvenv.cfg").write_text("legacy")
            reqs = Path(temp) / "requirements.txt"
            reqs.write_text("")
            with self.assertRaisesRegex(RuntimeError, "micromamba conda"):
                provision.create_env(env, "micromamba", {"channels": []}, [], reqs, force=True)
            self.assertEqual(list(env.parent.glob("prismenv*")), [env])


if __name__ == "__main__":
    unittest.main()
