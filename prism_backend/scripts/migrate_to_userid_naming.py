"""
迁移脚本：将 fingerprints 和 browser_profiles 的命名从 account_id 统一为 user_id

旧格式：
- fingerprints: account_{account_id}_{platform}.json
- browser_profiles: {platform}_account_{account_id}

新格式（与 cookiesFile 一致）：
- fingerprints: {platform}_{user_id}.json
- browser_profiles: {platform}_{user_id}

确保账号唯一性，避免同一账号多个 account_id 的问题
"""

import sys
import io
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

# 设置 stdout 编码为 UTF-8（解决 Windows GBK 编码问题）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加父目录到 Python 路径
sys_path = Path(__file__).resolve().parents[1]
if str(sys_path) not in sys.path:
    sys.path.insert(0, str(sys_path))

from myUtils.cookie_manager import cookie_manager

DB_PATH = cookie_manager.db_path
try:
    from fastapi_app.core.config import settings
    FINGERPRINTS_DIR = Path(settings.FINGERPRINTS_DIR)
    BROWSER_PROFILES_DIR = Path(settings.BROWSER_PROFILES_DIR)
except Exception:
    from config.conf import BASE_DIR
    FINGERPRINTS_DIR = Path(BASE_DIR) / "fingerprints"
    BROWSER_PROFILES_DIR = Path(BASE_DIR) / "browser_profiles"


def get_account_mappings() -> List[Dict[str, str]]:
    """
    从数据库中获取 account_id -> user_id 的映射关系

    Returns:
        List[Dict]: 包含 account_id, platform, user_id 的列表
    """
    mappings = []

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT account_id, platform, user_id FROM cookie_accounts WHERE user_id IS NOT NULL AND user_id != ''"
        )
        rows = cursor.fetchall()

        for row in rows:
            mappings.append({
                "account_id": row["account_id"],
                "platform": row["platform"],
                "user_id": row["user_id"]
            })

    print(f"✅ 从数据库获取到 {len(mappings)} 个账号映射关系")
    return mappings


def migrate_fingerprints(mappings: List[Dict[str, str]]) -> Dict[str, int]:
    """
    迁移 fingerprints 文件命名

    旧格式: account_{account_id}_{platform}.json
    新格式: {platform}_{user_id}.json
    """
    stats = {"renamed": 0, "skipped": 0, "errors": 0}

    if not FINGERPRINTS_DIR.exists():
        print(f"⚠️ Fingerprints 目录不存在: {FINGERPRINTS_DIR}")
        return stats

    print(f"\n📁 开始迁移 Fingerprints 文件...")

    for mapping in mappings:
        account_id = mapping["account_id"]
        platform = mapping["platform"]
        user_id = mapping["user_id"]

        # 旧文件名格式 1: account_{account_id}_{platform}.json
        # 旧文件名格式 2: {platform}_{account_id}.json
        old_filename_1 = f"{account_id}_{platform}.json"
        old_filename_2 = f"{platform}_{account_id}.json"
        
        old_path_1 = FINGERPRINTS_DIR / old_filename_1
        old_path_2 = FINGERPRINTS_DIR / old_filename_2

        old_path = None
        old_filename = None
        if old_path_1.exists():
            old_path = old_path_1
            old_filename = old_filename_1
        elif old_path_2.exists():
            old_path = old_path_2
            old_filename = old_filename_2

        # 新文件名格式
        new_filename = f"{platform}_{user_id}.json"
        new_path = FINGERPRINTS_DIR / new_filename

        if not old_path:
            # 旧文件不存在，跳过
            stats["skipped"] += 1
            continue

        if new_path.exists() and new_path != old_path:
            # 新文件已存在（可能是之前迁移过的），跳过
            print(f"⚠️ 目标文件已存在，跳过: {new_filename}")
            stats["skipped"] += 1
            continue

        try:
            # 重命名文件
            old_path.rename(new_path)
            print(f"✅ 重命名: {old_filename} -> {new_filename}")
            stats["renamed"] += 1
        except Exception as e:
            print(f"❌ 重命名失败: {old_filename} -> {new_filename}, 错误: {e}")
            stats["errors"] += 1

    return stats


def migrate_browser_profiles(mappings: List[Dict[str, str]]) -> Dict[str, int]:
    """
    迁移 browser_profiles 目录命名

    旧格式: {platform}_account_{account_id}
    新格式: {platform}_{user_id}
    """
    stats = {"renamed": 0, "skipped": 0, "errors": 0}

    if not BROWSER_PROFILES_DIR.exists():
        print(f"⚠️ Browser Profiles 目录不存在: {BROWSER_PROFILES_DIR}")
        return stats

    print(f"\n📁 开始迁移 Browser Profiles 目录...")

    for mapping in mappings:
        account_id = mapping["account_id"]
        platform = mapping["platform"]
        user_id = mapping["user_id"]

        # 旧目录名格式：{platform}_account_{数字部分}
        # account_id 的格式是 "account_1767686579461"，需要提取数字部分
        numeric_part = account_id.replace('account_', '')
        old_dirname = f"{platform}_account_{numeric_part}"
        old_path = BROWSER_PROFILES_DIR / old_dirname

        # 新目录名格式
        new_dirname = f"{platform}_{user_id}"
        new_path = BROWSER_PROFILES_DIR / new_dirname

        if not old_path.exists():
            # 旧目录不存在，跳过
            stats["skipped"] += 1
            continue

        if new_path.exists() and new_path != old_path:
            # 新目录已存在（可能是之前迁移过的），跳过
            print(f"⚠️ 目标目录已存在，跳过: {new_dirname}")
            stats["skipped"] += 1
            continue

        try:
            # 重命名目录
            old_path.rename(new_path)
            print(f"✅ 重命名: {old_dirname} -> {new_dirname}")
            stats["renamed"] += 1
        except Exception as e:
            print(f"❌ 重命名失败: {old_dirname} -> {new_dirname}, 错误: {e}")
            stats["errors"] += 1

    return stats


def cleanup_orphaned_files():
    """
    清理孤立的旧格式文件（没有对应 user_id 的账号）
    """
    print(f"\n🧹 检查孤立的旧格式文件...")

    # 获取所有有效的 account_id
    valid_account_ids = set()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT account_id FROM cookie_accounts")
        valid_account_ids = {row[0] for row in cursor.fetchall()}

    orphaned_count = 0

    # 检查 fingerprints
    if FINGERPRINTS_DIR.exists():
        for file_path in FINGERPRINTS_DIR.glob("account_*_*.json"):
            # 提取 account_id (格式: account_{account_id}_{platform}.json)
            # account_id 包含 "account_" 前缀
            parts = file_path.stem.split('_', 2)  # 最多分割2次
            if len(parts) >= 3 and parts[0] == 'account':
                account_id = f"account_{parts[1]}"  # 重新拼接 account_id
                if account_id not in valid_account_ids:
                    print(f"⚠️ 发现孤立文件: {file_path.name} (account_id={account_id} 不存在)")
                    orphaned_count += 1

    # 检查 browser_profiles
    if BROWSER_PROFILES_DIR.exists():
        for dir_path in BROWSER_PROFILES_DIR.glob("*_account_*"):
            # 提取 account_id (格式: {platform}_account_{account_id})
            # account_id 包含 "account_" 前缀
            parts = dir_path.name.split('_account_')
            if len(parts) == 2:
                account_id = f"account_{parts[1]}"  # 重新拼接 account_id
                if account_id not in valid_account_ids:
                    print(f"⚠️ 发现孤立目录: {dir_path.name} (account_id={account_id} 不存在)")
                    orphaned_count += 1

    if orphaned_count > 0:
        print(f"\n⚠️ 发现 {orphaned_count} 个孤立文件/目录，可以手动清理")
    else:
        print(f"\n✅ 没有发现孤立文件")


def main():
    """
    主函数：执行迁移流程
    """
    print("=" * 60)
    print("开始迁移 Fingerprints 和 Browser Profiles 命名格式")
    print("=" * 60)

    # 1. 获取账号映射关系
    try:
        mappings = get_account_mappings()
        if not mappings:
            print("⚠️ 没有找到需要迁移的账号（user_id 为空）")
            return
    except Exception as e:
        print(f"❌ 获取账号映射失败: {e}")
        return

    # 2. 迁移 fingerprints
    fp_stats = migrate_fingerprints(mappings)
    print(f"\n📊 Fingerprints 迁移统计:")
    print(f"   - 重命名: {fp_stats['renamed']}")
    print(f"   - 跳过: {fp_stats['skipped']}")
    print(f"   - 错误: {fp_stats['errors']}")

    # 3. 迁移 browser_profiles
    bp_stats = migrate_browser_profiles(mappings)
    print(f"\n📊 Browser Profiles 迁移统计:")
    print(f"   - 重命名: {bp_stats['renamed']}")
    print(f"   - 跳过: {bp_stats['skipped']}")
    print(f"   - 错误: {bp_stats['errors']}")

    # 4. 清理孤立文件
    cleanup_orphaned_files()

    # 5. 总结
    total_renamed = fp_stats['renamed'] + bp_stats['renamed']
    total_errors = fp_stats['errors'] + bp_stats['errors']

    print("\n" + "=" * 60)
    if total_errors > 0:
        print(f"⚠️ 迁移完成，但有 {total_errors} 个错误")
    else:
        print(f"✅ 迁移完成！共重命名 {total_renamed} 个文件/目录")
    print("=" * 60)


if __name__ == "__main__":
    main()
