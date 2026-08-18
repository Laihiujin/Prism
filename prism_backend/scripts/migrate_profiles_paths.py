"""
持久化配置路径迁移脚本

将旧的错误路径下的数据迁移到正确路径：
- syn_backend/syn_backend/browser_profiles -> syn_backend/browser_profiles
- syn_backend/syn_backend/fingerprints -> syn_backend/fingerprints

同时确保每个账号只有一个持久化配置
"""
import shutil
from pathlib import Path
from loguru import logger


def get_base_dir() -> Path:
    """获取项目根目录"""
    try:
        from config.conf import BASE_DIR
        return Path(BASE_DIR)
    except Exception:
        return Path(__file__).resolve().parents[1]


def migrate_browser_profiles():
    """迁移 browser_profiles"""
    base_dir = get_base_dir()

    # 正确路径
    correct_path = base_dir / "browser_profiles"

    # 错误路径
    wrong_path = base_dir / "syn_backend" / "browser_profiles"

    logger.info("=" * 60)
    logger.info("开始迁移 browser_profiles")
    logger.info(f"正确路径: {correct_path}")
    logger.info(f"错误路径: {wrong_path}")
    logger.info("=" * 60)

    if not wrong_path.exists():
        logger.info("✅ 未发现错误路径，无需迁移")
        return 0, 0

    # 确保正确路径存在
    correct_path.mkdir(parents=True, exist_ok=True)

    # 统计
    migrated = 0
    skipped = 0

    # 遍历错误路径下的所有目录
    for item in wrong_path.iterdir():
        if not item.is_dir():
            continue

        # 检查格式 (platform_account_id)
        parts = item.name.split('_', 1)
        if len(parts) != 2:
            logger.warning(f"⚠️ 跳过非标准目录: {item.name}")
            continue

        platform, account_id = parts
        target_dir = correct_path / f"{platform}_{account_id}"

        # 如果目标已存在，检查是否需要合并
        if target_dir.exists():
            logger.warning(f"⚠️ 目标已存在，跳过: {platform}_{account_id}")
            skipped += 1

            # 删除错误路径下的重复配置
            try:
                shutil.rmtree(item)
                logger.info(f"   已删除重复配置: {item}")
            except Exception as e:
                logger.error(f"   删除失败: {e}")

            continue

        # 移动目录
        try:
            shutil.move(str(item), str(target_dir))
            logger.info(f"✅ 迁移成功: {platform}_{account_id}")
            migrated += 1
        except Exception as e:
            logger.error(f"❌ 迁移失败 {item.name}: {e}")

    # 如果错误路径为空，删除它
    try:
        if wrong_path.exists() and not any(wrong_path.iterdir()):
            wrong_path.rmdir()
            logger.info(f"✅ 已删除空目录: {wrong_path}")
    except Exception as e:
        logger.warning(f"⚠️ 删除空目录失败: {e}")

    logger.info("")
    logger.info(f"📊 迁移统计: 成功 {migrated}, 跳过 {skipped}")
    logger.info("")

    return migrated, skipped


def migrate_fingerprints():
    """迁移 fingerprints"""
    base_dir = get_base_dir()

    # 正确路径
    correct_path = base_dir / "fingerprints"

    # 错误路径
    wrong_path = base_dir / "syn_backend" / "fingerprints"

    logger.info("=" * 60)
    logger.info("开始迁移 fingerprints")
    logger.info(f"正确路径: {correct_path}")
    logger.info(f"错误路径: {wrong_path}")
    logger.info("=" * 60)

    if not wrong_path.exists():
        logger.info("✅ 未发现错误路径，无需迁移")
        return 0, 0

    # 确保正确路径存在
    correct_path.mkdir(parents=True, exist_ok=True)

    # 统计
    migrated = 0
    skipped = 0

    # 遍历错误路径下的所有文件
    for item in wrong_path.iterdir():
        if not item.is_file():
            continue

        # 检查是否是指纹文件 (account_{account_id}_{platform}.json)
        if not item.name.endswith('.json'):
            logger.warning(f"⚠️ 跳过非JSON文件: {item.name}")
            continue

        target_file = correct_path / item.name

        # 如果目标已存在，跳过
        if target_file.exists():
            logger.warning(f"⚠️ 目标已存在，保留原有文件: {item.name}")
            skipped += 1

            # 删除错误路径下的重复文件
            try:
                item.unlink()
                logger.info(f"   已删除重复文件: {item.name}")
            except Exception as e:
                logger.error(f"   删除失败: {e}")

            continue

        # 移动文件
        try:
            shutil.move(str(item), str(target_file))
            logger.info(f"✅ 迁移成功: {item.name}")
            migrated += 1
        except Exception as e:
            logger.error(f"❌ 迁移失败 {item.name}: {e}")

    # 如果错误路径为空，删除它
    try:
        if wrong_path.exists() and not any(wrong_path.iterdir()):
            wrong_path.rmdir()
            logger.info(f"✅ 已删除空目录: {wrong_path}")
    except Exception as e:
        logger.warning(f"⚠️ 删除空目录失败: {e}")

    logger.info("")
    logger.info(f"📊 迁移统计: 成功 {migrated}, 跳过 {skipped}")
    logger.info("")

    return migrated, skipped


def check_duplicates():
    """检查是否存在重复配置"""
    base_dir = get_base_dir()

    # 检查 browser_profiles
    correct_profiles = base_dir / "browser_profiles"
    wrong_profiles = base_dir / "syn_backend" / "browser_profiles"

    profiles_in_correct = set()
    profiles_in_wrong = set()

    if correct_profiles.exists():
        profiles_in_correct = {item.name for item in correct_profiles.iterdir() if item.is_dir()}

    if wrong_profiles.exists():
        profiles_in_wrong = {item.name for item in wrong_profiles.iterdir() if item.is_dir()}

    duplicate_profiles = profiles_in_correct & profiles_in_wrong

    # 检查 fingerprints
    correct_fps = base_dir / "fingerprints"
    wrong_fps = base_dir / "syn_backend" / "fingerprints"

    fps_in_correct = set()
    fps_in_wrong = set()

    if correct_fps.exists():
        fps_in_correct = {item.name for item in correct_fps.iterdir() if item.is_file()}

    if wrong_fps.exists():
        fps_in_wrong = {item.name for item in wrong_fps.iterdir() if item.is_file()}

    duplicate_fps = fps_in_correct & fps_in_wrong

    logger.info("=" * 60)
    logger.info("重复配置检查")
    logger.info("=" * 60)

    if duplicate_profiles:
        logger.warning(f"⚠️ 发现 {len(duplicate_profiles)} 个重复的 browser_profiles:")
        for name in sorted(duplicate_profiles):
            logger.warning(f"   - {name}")
    else:
        logger.info("✅ 未发现重复的 browser_profiles")

    logger.info("")

    if duplicate_fps:
        logger.warning(f"⚠️ 发现 {len(duplicate_fps)} 个重复的 fingerprints:")
        for name in sorted(duplicate_fps):
            logger.warning(f"   - {name}")
    else:
        logger.info("✅ 未发现重复的 fingerprints")

    logger.info("")

    return len(duplicate_profiles), len(duplicate_fps)


def main():
    """主函数"""
    logger.info("🚀 开始持久化配置路径迁移")
    logger.info("")

    # 检查重复
    dup_profiles, dup_fps = check_duplicates()

    # 迁移 browser_profiles
    migrated_profiles, skipped_profiles = migrate_browser_profiles()

    # 迁移 fingerprints
    migrated_fps, skipped_fps = migrate_fingerprints()

    # 总结
    logger.info("=" * 60)
    logger.info("迁移完成")
    logger.info("=" * 60)
    logger.info(f"browser_profiles: 迁移 {migrated_profiles} 个, 跳过 {skipped_profiles} 个")
    logger.info(f"fingerprints: 迁移 {migrated_fps} 个, 跳过 {skipped_fps} 个")
    logger.info("")

    if migrated_profiles + migrated_fps > 0:
        logger.info("✅ 迁移成功！")
    else:
        logger.info("ℹ️ 无需迁移")

    logger.info("")
    logger.info("💡 说明:")
    logger.info("  - 所有持久化配置现在位于正确路径")
    logger.info("  - 每个账号只有一个配置，不会重复")
    logger.info("  - browser_profiles: syn_backend/browser_profiles")
    logger.info("  - fingerprints: syn_backend/fingerprints")
    logger.info("")


if __name__ == "__main__":
    main()
