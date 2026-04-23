from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loguru import logger

from myUtils.browser_context import build_context_options, persistent_browser_manager
from myUtils.fingerprint_policy import get_fingerprint_policy, resolve_proxy
from utils.base_social_media import set_init_script


def _resolve_local_chrome_path() -> str | None:
    def _normalize(candidate: str | Path | None) -> Path | None:
        if not candidate:
            return None
        path = Path(candidate)
        if not path.is_absolute():
            try:
                from config.conf import APP_ROOT

                path = Path(APP_ROOT) / path
            except Exception:
                path = Path(__file__).resolve().parents[2] / path
        return path.resolve()

    def _is_legacy_bundled_chrome(candidate: Path) -> bool:
        normalized = str(candidate).replace("/", "\\").lower()
        return (
            "\\browsers\\chromium\\chromium-" in normalized
            or "\\browsers\\chrome-for-testing\\" in normalized
        )

    roots: list[Path] = []
    try:
        from config.conf import APP_ROOT

        roots.append(Path(APP_ROOT) / "browsers")
    except Exception:
        pass
    roots.append(Path(__file__).resolve().parents[2] / "browsers")

    def _find_matching(patterns: tuple[str, ...]) -> Path | None:
        seen: set[str] = set()
        for root in roots:
            root = root.resolve()
            key = str(root).lower()
            if key in seen or not root.exists():
                continue
            seen.add(key)
            for pattern in patterns:
                matches = sorted(glob.glob(str(root / pattern)))
                if matches:
                    return Path(matches[-1])
        return None

    preferred_chrome_path = _find_matching(("chromium/hibbiki-*/Chrome-bin/chrome.exe",))

    for env_name in ("LOCAL_CHROME_PATH", "LOCAL_CHROME_HEADLESS_SHELL_PATH"):
        candidate = _normalize(os.getenv(env_name))
        if candidate and candidate.is_file():
            if env_name == "LOCAL_CHROME_PATH" and preferred_chrome_path and _is_legacy_bundled_chrome(candidate):
                return str(preferred_chrome_path)
            return str(candidate)

    try:
        from config.conf import LOCAL_CHROME_HEADLESS_SHELL_PATH, LOCAL_CHROME_PATH

        for configured in (LOCAL_CHROME_PATH, LOCAL_CHROME_HEADLESS_SHELL_PATH):
            candidate = _normalize(configured)
            if candidate and candidate.is_file():
                if preferred_chrome_path and _is_legacy_bundled_chrome(candidate):
                    return str(preferred_chrome_path)
                return str(candidate)
    except Exception:
        pass

    patterns = (
        "chromium/hibbiki-*/Chrome-bin/chrome.exe",
        "chromium/chromium-*/chrome-win64/chrome.exe",
        "chromium/chromium-*/chrome-win/chrome.exe",
        "chrome-for-testing/chrome-*/chrome-win64/chrome.exe",
        "chromium_headless_shell-*/chrome-headless-shell-win64/chrome-headless-shell.exe",
    )
    match = _find_matching(patterns)
    return str(match) if match else None


async def create_context_with_policy(
    playwright,
    *,
    platform: str,
    account_id: Optional[str],
    headless: bool,
    storage_state: Any = None,
    force_ephemeral: bool = False,
    base_context_opts: Optional[Dict[str, Any]] = None,
    launch_kwargs: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Any], Any, Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Build a Playwright context with fingerprint policy, proxy, and persistence.
    Returns (browser, context, fingerprint, policy).
    """
    policy = get_fingerprint_policy(account_id, platform)
    apply_fingerprint = bool(policy.get("apply_fingerprint", True)) and bool(account_id)
    apply_stealth = bool(policy.get("apply_stealth", True))
    use_persistent_profile = bool(policy.get("use_persistent_profile", True)) and bool(account_id)
    user_id = None
    if account_id:
        try:
            from myUtils.cookie_manager import cookie_manager

            acc = cookie_manager.get_account_by_id(account_id)
            user_id = acc.get("user_id") if acc else None
        except Exception as e:
            logger.warning(f"[playwright] Failed to load user_id: {e}")
    if use_persistent_profile and not user_id:
        logger.warning("[playwright] Missing user_id; disabling persistent profile")
        use_persistent_profile = False
    if apply_fingerprint and not user_id:
        logger.warning("[playwright] Missing user_id; disabling fingerprint injection")
        apply_fingerprint = False
    if apply_stealth and not user_id:
        logger.warning("[playwright] Missing user_id; disabling stealth init")
        apply_stealth = False
    if force_ephemeral:
        use_persistent_profile = False
    if storage_state is not None and use_persistent_profile:
        use_persistent_profile = False

    launch_opts = {"headless": headless}
    if launch_kwargs:
        launch_opts.update(launch_kwargs)

    if "executable_path" not in launch_opts:
        chrome_path = _resolve_local_chrome_path()
        if chrome_path:
            launch_opts["executable_path"] = chrome_path
            logger.info(f"[playwright] Using local chrome executable: {chrome_path}")
        else:
            logger.debug("[playwright] No local chrome executable detected, using runtime default browser")

    proxy = resolve_proxy(policy)
    if proxy:
        launch_opts["proxy"] = proxy

    context_opts = build_context_options(**(base_context_opts or {}))
    if storage_state is not None:
        context_opts["storage_state"] = storage_state

    fingerprint = None
    if apply_fingerprint:
        try:
            from myUtils.device_fingerprint import device_fingerprint_manager

            fingerprint = device_fingerprint_manager.get_or_create_fingerprint(
                account_id=account_id,
                user_id=user_id,
                platform=platform,
                policy=policy,
            )
            context_opts = device_fingerprint_manager.apply_to_context(fingerprint, context_opts)
        except Exception as e:
            logger.warning(f"[fp] apply failed: {e}")

    if use_persistent_profile:
        profile_root = policy.get("persistent_profile_dir") or "browser_profiles"
        try:
            from config.conf import BASE_DIR

            profile_root_path = Path(profile_root)
            if not profile_root_path.is_absolute():
                profile_root_path = Path(BASE_DIR) / profile_root_path
        except Exception:
            profile_root_path = Path(profile_root)

        custom_manager = persistent_browser_manager
        if profile_root_path:
            try:
                custom_manager = persistent_browser_manager.__class__(profile_root_path)
            except Exception:
                custom_manager = persistent_browser_manager

        user_data_dir = custom_manager.get_user_data_dir(account_id, platform, user_id=user_id)
        context = await playwright.chromium.launch_persistent_context(
            str(user_data_dir), **context_opts, **launch_opts
        )
        try:
            browser = context.browser()
        except Exception:
            browser = None
    else:
        browser = await playwright.chromium.launch(**launch_opts)
        context = await browser.new_context(**context_opts)

    if fingerprint:
        try:
            from myUtils.device_fingerprint import device_fingerprint_manager

            await context.add_init_script(device_fingerprint_manager.get_init_script(fingerprint))
        except Exception as e:
            logger.warning(f"[fp] add init failed: {e}")

    if apply_stealth:
        try:
            await set_init_script(context)
        except Exception as e:
            logger.warning(f"[fp] stealth init failed: {e}")

    if (policy.get("tls_ja3") or {}).get("enabled"):
        logger.warning("[fp] tls_ja3 enabled in policy, but Playwright does not support JA3 spoofing.")

    return browser, context, fingerprint, policy
