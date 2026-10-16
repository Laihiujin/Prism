"""Verify the packaged interpreter after moving it to a clean install directory."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("stage_python_runtime", ROOT / "scripts/packaging/stage_python_runtime.py")
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


@unittest.skipUnless(os.name == "nt", "Windows runtime layout")
class PackagedRuntimeTests(unittest.TestCase):
    def test_batch_interpreter_discovery_handles_windows_install_paths(self):
        source = (ROOT / 'scripts/packaging/build-package.bat').read_text(encoding='utf-8')
        routine = source[source.rindex('\n:ResolveBuildPython\n') + 1:]
        with tempfile.TemporaryDirectory(prefix='prism batch ') as directory:
            script = Path(directory) / 'resolver.cmd'
            script.write_text('@echo off\nsetlocal enabledelayedexpansion\ncall :ResolveBuildPython\n'
                              'if errorlevel 1 exit /b 1\necho RESOLVED=!BUILD_PYTHON!\nexit /b 0\n'
                              + routine, encoding='utf-8')
            env = dict(os.environ)
            env.pop('PRISM_BUILD_PYTHON', None)
            result = subprocess.run(['cmd', '/d', '/c', str(script)], env=env, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b'RESOLVED=', result.stdout)

    def test_interpreter_stays_inside_package_after_install_location_changes(self):
        python = os.environ.get("PRISM_TEST_BUILD_PYTHON") or shutil.which("python")
        with tempfile.TemporaryDirectory(prefix="prism runtime ") as directory:
            build = Path(directory) / "build machine"
            env = build / "prismenv"
            subprocess.run([python, "-m", "venv", "--without-pip", str(env)], check=True)
            stage.stage_runtime(env)
            installed = Path(directory) / "installed application"
            build.rename(installed)
            # Exercise the actual Electron startup method without launching services.
            script = r'''
const fs = require('fs'), path = require('path');
const source = fs.readFileSync(process.argv[1], 'utf8');
const start = source.indexOf('  ensurePrismenvHome() {');
const method = source.slice(start, source.indexOf('\n  getRuntimeManifest()', start));
const app = new Function('fs', 'path', 'log', 'return ({' + method + '});')(fs, path, console);
app.getResourcesRoot = () => process.argv[2];
app.ensurePrismenvHome();
app.ensurePrismenvHome();
'''
            subprocess.run(["node", "-e", script, str(ROOT / "desktop-electron/src/main/index.js"), str(installed)], check=True)
            child_env = dict(os.environ)
            for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
                child_env.pop(key, None)
            subprocess.run([str(installed / "prismenv/Scripts/python.exe"), "-I", "-c",
                            "import encodings,ssl,sqlite3,zlib,sys,pathlib; "
                            "assert pathlib.Path(sys.base_prefix).resolve() == pathlib.Path(sys.prefix,'_python').resolve(); "
                            "assert 'installed application' in sys.base_prefix"],
                           check=True, env=child_env)
