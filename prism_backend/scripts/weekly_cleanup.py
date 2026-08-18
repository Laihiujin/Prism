"""
每周定时清理脚本
功能：清理超过7天的Cookie备份文件

建议配置为每周执行一次 (Crontab)
0 3 * * 0 cd /path/to/syn_backend && python scripts/weekly_cleanup.py
"""
import os
import sys
from pathlib import Path

sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from myUtils.cookie_backup import cleanup_old_backups, get_backup_stats

def main():
    print("="*50)
    print("🗑️  每周Cookie备份清理任务")
    print("="*50)
    
    # 显示清理前统计
    before_stats = get_backup_stats()
    print(f"\n清理前:")
    print(f"  总文件数: {before_stats['total']}")
    print(f"  总大小: {before_stats['size'] / 1024:.2f} KB")
    
    # 执行清理
    deleted = cleanup_old_backups(7)
    
    # 显示清理后统计
    after_stats = get_backup_stats()
    print(f"\n清理后:")
    print(f"  总文件数: {after_stats['total']}")
    print(f"  总大小: {after_stats['size'] / 1024:.2f} KB")
    print(f"  释放空间: {(before_stats['size'] - after_stats['size']) / 1024:.2f} KB")
    
    print(f"\n✅ 清理完成，删除了 {deleted} 个过期备份")

if __name__ == "__main__":
    main()
