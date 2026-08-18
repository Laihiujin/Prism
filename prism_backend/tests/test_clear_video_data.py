"""测试清除视频数据功能"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from fastapi_app.core.config import settings
from fastapi_app.db.session import main_db_pool
import shutil
from datetime import datetime

def test_clear_video_data(backup=True):
    """测试清除视频数据"""
    print("=" * 60)
    print("视频数据清除测试")
    print("=" * 60)

    try:
        # 1. 检查当前数据
        print("\n1. 检查当前数据...")
        with main_db_pool.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM video_analytics")
            video_count = cursor.fetchone()[0]
            print(f"   - 视频数据条数: {video_count}")

            cursor = conn.execute("SELECT COUNT(*) FROM analytics_history")
            history_count = cursor.fetchone()[0]
            print(f"   - 历史记录条数: {history_count}")

        video_dir = Path(settings.VIDEO_FILES_DIR)
        if video_dir.exists():
            file_count = len(list(video_dir.rglob("*")))
            print(f"   - 视频文件数: {file_count}")
        else:
            print(f"   - 视频目录不存在")

        # 2. 执行备份（如果需要）
        if backup:
            print("\n2. 执行备份...")
            backup_dir = Path(settings.BASE_DIR) / "backups" / f"video_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_dir.mkdir(parents=True, exist_ok=True)

            # 备份视频文件
            if video_dir.exists():
                shutil.copytree(video_dir, backup_dir / "videoFile", dirs_exist_ok=True)
                print(f"   [OK] 视频文件已备份到: {backup_dir / 'videoFile'}")

            # 备份数据库数据
            with main_db_pool.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM video_analytics")
                video_analytics_data = cursor.fetchall()

                cursor = conn.execute("SELECT * FROM analytics_history")
                analytics_history_data = cursor.fetchall()

                import json
                backup_data = {
                    "video_analytics": [dict(row) for row in video_analytics_data],
                    "analytics_history": [dict(row) for row in analytics_history_data],
                    "backup_time": datetime.now().isoformat()
                }

                backup_file = backup_dir / "video_analytics_backup.json"
                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, ensure_ascii=False, indent=2)
                print(f"   - 数据库数据已备份到: {backup_file}")

        # 3. 清理视频文件
        print("\n3. 清理视频文件...")
        if video_dir.exists():
            shutil.rmtree(video_dir)
            video_dir.mkdir(parents=True, exist_ok=True)
            print(f"   [OK] 视频文件目录已清空: {video_dir}")

        # 4. 清理数据库
        print("\n4. 清理数据库...")
        with main_db_pool.get_connection() as conn:
            conn.execute("DELETE FROM video_analytics")
            conn.execute("DELETE FROM analytics_history")
            conn.commit()
            print(f"   - 数据库表已清空")

        # 5. 验证清理结果
        print("\n5. 验证清理结果...")
        with main_db_pool.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM video_analytics")
            remaining_videos = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM analytics_history")
            remaining_history = cursor.fetchone()[0]

            print(f"   - 剩余视频数据: {remaining_videos}")
            print(f"   - 剩余历史记录: {remaining_history}")

        print("\n" + "=" * 60)
        print("[OK] 测试完成！")
        if backup:
            print(f"[Backup] 备份位置: {backup_dir}")
        print("=" * 60)

        return {
            "status": "success",
            "message": "所有视频数据已清理",
            "backup": backup,
            "backup_location": str(backup_dir) if backup else None
        }

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e)
        }

if __name__ == "__main__":
    import sys
    backup = "--no-backup" not in sys.argv
    result = test_clear_video_data(backup=backup)
    print(f"\n最终结果: {result}")
