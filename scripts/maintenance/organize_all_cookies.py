"""
Cookie文件完整整理脚本（增强版）
- 处理数据库中有记录的账号
- 处理没有数据库记录的孤立cookie文件
- 从cookie文件中提取user_id并重命名
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


def extract_user_id_from_cookie_file(cookie_file: Path, platform: str) -> str:
    """从cookie文件中提取user_id"""
    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 1. 优先从user_info中提取
        if isinstance(data, dict):
            user_info = data.get('user_info', {})
            if user_info and user_info.get('user_id'):
                return str(user_info['user_id'])

        # 2. 从cookies中提取（平台特定）
        cookies = data.get('cookies', []) if isinstance(data, dict) else data

        platform_id_map = {
            'kuaishou': ['userId', 'bUserId'],
            'channels': ['wxuin', 'uin'],
            'bilibili': ['DedeUserID', 'DedeUserID__ckMd5'],
        }

        if platform in platform_id_map:
            for cookie in cookies:
                if isinstance(cookie, dict):
                    for key in platform_id_map[platform]:
                        if cookie.get('name') == key and cookie.get('value'):
                            return str(cookie['value'])

        return None
    except Exception as e:
        logger.warning(f"提取user_id失败: {cookie_file.name} - {e}")
        return None


def detect_platform_from_filename(filename: str) -> str:
    """从文件名推测平台"""
    platforms = ['douyin', 'kuaishou', 'bilibili', 'xiaohongshu', 'channels', 'tencent']
    for platform in platforms:
        if filename.startswith(platform):
            # tencent -> channels
            if platform == 'tencent':
                return 'channels'
            return platform
    return None


def organize_all_cookies():
    """完整整理所有cookie文件"""
    logger.info("=" * 60)
    logger.info("🚀 Cookie文件完整整理（增强版）")
    logger.info("=" * 60)

    # 初始化
    cookie_dir = Path(__file__).parent.parent.parent / "prism_backend" / "cookiesFile"
    backup_dir = cookie_dir / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S") / "organize_full"
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
    logger.info("📍 步骤2: 从数据库获取账号...")
    db_accounts = manager.list_flat_accounts()
    logger.info(f"   数据库中有 {len(db_accounts)} 个账号记录")
    logger.info("")

    # 3. 处理数据库账号
    logger.info("📍 步骤3: 处理数据库账号...")
    logger.info("=" * 60)

    db_files_processed = set()
    renamed_count = 0

    for acc in db_accounts:
        platform = acc.get('platform', '')
        user_id = acc.get('user_id', '')
        cookie_file = acc.get('cookie_file', '')

        if not user_id:
            logger.warning(f"⚠️  账号 {acc.get('account_id')} ({platform}) 没有user_id，跳过")
            continue

        target_name = f"{platform}_{user_id}.json"
        old_file = cookie_dir / cookie_file
        new_file = cookie_dir / target_name

        if old_file.exists():
            db_files_processed.add(old_file.name)
            if old_file.name != target_name:
                logger.info(f"📝 数据库账号重命名: {old_file.name} → {target_name}")
                shutil.move(str(old_file), str(new_file))
                renamed_count += 1
            else:
                logger.info(f"✅ 已是规范格式: {target_name}")
        else:
            logger.warning(f"⚠️  文件不存在: {old_file}")

    logger.info(f"✅ 数据库账号处理完成，重命名 {renamed_count} 个")
    logger.info("")

    # 4. 处理孤立文件（没有数据库记录的）
    logger.info("📍 步骤4: 处理孤立cookie文件（无数据库记录）...")
    logger.info("=" * 60)

    orphan_files = [f for f in cookie_dir.glob("*.json") if f.name not in db_files_processed]
    logger.info(f"   找到 {len(orphan_files)} 个孤立文件")
    logger.info("")

    orphan_renamed = 0
    orphan_failed = []

    for file in orphan_files:
        # 推测平台
        platform = detect_platform_from_filename(file.name)

        if not platform:
            logger.warning(f"⚠️  无法推测平台: {file.name}，跳过")
            orphan_failed.append(file.name)
            continue

        # 提取user_id
        user_id = extract_user_id_from_cookie_file(file, platform)

        if not user_id:
            logger.warning(f"⚠️  无法提取user_id: {file.name}，跳过")
            orphan_failed.append(file.name)
            continue

        # 重命名
        target_name = f"{platform}_{user_id}.json"
        new_file = cookie_dir / target_name

        if file.name != target_name:
            # 检查目标文件是否已存在
            if new_file.exists():
                logger.warning(f"⚠️  目标文件已存在: {target_name}，删除旧文件 {file.name}")
                file.unlink()
            else:
                logger.info(f"📝 孤立文件重命名: {file.name} → {target_name}")
                shutil.move(str(file), str(new_file))
                orphan_renamed += 1
        else:
            logger.info(f"✅ 已是规范格式: {target_name}")

    logger.info(f"✅ 孤立文件处理完成，重命名 {orphan_renamed} 个")
    if orphan_failed:
        logger.info(f"⚠️  {len(orphan_failed)} 个文件处理失败:")
        for fn in orphan_failed:
            logger.info(f"     - {fn}")
    logger.info("")

    # 5. 总结
    logger.info("=" * 60)
    logger.info("📊 整理完成！")
    logger.info("=" * 60)
    logger.info(f"✅ 备份位置: {backup_dir}")
    logger.info(f"✅ 数据库账号重命名: {renamed_count}")
    logger.info(f"✅ 孤立文件重命名: {orphan_renamed}")
    logger.info(f"⚠️  处理失败文件: {len(orphan_failed)}")
    logger.info("")

    logger.info("📁 当前Cookie目录结构：")
    logger.info(f"   {cookie_dir}")

    # 按平台分组显示
    current_files = sorted(cookie_dir.glob("*.json"))
    by_platform = {}
    for f in current_files:
        platform = detect_platform_from_filename(f.name) or 'unknown'
        if platform not in by_platform:
            by_platform[platform] = []
        by_platform[platform].append(f.name)

    for platform in sorted(by_platform.keys()):
        logger.info(f"\n   📂 {platform} ({len(by_platform[platform])} 个):")
        for fn in by_platform[platform][:5]:  # 每个平台最多显示5个
            logger.info(f"      ✅ {fn}")
        if len(by_platform[platform]) > 5:
            logger.info(f"      ... 还有 {len(by_platform[platform]) - 5} 个")

    logger.info("")
    logger.info("💡 建议：")
    logger.info("   1. 检查上述文件列表，确认无误")
    logger.info("   2. 如需恢复，备份文件在: " + str(backup_dir))
    logger.info("   3. 处理失败的文件需要手动检查和重命名")
    logger.info("   4. 后续新账号将自动使用规范命名: {platform}_{user_id}.json")
    logger.info("")


if __name__ == "__main__":
    organize_all_cookies()
