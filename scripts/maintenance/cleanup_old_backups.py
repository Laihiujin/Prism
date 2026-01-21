"""
清理旧的cookie备份文件
- 删除backups根目录下154个带时间戳的旧备份
- 保留4个整理备份目录
"""
from pathlib import Path
from datetime import datetime

def cleanup_old_backups():
    """清理旧备份"""
    print("=" * 60)
    print("Cleaning Old Cookie Backups")
    print("=" * 60)
    print()

    backup_dir = Path("E:/SynapseAutomation/syn_backend/cookiesFile/backups")

    # 查找所有根目录的json文件（旧备份）
    old_backups = list(backup_dir.glob("*.json"))

    print(f"Found {len(old_backups)} old backup files")

    if not old_backups:
        print("[OK] No old backups to clean")
        return

    # 计算总大小
    total_size = sum(f.stat().st_size for f in old_backups)
    print(f"Total size: {total_size / 1024 / 1024:.2f} MB")
    print()

    # 创建归档目录
    archive_dir = backup_dir / "archived_old_backups_20251219"
    archive_dir.mkdir(exist_ok=True)

    print(f"Moving to: {archive_dir}")
    print()

    # 移动文件
    moved = 0
    for f in old_backups:
        try:
            dest = archive_dir / f.name
            f.rename(dest)
            moved += 1
            if moved % 20 == 0:
                print(f"  Moved {moved}/{len(old_backups)}...")
        except Exception as e:
            print(f"[ERROR] Failed to move {f.name}: {e}")

    print()
    print("=" * 60)
    print("[SUCCESS] Cleanup complete!")
    print("=" * 60)
    print(f"Moved: {moved} files")
    print(f"Freed: {total_size / 1024 / 1024:.2f} MB from backups root")
    print(f"Archived to: {archive_dir}")
    print()
    print("Remaining structure:")
    print("  cookiesFile/backups/")
    print("    ├── 20251219_144958/      (organize)")
    print("    ├── 20251219_145112/      (organize)")
    print("    ├── 20251219_145238/      (organize_full)")
    print("    ├── 20251219_150339/      (orphaned)")
    print("    └── archived_old_backups_20251219/  (154 old files)")
    print()

if __name__ == "__main__":
    cleanup_old_backups()
