import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

# Base directory: .../SynapseAutomation
BASE_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = BASE_DIR / "syn_backend" / "scripts"


def _safe_path(script_name: str) -> Path:
    """Resolve a script name to an absolute path inside the scripts directory."""
    candidate = (SCRIPTS_DIR / script_name).resolve()
    if not str(candidate).startswith(str(SCRIPTS_DIR.resolve())):
        raise ValueError("Invalid script path")
    if candidate.suffix != ".py":
        raise ValueError("Only .py scripts are allowed")
    if not candidate.exists():
        raise FileNotFoundError(f"Script not found: {script_name}")
    return candidate


def _extract_description(script_path: Path) -> str:
    """Grab the first line/docstring to show in the UI."""
    try:
        text = script_path.read_text(encoding="utf-8")
    except Exception:
        return ""

    stripped = text.strip()
    if stripped.startswith('"""') or stripped.startswith("'''"):
        # Simple docstring extraction
        try:
            doc = stripped.split(stripped[:3], 2)[1]
            first_line = doc.strip().splitlines()[0]
            return first_line.strip()
        except Exception:
            pass

    # Fallback to first comment line
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
        if line:
            # Stop at first non-empty, non-comment line
            break
    return ""


def list_available_scripts() -> List[Dict[str, Any]]:
    """Return metadata for runnable scripts."""
    if not SCRIPTS_DIR.exists():
        return []

    scripts = []
    for path in sorted(SCRIPTS_DIR.glob("*.py")):
        scripts.append(
            {
                "name": path.name,
                "description": _extract_description(path),
                "path": str(path),
            }
        )
    return scripts


def run_script(script_name: str, args: List[str] | None = None) -> Dict[str, Any]:
    """Execute a whitelisted script and return output."""
    args = args or []
    script_path = _safe_path(script_name)

    start = time.time()
    try:
        completed = subprocess.run(
            [sys.executable, str(script_path), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
        duration = round(time.time() - start, 3)
        return {
            "script": script_name,
            "args": args,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-8000:],  # keep response size sane
            "stderr": completed.stderr[-8000:],
            "duration": duration,
        }
    except subprocess.TimeoutExpired as exc:
        duration = round(time.time() - start, 3)
        return {
            "script": script_name,
            "args": args,
            "error": f"Script timed out after {duration}s",
            "duration": duration,
        }
