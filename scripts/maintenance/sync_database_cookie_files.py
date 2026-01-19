"""
同步数据库中的cookie_file字段
- 将数据库中的旧文件名更新为新的规范格式
- {account_id}.json -> {platform}_{user_id}.json
"""
import sys
from pathlib import Path
import sqlite3

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "syn_backend"))

from myUtils.cookie_manager import CookieManager
from loguru import logger


def sync_database_cookie_files():
    """同步数据库cookie_file字段"""
    logger.info("=" * 60)
    logger.info("🔄 同步数据库Cookie文件名")
    logger.info("=" * 60)

    manager = CookieManager()
    db_path = manager.db_path

    # 获取所有账号
    accounts = manager.list_flat_accounts()
    logger.info(f"📍 数据库中有 {len(accounts)} 个账号")
    logger.info("")

    updated_count = 0

    for acc in accounts:
        account_id = acc['account_id']
        platform = acc['platform']
        user_id = acc['user_id']
        old_cookie_file = acc['cookie_file']

        if not user_id:
            logger.warning(f"⚠️  账号 {account_id} ({platform}) 没有user_id，跳过")
            continue

        # 计算新的规范文件名
        new_cookie_file = f"{platform}_{user_id}.json"

        # 如果已经是规范格式，跳过
        if old_cookie_file == new_cookie_file:
            logger.info(f"✅ 已是规范格式: {old_cookie_file}")
            continue

        # 检查新文件是否存在
        cookie_dir = Path(__file__).parent.parent.parent / "syn_backend" / "cookiesFile"
        new_file_path = cookie_dir / new_cookie_file
        old_file_path = cookie_dir / old_cookie_file

        if not new_file_path.exists() and not old_file_path.exists():
            logger.warning(f"⚠️  文件不存在: {new_cookie_file} 和 {old_cookie_file}")
            continue

        # 如果新文件存在，更新数据库
        if new_file_path.exists():
            logger.info(f"📝 更新数据库: {old_cookie_file} -> {new_cookie_file}")

            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "UPDATE cookie_accounts SET cookie_file = ? WHERE account_id = ?",
                    (new_cookie_file, account_id)
                )

            updated_count += 1

        # 如果只有旧文件，重命名旧文件
        elif old_file_path.exists():
            import shutil
            logger.info(f"📝 重命名文件: {old_cookie_file} -> {new_cookie_file}")
            shutil.move(str(old_file_path), str(new_file_path))

            logger.info(f"📝 更新数据库: {old_cookie_file} -> {new_cookie_file}")
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "UPDATE cookie_accounts SET cookie_file = ? WHERE account_id = ?",
                    (new_cookie_file, account_id)
                )

            updated_count += 1

    logger.info("")
    logger.info("=" * 60)
    logger.info("✅ 同步完成！")
    logger.info("=" * 60)
    logger.info(f"✅ 更新账号数: {updated_count}")
    logger.info("")

    # 显示更新后的账号
    logger.info("📊 更新后的账号列表:")
    accounts = manager.list_flat_accounts()
    for acc in accounts:
        logger.info(f"  ✅ {acc['platform']:12} | {acc['cookie_file']:40} | {acc['name']}")


if __name__ == "__main__":
    sync_database_cookie_files()
