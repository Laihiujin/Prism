"""
测试持久化浏览器配置管理功能
"""
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from myUtils.browser_context import persistent_browser_manager
from loguru import logger


def main():
    """测试持久化配置管理"""

    logger.info("=" * 60)
    logger.info("持久化浏览器配置管理测试")
    logger.info("=" * 60)
    logger.info("")

    # 1. 获取总大小和统计信息
    logger.info("[1] 获取总大小和统计信息")
    size_info = persistent_browser_manager.get_total_size()

    logger.info(f"总配置数量: {size_info['profile_count']}")
    logger.info(f"总占用空间: {size_info['total_mb']} MB ({size_info['total_gb']} GB)")
    logger.info("")

    # 2. 列出所有持久化配置
    logger.info("[2] 所有持久化配置列表")
    logger.info("-" * 60)

    profiles = size_info['profiles']
    if not profiles:
        logger.warning("❌ 没有找到任何持久化配置")
    else:
        # 按平台分组
        by_platform = {}
        for profile in profiles:
            platform = profile['platform']
            if platform not in by_platform:
                by_platform[platform] = []
            by_platform[platform].append(profile)

        for platform, platform_profiles in sorted(by_platform.items()):
            logger.info(f"\n平台: {platform}")
            logger.info(f"  配置数量: {len(platform_profiles)}")

            total_size = sum(p['size_mb'] for p in platform_profiles)
            logger.info(f"  总大小: {total_size:.2f} MB")

            for profile in sorted(platform_profiles, key=lambda x: x['size_mb'], reverse=True)[:5]:
                logger.info(f"    - {profile['account_id']}: {profile['size_mb']} MB")
                logger.info(f"      路径: {profile['path']}")

    logger.info("")
    logger.info("-" * 60)

    # 3. 检查重复配置
    logger.info("\n[3] 检查重复配置")
    account_dirs = {}
    for profile in profiles:
        key = f"{profile['platform']}_{profile['account_id']}"
        if key not in account_dirs:
            account_dirs[key] = []
        account_dirs[key].append(profile['path'])

    duplicates = {k: v for k, v in account_dirs.items() if len(v) > 1}
    if duplicates:
        logger.warning(f"⚠️  发现 {len(duplicates)} 个账号有重复配置:")
        for key, paths in duplicates.items():
            logger.warning(f"  {key}:")
            for path in paths:
                logger.warning(f"    - {path}")
    else:
        logger.success("✅ 没有发现重复配置")

    logger.info("")

    # 4. 检查路径问题
    logger.info("[4] 检查路径问题")
    wrong_paths = [p for p in profiles if "prism_backend\\prism_backend" in p['path'] or "prism_backend/prism_backend" in p['path']]
    if wrong_paths:
        logger.warning(f"⚠️  发现 {len(wrong_paths)} 个错误路径配置 (prism_backend/prism_backend):")
        for profile in wrong_paths[:5]:
            logger.warning(f"  - {profile['platform']}_{profile['account_id']}")
            logger.warning(f"    {profile['path']}")
    else:
        logger.success("✅ 没有发现路径问题")

    logger.info("")

    # 5. 统计信息
    logger.info("[5] 按大小统计")
    logger.info("-" * 60)

    # 按大小排序
    sorted_profiles = sorted(profiles, key=lambda x: x['size_mb'], reverse=True)

    logger.info("📊 前10个最大的配置:")
    for i, profile in enumerate(sorted_profiles[:10], 1):
        logger.info(f"  {i}. {profile['platform']}_{profile['account_id']}: {profile['size_mb']} MB")

    logger.info("")

    # 大小分布
    size_ranges = {
        "< 50MB": 0,
        "50-100MB": 0,
        "100-200MB": 0,
        "200-500MB": 0,
        "> 500MB": 0
    }

    for profile in profiles:
        size_mb = profile['size_mb']
        if size_mb < 50:
            size_ranges["< 50MB"] += 1
        elif size_mb < 100:
            size_ranges["50-100MB"] += 1
        elif size_mb < 200:
            size_ranges["100-200MB"] += 1
        elif size_mb < 500:
            size_ranges["200-500MB"] += 1
        else:
            size_ranges["> 500MB"] += 1

    logger.info("📊 大小分布:")
    for range_name, count in size_ranges.items():
        if count > 0:
            logger.info(f"  {range_name}: {count} 个")

    logger.info("")
    logger.info("=" * 60)
    logger.info("测试完成!")
    logger.info("=" * 60)

    # 6. 提供操作建议
    logger.info("")
    logger.info("💡 操作建议:")
    logger.info("")

    if duplicates:
        logger.info("1. 清理重复配置:")
        logger.info("   - 删除 prism_backend/prism_backend/browser_profiles 目录下的重复配置")
        logger.info("")

    if size_info['total_gb'] > 5:
        logger.warning(f"2. 总占用空间较大 ({size_info['total_gb']} GB):")
        logger.info("   - 可以使用 API 清理超过30天未使用的配置")
        logger.info("   - POST /api/v1/system/browser-profiles/cleanup-old")
        logger.info("")

    if wrong_paths:
        logger.info("3. 修复错误路径:")
        logger.info("   - 删除 prism_backend/prism_backend/browser_profiles 目录")
        logger.info("   - 只保留 prism_backend/browser_profiles")
        logger.info("")

    logger.info("📚 API 端点:")
    logger.info("  - GET  /api/v1/system/browser-profiles/list")
    logger.info("  - GET  /api/v1/system/browser-profiles/stats")
    logger.info("  - POST /api/v1/system/browser-profiles/cleanup-old")
    logger.info("  - DELETE /api/v1/system/browser-profiles/{platform}/{account_id}")
    logger.info("")


if __name__ == "__main__":
    main()
