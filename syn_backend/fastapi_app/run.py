"""
FastAPI Application Startup Script
"""
import sys
import os
import asyncio
from pathlib import Path

# CRITICAL: Ensure Windows ProactorEventLoop for asyncio subprocess support (Playwright needs this)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("[WINDOWS] Set ProactorEventLoopPolicy for Playwright subprocess support")

# IMPORTANT:
# Do NOT force `PLAYWRIGHT_BROWSERS_PATH=0` here.
# Setting it to `0` makes Playwright look for browsers under Python package `.local-browsers`,
# which breaks if those browsers haven't been downloaded.
# Prefer Playwright's default cache location unless the user explicitly sets it.

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add project root to Python path
project_root = Path(__file__).parent.parent

# Remove fastapi_app from sys.path if it was auto-added (it causes import conflicts)
fastapi_app_path = str(Path(__file__).parent)
if fastapi_app_path in sys.path:
    sys.path.remove(fastapi_app_path)

# Add project root (syn_backend) to sys.path FIRST
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add OpenManus-worker to Python path (必须在导入 main.py 之前)
openmanus_path = project_root / "OpenManus-worker"
if openmanus_path.exists() and str(openmanus_path) not in sys.path:
    sys.path.insert(0, str(openmanus_path))
    print(f"[OPENMANUS] Added to sys.path: {openmanus_path}")

if __name__ == "__main__":
    # Debug: Print sys.path to diagnose import issues
    print(f"[DEBUG] Python executable: {sys.executable}")
    print(f"[DEBUG] Current working directory: {os.getcwd()}")
    print(f"[DEBUG] Project root: {project_root}")
    print(f"[DEBUG] sys.path:")
    for p in sys.path[:5]:
        print(f"  - {p}")
    sys.stdout.flush()

    import uvicorn
    from fastapi_app.core.config import settings
    from utils.playwright_bootstrap import ensure_playwright_chromium_installed

    print(f"[START] {settings.PROJECT_NAME} v{settings.VERSION}")
    print(f"[SERVER] http://{settings.HOST}:{settings.PORT}")
    print(f"[API DOCS] http://localhost:{settings.PORT}/api/docs")
    print(f"[REDOC] http://localhost:{settings.PORT}/api/redoc")
    print(f"[OPENAPI] http://localhost:{settings.PORT}/api/openapi.json")

    # Ensure project-local Playwright Chromium is available (required for publish/login automation).
    # Can be disabled by setting PLAYWRIGHT_AUTO_INSTALL=0.
    auto_install = os.getenv("PLAYWRIGHT_AUTO_INSTALL", "1").strip().lower() not in {"0", "false", "no", "off"}
    r = ensure_playwright_chromium_installed(auto_install=auto_install)
    print(f"[PLAYWRIGHT] PLAYWRIGHT_BROWSERS_PATH={r.browsers_path}")
    if not r.installed:
        print(f"[PLAYWRIGHT] Chromium not ready: {r.error}")

    # Limit reload directories to avoid scanning venv/lib64 (broken symlink on Windows)
    reload_dirs = [str(project_root / "fastapi_app")] if settings.DEBUG else None

    # Keep default asyncio loop; on Windows this follows the Proactor policy set above.
    loop_type = "asyncio"

    uvicorn.run(
        "fastapi_app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        reload_dirs=reload_dirs,
        log_level=settings.LOG_LEVEL.lower(),
        loop=loop_type
    )
