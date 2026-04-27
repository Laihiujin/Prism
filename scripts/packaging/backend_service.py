import asyncio
import os
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

from fastapi_app.core.config import settings
from fastapi_app.main import app


def main() -> None:
    import uvicorn

    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        log_level=settings.LOG_LEVEL.lower(),
        loop="asyncio",
    )


if __name__ == "__main__":
    main()
