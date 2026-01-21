"""
清理孤立的持久化浏览器配置
以前端数据库中存在的账号为准,删除已不存在的账号的持久化配置
"""
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from myUtils.browser_context import persistent_browser_manager
from myUtils.cookie_manager import cookie_manager
from loguru import logger
import shutil


def main():
    """清理孤立的持久化配置"""

    logger.info("=" * 60)
    logger.info("清理孤立的持久化浏览器配置")
    logger.info("=" * 60)
    logger.info("")

    # 1. 获取所有持久化配置
    logger.info("[1] 扫描持久化配置目录")
    all_profiles = persistent_browser_manager.list_all_profiles()
    logger.info(f"找到 {len(all_profiles)} 个持久化配置")
    logger.info("")

    # 2. 获取前端数据库中的所有账号
    logger.info("[2] 获取前端数据库中的账号")
    db_accounts = cookie_manager.list_flat_accounts()

    # 构建账号ID集合 (去重)
    db_account_ids = set()
    for account in db_accounts:
        db_account_ids.add(account['account_id'])

    logger.info(f"数据库中有 {len(db_account_ids)} 个账号")
    logger.info("")

    # 3. 找出孤立的配置(持久化目录存在但数据库中不存在)
    logger.info("[3] 查找孤立的配置")
    logger.info("-" * 60)

    orphaned_profiles = []
    for profile in all_profiles:
        account_id = profile['account_id']

        # 跳过特殊账号(如 mediacrawler_kuaishou, manual等)
        if account_id.startswith('mediacrawler_') or account_id == 'manual':
            logger.debug(f"跳过特殊账号: {profile['platform']}_{account_id}")
            continue

        # 检查是否在数据库中
        if account_id not in db_account_ids:
            orphaned_profiles.append(profile)
            logger.warning(f"⚠️  孤立配置: {profile['platform']}_{account_id}")
            logger.warning(f"   路径: {profile['path']}")
            logger.warning(f"   大小: {profile['size_mb']} MB")

    logger.info("-" * 60)
    logger.info("")

    if not orphaned_profiles:
        logger.success("✅ 没有发现孤立的配置!")
        return

    # 4. 统计信息
    total_size_mb = sum(p['size_mb'] for p in orphaned_profiles)
    total_size_gb = round(total_size_mb / 1024, 2)

    logger.info("=" * 60)
    logger.info(f"发现 {len(orphaned_profiles)} 个孤立配置")
    logger.info(f"总大小: {total_size_mb:.2f} MB ({total_size_gb} GB)")
    logger.info("=" * 60)
    logger.info("")

    # 按平台分组显示
    by_platform = {}
    for profile in orphaned_profiles:
        platform = profile['platform']
        if platform not in by_platform:
            by_platform[platform] = []
        by_platform[platform].append(profile)

    for platform, profiles in sorted(by_platform.items()):
        logger.info(f"\n平台: {platform}")
        logger.info(f"  数量: {len(profiles)}")
        platform_size = sum(p['size_mb'] for p in profiles)
        logger.info(f"  大小: {platform_size:.2f} MB")
        for profile in profiles:
            logger.info(f"    - {profile['account_id']}: {profile['size_mb']} MB")

    logger.info("")
    logger.info("=" * 60)

    # 5. 询问是否删除
    logger.warning("⚠️  警告: 此操作将永久删除这些配置,无法恢复!")
    logger.info("")

    response = input("是否删除这些孤立的配置? (yes/no): ").strip().lower()

    if response not in ['yes', 'y']:
        logger.info("❌ 操作已取消")
        return

    # 6. 执行删除
    logger.info("")
    logger.info("[4] 删除孤立的配置")
    logger.info("-" * 60)

    deleted_count = 0
    failed_count = 0

    for profile in orphaned_profiles:
        profile_path = Path(profile['path'])

        try:
            if profile_path.exists():
                shutil.rmtree(profile_path)
                deleted_count += 1
                logger.success(f"✅ 已删除: {profile['platform']}_{profile['account_id']}")
            else:
                logger.warning(f"⚠️  路径不存在: {profile_path}")
        except Exception as e:
            failed_count += 1
            logger.error(f"❌ 删除失败: {profile['platform']}_{profile['account_id']}")
            logger.error(f"   错误: {e}")

    logger.info("-" * 60)
    logger.info("")

    # 7. 总结
    logger.info("=" * 60)
    logger.info("清理完成!")
    logger.info("=" * 60)
    logger.success(f"✅ 成功删除: {deleted_count} 个")
    if failed_count > 0:
        logger.error(f"❌ 删除失败: {failed_count} 个")
    logger.info(f"💾 释放空间: {total_size_mb:.2f} MB ({total_size_gb} GB)")
    logger.info("")


if __name__ == "__main__":
    main()
