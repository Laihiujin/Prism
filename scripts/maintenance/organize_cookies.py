"""
Cookie文件整理脚本
- 分析当前cookie文件和数据库记录
- 识别同一账号的多个备份
- 重命名为规范格式: {platform}_{user_id}.json
- 清理重复文件（保留最新）
"""
import sys
from pathlib import Path
from datetime import datetime
import shutil
import json

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "prism_backend"))

from myUtils.cookie_manager import CookieManager
from loguru import logger


def organize_cookies():
    """整理cookie文件"""
    logger.info("=" * 60)
    logger.info("🚀 Cookie文件整理")
    logger.info("=" * 60)

    # 初始化
    cookie_dir = Path(__file__).parent.parent.parent / "prism_backend" / "cookiesFile"
    backup_dir = cookie_dir / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S") / "organize"
    backup_dir.mkdir(parents=True, exist_ok=True)

    manager = CookieManager()

    # 1. 备份所有现有文件
    logger.info("📍 步骤1: 备份所有现有文件...")
    all_cookies = list(cookie_dir.glob("*.json"))
    logger.info(f"   找到 {len(all_cookies)} 个cookie文件")

    for file in all_cookies:
        shutil.copy2(file, backup_dir / file.name)
    logger.info(f"✅ 已备份到: {backup_dir}")
    logger.info("")

    # 2. 从数据库获取所有账号
    logger.info("📍 步骤2: 从数据库获取所有账号...")
    accounts = manager.list_flat_accounts()
    logger.info(f"   数据库中有 {len(accounts)} 个账号记录")
    logger.info("")

    # 3. 分析和整理
    logger.info("📍 步骤3: 分析和整理...")
    logger.info("=" * 60)

    # 按 platform + user_id 分组
    account_groups = {}
    for acc in accounts:
        platform = acc.get('platform', '')
        user_id = acc.get('user_id', '')
        cookie_file = acc.get('cookie_file', '')
        account_id = acc.get('account_id', '')

        if not user_id:
            logger.warning(f"⚠️  账号 {account_id} ({platform}) 没有user_id，跳过")
            continue

        key = f"{platform}_{user_id}"
        if key not in account_groups:
            account_groups[key] = []

        account_groups[key].append({
            'account_id': account_id,
            'platform': platform,
            'user_id': user_id,
            'cookie_file': cookie_file,
            'name': acc.get('name', ''),
        })

    logger.info(f"   识别出 {len(account_groups)} 个唯一账号（按platform+user_id）")
    logger.info("")

    # 4. 处理每个账号组
    duplicates_count = 0
    renamed_count = 0

    for key, group in account_groups.items():
        platform = group[0]['platform']
        user_id = group[0]['user_id']

        if len(group) > 1:
            logger.info(f"🔍 发现重复账号: {platform}_{user_id}")
            logger.info(f"   共 {len(group)} 条记录:")
            for item in group:
                logger.info(f"     - {item['account_id']}: {item['cookie_file']} ({item['name']})")
            duplicates_count += 1
            logger.info("")

        # 保留最新的记录（按account_id倒序，假设ID包含时间戳）
        sorted_group = sorted(group, key=lambda x: x['account_id'], reverse=True)
        keep = sorted_group[0]
        remove = sorted_group[1:]

        # 目标文件名
        target_name = f"{platform}_{user_id}.json"
        old_file = cookie_dir / keep['cookie_file']
        new_file = cookie_dir / target_name

        # 重命名保留的文件
        if old_file.exists():
            if old_file.name != target_name:
                logger.info(f"📝 重命名: {old_file.name} → {target_name}")
                shutil.move(str(old_file), str(new_file))
                renamed_count += 1
            else:
                logger.info(f"✅ 已是规范格式: {target_name}")
        else:
            logger.warning(f"⚠️  文件不存在: {old_file}")

        # 删除重复记录对应的文件
        for item in remove:
            dup_file = cookie_dir / item['cookie_file']
            if dup_file.exists() and dup_file != new_file:
                logger.info(f"🗑️  删除重复文件: {dup_file.name}")
                dup_file.unlink()

        logger.info("")

    # 5. 总结
    logger.info("=" * 60)
    logger.info("📊 整理完成！")
    logger.info("=" * 60)
    logger.info(f"✅ 备份位置: {backup_dir}")
    logger.info(f"✅ 重命名文件数: {renamed_count}")
    logger.info(f"✅ 发现重复账号数: {duplicates_count}")
    logger.info("")
    logger.info("📁 当前Cookie目录结构：")
    logger.info(f"   {cookie_dir}")

    current_files = sorted(cookie_dir.glob("*.json"))
    for f in current_files:
        logger.info(f"   ✅ {f.name}")

    logger.info("")
    logger.info("💡 建议：")
    logger.info("   1. 检查上述文件列表，确认无误")
    logger.info("   2. 如需恢复，备份文件在: " + str(backup_dir))
    logger.info("   3. 后续新账号将自动使用规范命名: {platform}_{user_id}.json")
    logger.info("")


if __name__ == "__main__":
    organize_cookies()
