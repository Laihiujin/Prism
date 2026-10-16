"""Options for background helpers; visible browser windows remain unaffected."""
import subprocess
import sys


def hidden_process_kwargs() -> dict:
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
