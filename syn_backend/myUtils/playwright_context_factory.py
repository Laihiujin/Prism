from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loguru import logger

from myUtils.browser_context import build_context_options, persistent_browser_manager
from myUtils.fingerprint_policy import get_fingerprint_policy, resolve_proxy
from utils.base_social_media import set_init_script


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
    if force_ephemeral:
        use_persistent_profile = False
    if storage_state is not None and use_persistent_profile:
        # storage_state is not supported by launch_persistent_context; fall back to non-persistent
        use_persistent_profile = False

    launch_opts = {"headless": headless}
    if launch_kwargs:
        launch_opts.update(launch_kwargs)

    # 🔧 自动配置 Chrome 可执行文件路径（支持相对路径）
    # 优先使用配置文件中的 LOCAL_CHROME_PATH
    if "executable_path" not in launch_opts:
        try:
            from config.conf import LOCAL_CHROME_PATH, BASE_DIR
            if LOCAL_CHROME_PATH:
                chrome_path = Path(str(LOCAL_CHROME_PATH))

                # 如果是相对路径，从项目根目录解析
                if not chrome_path.is_absolute():
                    chrome_path = Path(BASE_DIR) / chrome_path

                if chrome_path.is_file():
                    launch_opts["executable_path"] = str(chrome_path.resolve())
                    logger.info(f"[playwright] Using LOCAL_CHROME_PATH: {chrome_path}")
                else:
                    logger.warning(f"[playwright] LOCAL_CHROME_PATH not found: {LOCAL_CHROME_PATH}")
            else:
                logger.debug("[playwright] LOCAL_CHROME_PATH not set, using default Chromium")
        except Exception as e:
            logger.warning(f"[playwright] Failed to load LOCAL_CHROME_PATH: {e}")

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
                account_id=account_id, user_id=user_id,
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
        context = await playwright.chromium.launch_persistent_context(str(user_data_dir), **context_opts, **launch_opts)
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
