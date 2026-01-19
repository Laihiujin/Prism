import asyncio
import json
import os
from pathlib import Path
from typing import Dict, List, Set

from loguru import logger

from myUtils.cookie_manager import cookie_manager

BASE_DIR = Path(__file__).resolve().parents[1]


def _is_dev_repo(base_dir: Path) -> bool:
    env = (os.getenv("SYNAPSE_ENV") or os.getenv("NODE_ENV") or "").strip().lower()
    if env in ("dev", "development", "local"):
        return True
    try:
        return (base_dir.parent / ".git").exists()
    except Exception:
        return False


def _resolve_profiles_dir() -> Path:
    try:
        from fastapi_app.core.config import settings
        return Path(settings.BROWSER_PROFILES_DIR)
    except Exception:
        env_dir = os.getenv("SYNAPSE_DATA_DIR")
        if env_dir:
            return Path(env_dir) / "browser_profiles"
        if _is_dev_repo(BASE_DIR):
            return BASE_DIR / "browser_profiles"
        candidates = []
        appdata = os.getenv("APPDATA")
        local_root = os.getenv("LOCALAPPDATA")
        if appdata:
            candidates.append(Path(appdata) / "SynapseAutomation" / "data" / "browser_profiles")
        if local_root and local_root != appdata:
            candidates.append(Path(local_root) / "SynapseAutomation" / "data" / "browser_profiles")
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return BASE_DIR / "browser_profiles"


def _resolve_fingerprints_dir() -> Path:
    try:
        from fastapi_app.core.config import settings
        return Path(settings.FINGERPRINTS_DIR)
    except Exception:
        env_dir = os.getenv("SYNAPSE_DATA_DIR")
        if env_dir:
            return Path(env_dir) / "fingerprints"
        if _is_dev_repo(BASE_DIR):
            return BASE_DIR / "fingerprints"
        candidates = []
        appdata = os.getenv("APPDATA")
        local_root = os.getenv("LOCALAPPDATA")
        if appdata:
            candidates.append(Path(appdata) / "SynapseAutomation" / "data" / "fingerprints")
        if local_root and local_root != appdata:
            candidates.append(Path(local_root) / "SynapseAutomation" / "data" / "fingerprints")
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return BASE_DIR / "fingerprints"



def _profiles_dir() -> Path:
    return _resolve_profiles_dir()


def _fingerprints_dir() -> Path:
    return _resolve_fingerprints_dir()


def _storage_state_dir() -> Path:
    return cookie_manager.cookies_dir / "storage_state"


def _try_enrich_user_id(account: Dict[str, str]) -> bool:
    """
    尝试为缺少 user_id 的账号补全 user_id。

    Args:
        account: 账号字典，必须包含 platform, account_id, cookie_file

    Returns:
        bool: 补全成功返回 True，失败返回 False
    """
    if account.get("user_id"):
        return True  # 已有 user_id，无需补全

    platform = account.get("platform")
    account_id = account.get("account_id")
    cookie_file = account.get("cookie_file")

    if not platform or not account_id or not cookie_file:
        return False

    try:
        # 方法1: 从文件名推断 user_id
        inferred = cookie_manager._infer_user_id(platform, cookie_file)
        if inferred:
            logger.info(f"[ProfileManager] 从文件名推断 user_id: {platform}_{inferred}")
            cookie_manager.update_account(account_id, user_id=inferred)
            account["user_id"] = inferred
            return True

        # 方法2: 通过 Worker 快速校验补全
        logger.info(f"[ProfileManager] 尝试通过 Worker 补全 user_id: {platform}_{account_id}")
        cookie_manager._enrich_with_fast_validator(platform, cookie_file, account)

        if account.get("user_id"):
            # 补全成功，更新数据库
            cookie_manager.update_account(account_id, user_id=account["user_id"])
            logger.info(f"[ProfileManager] Worker 补全成功: {platform}_{account['user_id']}")
            return True

        logger.warning(f"[ProfileManager] 无法补全 user_id: {platform}_{account_id}")
        return False

    except Exception as exc:
        logger.warning(f"[ProfileManager] 补全 user_id 失败: {platform}_{account_id} ({exc})")
        return False


def _allowed_accounts() -> List[Dict[str, str]]:
    accounts = cookie_manager.list_flat_accounts()
    normalized = []
    for acc in accounts:
        platform = acc.get("platform")
        account_id = acc.get("account_id")
        user_id = acc.get("user_id")
        if platform and account_id:
            normalized.append({
                "platform": str(platform),
                "account_id": str(account_id),
                "user_id": str(user_id) if user_id else None
            })
    return normalized


def _allowed_profile_names() -> Set[str]:
    names = set()
    for a in _allowed_accounts():
        if not a.get("user_id"):
            # 尝试补全 user_id
            if not _try_enrich_user_id(a):
                logger.warning(f"[ProfileManager] Missing user_id for {a['platform']} {a['account_id']}; skip profile")
                continue
        names.add(f"{a['platform']}_{a['user_id']}")
    return names


def cleanup_profiles() -> Dict[str, int]:
    profiles_dir = _profiles_dir()
    profiles_dir.mkdir(parents=True, exist_ok=True)
    allowed = _allowed_profile_names()
    removed = 0
    kept = 0

    for item in profiles_dir.iterdir():
        if not item.is_dir():
            continue
        if item.name in allowed:
            kept += 1
            continue
        try:
            import shutil

            shutil.rmtree(item)
            removed += 1
        except Exception as exc:
            logger.warning(f"[ProfileManager] Failed to remove profile {item}: {exc}")

    return {"kept": kept, "removed": removed}


def ensure_profiles_for_accounts() -> Dict[str, int]:
    profiles_dir = _profiles_dir()
    profiles_dir.mkdir(parents=True, exist_ok=True)
    accounts = _allowed_accounts()
    created = 0
    existing = 0
    for acc in accounts:
        if not acc.get("user_id"):
            # 尝试补全 user_id
            if not _try_enrich_user_id(acc):
                logger.warning(f"[ProfileManager] Missing user_id for {acc['platform']} {acc['account_id']}; skip create")
                continue
        name = f"{acc['platform']}_{acc['user_id']}"
        target = profiles_dir / name
        if target.exists():
            existing += 1
            continue
        try:
            target.mkdir(parents=True, exist_ok=True)
            created += 1
        except Exception as exc:
            logger.warning(f"[ProfileManager] Failed to create profile {target}: {exc}")
    return {"created": created, "existing": existing}


def cleanup_fingerprints() -> Dict[str, int]:
    fingerprints_dir = _fingerprints_dir()
    fingerprints_dir.mkdir(parents=True, exist_ok=True)
    allowed_accounts = _allowed_accounts()
    allowed = set()
    for a in allowed_accounts:
        if not a.get("user_id"):
            # 尝试补全 user_id
            if not _try_enrich_user_id(a):
                logger.warning(f"[ProfileManager] Missing user_id for {a['platform']} {a['account_id']}; skip fingerprint")
                continue
        allowed.add(f"{a['platform']}_{a['user_id']}.json")
    removed = 0
    kept = 0

    for item in fingerprints_dir.iterdir():
        if not item.is_file():
            continue
        if item.name in allowed:
            kept += 1
            continue
        try:
            item.unlink()
            removed += 1
        except Exception as exc:
            logger.warning(f"[ProfileManager] Failed to remove fingerprint {item}: {exc}")

    return {"kept": kept, "removed": removed}


def _resolve_chrome_path() -> str:
    local_path = os.getenv("LOCAL_CHROME_PATH")
    if local_path:
        candidate = Path(local_path)
        if not candidate.is_absolute():
            try:
                from config.conf import APP_ROOT
                candidate = (APP_ROOT / candidate).resolve()
            except Exception:
                candidate = (BASE_DIR.parent / candidate).resolve()
        if candidate.exists():
            return str(candidate)
    try:
        from config.conf import APP_ROOT
        fallback = APP_ROOT / "browsers" / "chromium" / "chromium-1161" / "chrome-win" / "chrome.exe"
    except Exception:
        fallback = BASE_DIR.parent / "browsers" / "chromium" / "chromium-1161" / "chrome-win" / "chrome.exe"
    if fallback.exists():
        return str(fallback)
    return ""


async def _export_state_for_account(profile_dir: Path, platform: str, account_id: str) -> bool:
    chrome_path = _resolve_chrome_path()
    if not chrome_path:
        logger.warning("[ProfileManager] Chrome path not found, skip export")
        return False

    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        logger.warning(f"[ProfileManager] Playwright missing: {exc}")
        return False

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(profile_dir),
            headless=True,
            executable_path=chrome_path,
            args=["--disable-blink-features=AutomationControlled"],
        )
        await context.new_page()
        state = await context.storage_state()
        await context.close()

    output_dir = _storage_state_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{platform}_{account_id}.json"
    output_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def export_profile_storage_states() -> Dict[str, int]:
    profiles_dir = _profiles_dir()
    profiles_dir.mkdir(parents=True, exist_ok=True)
    allowed = _allowed_accounts()
    exported = 0
    failed = 0

    for acc in allowed:
        if not acc.get("user_id"):
            # 尝试补全 user_id
            if not _try_enrich_user_id(acc):
                failed += 1
                logger.warning(f"[ProfileManager] Missing user_id for {acc['platform']} {acc['account_id']}; skip export")
                continue
        profile_name = f"{acc['platform']}_{acc['user_id']}"
        profile_dir = profiles_dir / profile_name
        if not profile_dir.exists():
            failed += 1
            continue
        try:
            if asyncio.run(_export_state_for_account(profile_dir, acc["platform"], acc["user_id"])):
                exported += 1
            else:
                failed += 1
        except Exception as exc:
            logger.warning(f"[ProfileManager] Export failed for {profile_name}: {exc}")
            failed += 1

    return {"exported": exported, "failed": failed}


def repair_missing_user_ids() -> Dict[str, int]:
    """
    手动触发修复所有缺少 user_id 的账号。

    扫描数据库中的所有账号，对缺少 user_id 的账号尝试补全。

    Returns:
        Dict[str, int]: 包含以下统计信息：
            - total: 总账号数
            - missing: 缺少 user_id 的账号数
            - repaired: 成功补全的账号数
            - failed: 补全失败的账号数
    """
    logger.info("[ProfileManager] 开始修复缺少 user_id 的账号...")

    accounts = cookie_manager.list_flat_accounts()
    total = len(accounts)
    missing = 0
    repaired = 0
    failed = 0

    for acc in accounts:
        if not acc.get("user_id"):
            missing += 1
            logger.info(f"[ProfileManager] 发现缺少 user_id 的账号: {acc['platform']}_{acc['account_id']}")

            if _try_enrich_user_id(acc):
                repaired += 1
                logger.info(f"[ProfileManager] ✅ 补全成功: {acc['platform']}_{acc['user_id']}")
            else:
                failed += 1
                logger.warning(f"[ProfileManager] ❌ 补全失败: {acc['platform']}_{acc['account_id']}")

    result = {
        "total": total,
        "missing": missing,
        "repaired": repaired,
        "failed": failed
    }

    logger.info(f"[ProfileManager] 修复完成: {result}")
    return result
