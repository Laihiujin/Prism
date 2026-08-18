import asyncio
import os
import shutil
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

def _iter_candidate_roots() -> list[Path]:
    roots: list[Path] = []

    def add_roots(base: Path | None) -> None:
        if not base:
            return
        roots.append(base)
        roots.extend(base.parents)

    add_roots(Path(sys.executable).resolve().parent)
    add_roots(Path(__file__).resolve().parent)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        add_roots(Path(meipass).resolve())

    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        key = str(root).lower()
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def _looks_like_backend_root(candidate: Path) -> bool:
    return (candidate / "fastapi_app").exists()


def _pick_existing(roots: list[Path], name: str) -> Path | None:
    for root in roots:
        candidate = root / name
        if candidate.exists() and _looks_like_backend_root(candidate):
            return candidate
    return None


def resolve_backend_dir() -> Path:
    roots = _iter_candidate_roots()
    backend_dir = _pick_existing(roots, "backend")
    if backend_dir:
        return backend_dir
    syn_backend_dir = _pick_existing(roots, "syn_backend")
    if syn_backend_dir:
        return syn_backend_dir
    return Path(__file__).resolve().parents[2] / "syn_backend"


project_root = resolve_backend_dir()
os.chdir(project_root)
sys.path.insert(0, str(project_root))


def ensure_playwright_driver_node() -> None:
    internal_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent / "_internal")).resolve()
    patchright_node = internal_dir / "patchright" / "driver" / "node.exe"
    playwright_node = internal_dir / "playwright" / "driver" / "node.exe"
    if playwright_node.exists() or not patchright_node.exists():
        return
    playwright_node.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(patchright_node, playwright_node)


ensure_playwright_driver_node()

from playwright_worker.worker import app


def main() -> None:
    host = os.getenv("PLAYWRIGHT_WORKER_HOST", "127.0.0.1")
    port = int(os.getenv("PLAYWRIGHT_WORKER_PORT", "7001"))

    import uvicorn

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        loop="asyncio",
    )


if __name__ == "__main__":
    main()
