"""
账号数据一致性清理脚本
确保 cookiesFile、fingerprints、browser_profiles 与前端账号数据保持一致
"""
import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Set, List, Dict
import logging
from myUtils.cookie_manager import cookie_manager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 路径配置
BASE_DIR = Path(__file__).parent.parent
FRONTEND_ACCOUNTS_PATH = BASE_DIR / "db" / "frontend_accounts_snapshot.json"
try:
    from fastapi_app.core.config import settings
    COOKIES_DIR = Path(settings.COOKIE_FILES_DIR)
    FINGERPRINTS_DIR = Path(settings.FINGERPRINTS_DIR)
    BROWSER_PROFILES_DIR = Path(settings.BROWSER_PROFILES_DIR)
except Exception:
    COOKIES_DIR = BASE_DIR / "cookiesFile"
    FINGERPRINTS_DIR = BASE_DIR / "fingerprints"
    BROWSER_PROFILES_DIR = BASE_DIR / "browser_profiles"


def load_frontend_accounts() -> Set[str]:
    """
    从前端账号快照中加载活跃账号ID

    Returns:
        Set[str]: 活跃账号ID集合
    """
    try:
        if not FRONTEND_ACCOUNTS_PATH.exists():
            logger.warning(f"前端账号文件不存在: {FRONTEND_ACCOUNTS_PATH}")
            return set()

        with open(FRONTEND_ACCOUNTS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)

        account_ids = {acc.get('account_id') for acc in data.get('accounts', []) if acc.get('account_id')}
        logger.info(f"加载了 {len(account_ids)} 个活跃账号: {account_ids}")
        return account_ids

    except Exception as e:
        logger.error(f"加载前端账号失败: {e}")
        return set()



def build_allowed_identifiers() -> Set[str]:
    """
    Build allowed platform_user_id identifiers aligned with frontend snapshot.
    """
    accounts = cookie_manager.list_flat_accounts()
    snapshot_ids = load_frontend_accounts()
    if snapshot_ids:
        accounts = [a for a in accounts if a.get("account_id") in snapshot_ids]
    allowed = set()
    for acc in accounts:
        user_id = acc.get("user_id")
        if not user_id:
            logger.warning(f"skip account without user_id: {acc.get('platform')} {acc.get('account_id')}")
            continue
        allowed.add(f"{acc.get('platform')}_{user_id}")
    return allowed


def build_account_mappings() -> List[Dict[str, str]]:
    """Build account_id -> user_id mappings for rename normalization."""
    accounts = cookie_manager.list_flat_accounts()
    snapshot_ids = load_frontend_accounts()
    if snapshot_ids:
        accounts = [a for a in accounts if a.get("account_id") in snapshot_ids]
    mappings = []
    for acc in accounts:
        if acc.get("user_id") and acc.get("account_id"):
            mappings.append({
                "platform": str(acc.get("platform")),
                "account_id": str(acc.get("account_id")),
                "user_id": str(acc.get("user_id")),
            })
    return mappings


def _rename_if_needed(old_path: Path, new_path: Path) -> bool:
    if not old_path.exists() or new_path.exists():
        return False
    try:
        old_path.rename(new_path)
        return True
    except Exception:
        return False


def normalize_fingerprints_and_profiles(mappings: List[Dict[str, str]]) -> None:
    """Rename legacy account_id-based files/dirs to platform_user_id."""
    for m in mappings:
        platform = m["platform"]
        account_id = m["account_id"]
        user_id = m["user_id"]

        # cookies
        new_cookie = COOKIES_DIR / f"{platform}_{user_id}.json"
        legacy_cookie = COOKIES_DIR / f"{platform}_account_{account_id}.json"
        legacy_cookie_alt = COOKIES_DIR / f"{platform}_{account_id}.json"
        legacy_cookie_plain = COOKIES_DIR / f"{account_id}.json"
        if (
            _rename_if_needed(legacy_cookie, new_cookie)
            or _rename_if_needed(legacy_cookie_alt, new_cookie)
            or _rename_if_needed(legacy_cookie_plain, new_cookie)
        ):
            logger.info(f"renamed cookie: {new_cookie.name}")

        # fingerprints
        new_fp = FINGERPRINTS_DIR / f"{platform}_{user_id}.json"
        legacy_fp = FINGERPRINTS_DIR / f"{platform}_account_{account_id}.json"
        legacy_fp_alt = FINGERPRINTS_DIR / f"{platform}_{account_id}.json"
        if _rename_if_needed(legacy_fp, new_fp) or _rename_if_needed(legacy_fp_alt, new_fp):
            logger.info(f"renamed fingerprint: {new_fp.name}")

        # browser_profiles
        new_profile = BROWSER_PROFILES_DIR / f"{platform}_{user_id}"
        legacy_profile = BROWSER_PROFILES_DIR / f"{platform}_account_{account_id}"
        legacy_profile_alt = BROWSER_PROFILES_DIR / f"{platform}_{account_id}"
        if _rename_if_needed(legacy_profile, new_profile) or _rename_if_needed(legacy_profile_alt, new_profile):
            logger.info(f"renamed browser profile: {new_profile.name}")


def cleanup_cookies_directory(active_identifiers: Set[str], dry_run: bool = False) -> Dict[str, int]:
    """
    清理 cookiesFile 目录无效文件
    """
    stats = {'total': 0, 'deleted': 0, 'kept': 0}

    allowed = build_allowed_identifiers()
    allowed_files = {f"{name}.json" for name in allowed}

    if not COOKIES_DIR.exists():
        logger.warning(f"Cookies 目录不存在: {COOKIES_DIR}")
        return stats

    logger.info("开始清理 cookiesFile 目录...")

    for file_path in COOKIES_DIR.glob("*.json"):
        stats['total'] += 1
        filename = file_path.name

        if filename in allowed_files:
            stats['kept'] += 1
            logger.info(f"保留: {filename}")
            continue

        stats['deleted'] += 1
        if dry_run:
            logger.info(f"[试运行] 删除 {filename}")
            continue
        try:
            file_path.unlink()
            logger.info(f"删除: {filename}")
        except Exception as e:
            logger.error(f"删除失败 {filename}: {e}")

    return stats


def cleanup_fingerprints_directory(active_identifiers: Set[str], dry_run: bool = False) -> Dict[str, int]:
    """
    清理 fingerprints 目录无效文件
    """
    stats = {'total': 0, 'deleted': 0, 'kept': 0}

    allowed = build_allowed_identifiers()
    allowed_files = {f"{name}.json" for name in allowed}

    if not FINGERPRINTS_DIR.exists():
        logger.warning(f"Fingerprints 目录不存在: {FINGERPRINTS_DIR}")
        return stats

    logger.info("开始清理 fingerprints 目录...")

    for file_path in FINGERPRINTS_DIR.glob("*.json"):
        stats['total'] += 1
        filename = file_path.name

        if filename in allowed_files:
            stats['kept'] += 1
            logger.info(f"保留: {filename}")
            continue

        stats['deleted'] += 1
        if dry_run:
            logger.info(f"[试运行] 删除 {filename}")
            continue
        try:
            file_path.unlink()
            logger.info(f"删除: {filename}")
        except Exception as e:
            logger.error(f"删除失败 {filename}: {e}")

    return stats


def cleanup_browser_profiles_directory(active_identifiers: Set[str], dry_run: bool = False) -> Dict[str, int]:
    """
    清理 browser_profiles 目录无效数据
    """
    stats = {'total': 0, 'deleted': 0, 'kept': 0}

    allowed = build_allowed_identifiers()

    if not BROWSER_PROFILES_DIR.exists():
        logger.warning(f"Browser profiles 目录不存在: {BROWSER_PROFILES_DIR}")
        return stats

    logger.info("开始清理 browser_profiles 目录...")

    for dir_path in BROWSER_PROFILES_DIR.iterdir():
        if not dir_path.is_dir():
            continue

        stats['total'] += 1
        dirname = dir_path.name

        if dirname in ['test_manual', 'default']:
            stats['kept'] += 1
            logger.info(f"保留默认目录: {dirname}")
            continue

        if dirname in allowed:
            stats['kept'] += 1
            logger.info(f"保留: {dirname}")
            continue

        stats['deleted'] += 1
        if dry_run:
            logger.info(f"[试运行] 删除 {dirname}")
            continue
        try:
            shutil.rmtree(dir_path)
            logger.info(f"删除: {dirname}")
        except Exception as e:
            logger.error(f"删除失败 {dirname}: {e}")

    return stats


def cleanup_all_account_data(dry_run: bool = False) -> Dict[str, Dict[str, int]]:
    """
    清理所有账号相关数据,确保与前端账号保持一致

    Args:
        dry_run: 是否为试运行模式（仅显示将要删除的内容）

    Returns:
        Dict[str, Dict[str, int]]: 各目录的清理统计信息
    """
    logger.info("=" * 60)
    logger.info("开始账号数据一致性清理")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"模式: {'试运行 (不会实际删除)' if dry_run else '正式清理'}")
    logger.info("=" * 60)

    # 先做一次命名规范化，避免误删旧命名
    mappings = build_account_mappings()
    if mappings:
        normalize_fingerprints_and_profiles(mappings)

    # 加载活跃账号
    active_identifiers = build_allowed_identifiers()

    if not active_identifiers:
        logger.warning("未找到活跃账号，跳过清理")
        return {}

    # 执行清理
    results = {}

    # 为了支持 dry-run，我们需要临时修改清理函数
    # 暂时通过全局变量传递 dry_run 状态
    import sys
    original_cleanup_cookies = cleanup_cookies_directory
    original_cleanup_fingerprints = cleanup_fingerprints_directory
    original_cleanup_browser = cleanup_browser_profiles_directory

    if dry_run:
        logger.info("\n试运行模式：以下是将要删除的文件（不会实际删除）\n")

    results['cookies'] = cleanup_cookies_directory(active_identifiers, dry_run=dry_run)
    results['fingerprints'] = cleanup_fingerprints_directory(active_identifiers, dry_run=dry_run)
    results['browser_profiles'] = cleanup_browser_profiles_directory(active_identifiers, dry_run=dry_run)

    # 输出统计信息
    logger.info("=" * 60)
    logger.info("清理完成统计:")
    for category, stats in results.items():
        logger.info(f"\n{category}:")
        logger.info(f"  总计: {stats['total']}")
        logger.info(f"  保留: {stats['kept']}")
        logger.info(f"  {'将删除' if dry_run else '已删除'}: {stats['deleted']}")

    total_deleted = sum(s['deleted'] for s in results.values())
    total_kept = sum(s['kept'] for s in results.values())
    logger.info(f"\n总计: 保留 {total_kept} 项, {'将删除' if dry_run else '已删除'} {total_deleted} 项")
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='账号数据一致性清理脚本')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='试运行模式，仅显示将要删除的内容'
    )

    args = parser.parse_args()

    try:
        cleanup_all_account_data(dry_run=args.dry_run)
    except Exception as e:
        logger.error(f"清理过程出错: {e}", exc_info=True)
        exit(1)
