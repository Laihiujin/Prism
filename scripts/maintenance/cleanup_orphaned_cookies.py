"""
清理孤立的Cookie文件
- 识别目录中存在但数据库中没有记录的文件
- 移动到专用的orphaned备份目录
- 不会删除，只是归档
"""
import sys
from pathlib import Path
from datetime import datetime
import shutil

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "prism_backend"))

from myUtils.cookie_manager import CookieManager
from loguru import logger


def cleanup_orphaned_cookies(dry_run=True):
    """清理孤立cookie文件"""
    logger.info("=" * 60)
    logger.info("🗑️  清理孤立Cookie文件")
    logger.info("=" * 60)

    # 初始化
    cookie_dir = Path(__file__).parent.parent.parent / "prism_backend" / "cookiesFile"
    orphaned_dir = cookie_dir / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S") / "orphaned"

    manager = CookieManager()

    # 1. 获取数据库中的cookie文件
    logger.info("📍 步骤1: 从数据库获取活跃账号...")
    accounts = manager.list_flat_accounts()
    db_cookie_files = {acc['cookie_file'] for acc in accounts}

    logger.info(f"   数据库中有 {len(db_cookie_files)} 个活跃账号:")
    for f in sorted(db_cookie_files):
        logger.info(f"     ✅ {f}")
    logger.info("")

    # 2. 获取目录中所有文件
    logger.info("📍 步骤2: 扫描Cookie目录...")
    all_files = list(cookie_dir.glob("*.json"))
    all_filenames = {f.name for f in all_files}

    logger.info(f"   目录中共有 {len(all_files)} 个文件")
    logger.info("")

    # 3. 找出孤立文件
    logger.info("📍 步骤3: 识别孤立文件...")
    orphan_files = all_filenames - db_cookie_files

    if not orphan_files:
        logger.info("✅ 没有发现孤立文件，目录很干净！")
        return

    logger.info(f"   发现 {len(orphan_files)} 个孤立文件（不在数据库中）:")
    logger.info("")

    # 按平台分组显示
    by_platform = {}
    for fname in orphan_files:
        if fname.startswith('douyin_'):
            platform = 'douyin'
        elif fname.startswith('kuaishou_'):
            platform = 'kuaishou'
        elif fname.startswith('bilibili_'):
            platform = 'bilibili'
        elif fname.startswith('xiaohongshu_'):
            platform = 'xiaohongshu'
        elif fname.startswith('channels_') or fname.startswith('tencent_'):
            platform = 'channels'
        else:
            platform = 'unknown'

        if platform not in by_platform:
            by_platform[platform] = []
        by_platform[platform].append(fname)

    for platform in sorted(by_platform.keys()):
        logger.info(f"   📂 {platform} ({len(by_platform[platform])} 个):")
        for fname in sorted(by_platform[platform])[:5]:
            logger.info(f"      ❌ {fname}")
        if len(by_platform[platform]) > 5:
            logger.info(f"      ... 还有 {len(by_platform[platform]) - 5} 个")

    logger.info("")

    # 4. 移动孤立文件
    if dry_run:
        logger.info("=" * 60)
        logger.info("🔍 DRY RUN 模式（仅预览，不会实际移动文件）")
        logger.info("=" * 60)
        logger.info(f"将会移动 {len(orphan_files)} 个孤立文件到:")
        logger.info(f"  {orphaned_dir}")
        logger.info("")
        logger.info("💡 要实际执行清理，请运行:")
        logger.info("   python scripts/maintenance/cleanup_orphaned_cookies.py --execute")
    else:
        logger.info("=" * 60)
        logger.info("🚀 开始移动孤立文件...")
        logger.info("=" * 60)

        # 创建归档目录
        orphaned_dir.mkdir(parents=True, exist_ok=True)

        moved_count = 0
        for fname in orphan_files:
            src = cookie_dir / fname
            dst = orphaned_dir / fname

            if src.exists():
                shutil.move(str(src), str(dst))
                logger.info(f"  ✅ 已移动: {fname}")
                moved_count += 1

        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ 清理完成！")
        logger.info("=" * 60)
        logger.info(f"✅ 移动文件数: {moved_count}")
        logger.info(f"✅ 归档位置: {orphaned_dir}")
        logger.info("")
        logger.info("📊 当前活跃Cookie文件:")
        remaining = list(cookie_dir.glob("*.json"))
        for f in sorted(remaining):
            logger.info(f"  ✅ {f.name}")
        logger.info("")
        logger.info(f"总计: {len(remaining)} 个活跃文件")
        logger.info("")
        logger.info("💡 如需恢复，孤立文件已保存在归档目录中")


if __name__ == "__main__":
    import sys

    # 检查命令行参数
    execute = "--execute" in sys.argv

    if not execute:
        logger.warning("⚠️  运行在 DRY RUN 模式，不会实际移动文件")
        logger.warning("⚠️  要实际执行，请添加 --execute 参数")
        logger.warning("")

    cleanup_orphaned_cookies(dry_run=not execute)
