from __future__ import annotations

import os
import sys
import time
import glob
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlaywrightBootstrapResult:
    browsers_path: str
    chromium_executable: str | None
    installed: bool
    install_ran: bool
    error: str | None


def _default_browsers_dir() -> Path:
    # 统一使用项目根目录的 browsers 目录（不包含 chromium 子目录）
    # Electron 会设置 PLAYWRIGHT_BROWSERS_PATH，这里只是开发环境的默认值
    # Default to repo-root browsers directory.
    syn_backend_dir = Path(__file__).resolve().parents[1]
    repo_root = syn_backend_dir.parent
    return repo_root / "browsers"


def _chromium_glob_patterns(browsers_dir: Path) -> list[str]:
    # browsers_dir 现在指向 browsers 根目录，需要在 chromium 子目录中查找
    chromium_dir = browsers_dir / "chromium"
    if sys.platform == "win32":
        return [
            str(chromium_dir / "chromium-*" / "chrome-win" / "chrome.exe"),
            str(chromium_dir / "chromium-*" / "chrome-win64" / "chrome.exe"),
        ]
    if sys.platform == "darwin":
        return [str(chromium_dir / "chromium-*" / "chrome-mac" / "Chromium.app" / "Contents" / "MacOS" / "Chromium")]
    return [str(chromium_dir / "chromium-*" / "chrome-linux" / "chrome")]


def _find_chromium_executable(browsers_path: str | None) -> str | None:
    if not browsers_path:
        return None
    try:
        browsers_dir = Path(browsers_path)
    except Exception:
        return None
    for pattern in _chromium_glob_patterns(browsers_dir):
        matches = glob.glob(pattern)
        if matches:
            matches = sorted(matches)
            exe = matches[-1]
            if Path(exe).exists():
                return exe
    return None


def _expected_chromium_executable_via_playwright() -> str | None:
    """
    Ask the installed Playwright package what Chromium executable path it expects.

    This avoids a common pitfall: older Chromium revisions may exist in PLAYWRIGHT_BROWSERS_PATH,
    but Playwright requires an exact, version-pinned revision (e.g. chromium-1200). In that case,
    "any chromium exists" is not enough, and Playwright will still error and ask for `playwright install`.
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            return str(p.chromium.executable_path)
    except Exception:
        return None


def _acquire_lock(lock_path: Path, timeout_s: int = 300) -> bool:
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(f"pid={os.getpid()}\n")
            return True
        except FileExistsError:
            time.sleep(0.4)
        except Exception:
            time.sleep(0.4)
    return False


def _release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink(missing_ok=True)  # type: ignore[arg-type]
    except Exception:
        pass


def ensure_playwright_chromium_installed(
    *,
    browsers_dir: str | None = None,
    auto_install: bool = True,
    timeout_s: int = 600,
) -> PlaywrightBootstrapResult:
    """
    Make Playwright's Chromium available in a project-local directory.

    Key goals:
    - Do not rely on any external/system browser.
    - Use a deterministic on-disk path that can be bundled into an exe distribution.
    - Auto-run `python -m playwright install chromium` on first run.
    """
    install_ran = False
    installed = False
    error: str | None = None

    repo_root = Path(__file__).resolve().parents[1].parent
    target_dir = Path(browsers_dir) if browsers_dir else _default_browsers_dir()
    if not target_dir.is_absolute():
        target_dir = (repo_root / target_dir).resolve()

    env_browsers = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
    if env_browsers is not None and env_browsers.strip():
        env_candidate = Path(env_browsers.strip())
        if not env_candidate.is_absolute():
            env_candidate = (repo_root / env_candidate).resolve()
        else:
            env_candidate = env_candidate.resolve()
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(env_candidate)
        target_dir = env_candidate
    else:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)

    # If a local Chromium executable is provided, trust it and skip Playwright download.
    local_chrome = os.getenv("LOCAL_CHROME_PATH")
    if local_chrome:
        chrome_path = Path(local_chrome)
        if not chrome_path.is_absolute():
            chrome_path = Path(__file__).resolve().parents[1].parent / chrome_path
        if chrome_path.exists():
            return PlaywrightBootstrapResult(
                browsers_path=os.environ["PLAYWRIGHT_BROWSERS_PATH"],
                chromium_executable=str(chrome_path),
                installed=True,
                install_ran=False,
                error=None,
            )

    expected_exe = _expected_chromium_executable_via_playwright()
    if expected_exe and Path(expected_exe).exists():
        return PlaywrightBootstrapResult(
            browsers_path=os.environ["PLAYWRIGHT_BROWSERS_PATH"],
            chromium_executable=expected_exe,
            installed=True,
            install_ran=False,
            error=None,
        )

    # Fallback: best-effort find "some" chromium under the browsers dir.
    chromium_exe = _find_chromium_executable(os.environ.get("PLAYWRIGHT_BROWSERS_PATH"))
    if chromium_exe:
        return PlaywrightBootstrapResult(
            browsers_path=os.environ["PLAYWRIGHT_BROWSERS_PATH"],
            chromium_executable=chromium_exe,
            installed=True,
            install_ran=False,
            error=None,
        )

    if not auto_install:
        return PlaywrightBootstrapResult(
            browsers_path=os.environ["PLAYWRIGHT_BROWSERS_PATH"],
            chromium_executable=None,
            installed=False,
            install_ran=False,
            error="chromium_not_installed",
        )

    lock_path = target_dir / ".install.lock"
    got_lock = _acquire_lock(lock_path, timeout_s=120)
    try:
        # If another process is installing, just wait for the exe to appear.
        expected_exe = _expected_chromium_executable_via_playwright()
        if expected_exe and Path(expected_exe).exists():
            return PlaywrightBootstrapResult(
                browsers_path=os.environ["PLAYWRIGHT_BROWSERS_PATH"],
                chromium_executable=expected_exe,
                installed=True,
                install_ran=False,
                error=None,
            )

        if not got_lock:
            # Wait (bounded) for other installer to finish.
            start = time.monotonic()
            while time.monotonic() - start < timeout_s:
                expected_exe = _expected_chromium_executable_via_playwright()
                if expected_exe and Path(expected_exe).exists():
                    return PlaywrightBootstrapResult(
                        browsers_path=os.environ["PLAYWRIGHT_BROWSERS_PATH"],
                        chromium_executable=expected_exe,
                        installed=True,
                        install_ran=False,
                        error=None,
                    )
                time.sleep(0.6)
            return PlaywrightBootstrapResult(
                browsers_path=os.environ["PLAYWRIGHT_BROWSERS_PATH"],
                chromium_executable=None,
                installed=False,
                install_ran=False,
                error="install_lock_timeout",
            )

        # Run installer in this process.
        cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
        install_ran = True
        try:
            subprocess.run(cmd, check=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            error = "playwright_install_timeout"
        except subprocess.CalledProcessError as e:
            error = f"playwright_install_failed:{e.returncode}"
        except Exception as e:
            error = f"playwright_install_error:{type(e).__name__}"

        expected_exe = _expected_chromium_executable_via_playwright()
        chromium_exe = None
        if expected_exe and Path(expected_exe).exists():
            chromium_exe = expected_exe
        else:
            chromium_exe = _find_chromium_executable(os.environ.get("PLAYWRIGHT_BROWSERS_PATH"))
        installed = chromium_exe is not None
        if not installed and error is None:
            error = "chromium_not_found_after_install"

        return PlaywrightBootstrapResult(
            browsers_path=os.environ["PLAYWRIGHT_BROWSERS_PATH"],
            chromium_executable=chromium_exe,
            installed=installed,
            install_ran=install_ran,
            error=error,
        )
    finally:
        if got_lock:
            _release_lock(lock_path)
