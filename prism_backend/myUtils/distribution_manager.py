import sqlite3
import uuid
import json
from datetime import datetime
from pathlib import Path
import os

# 数据库路径配置
# 假设此文件位于 syn_backend/myUtils/
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "db" / "database.db"

class DistributionManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    def delete_task(self, task_id):
        """
        删除派发任务及其关联的视频记录
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM task_videos WHERE task_id = ?", (task_id,))
                cursor.execute("DELETE FROM distribution_tasks WHERE task_id = ?", (task_id,))
                conn.commit()
                # rowcount 只对最后一次执行的语句有效，这里以任务表删除结果为准
                deleted = cursor.rowcount
                return {"success": deleted > 0}
        except Exception as e:
            print(f"Error deleting task {task_id}: {e}")
            return {"success": False, "error": str(e)}

    def create_task(self, platform, title_template, video_files, poi_location=None, expire_time=None):
        """
        创建派发任务并批量添加视频
        """
        qr_token = str(uuid.uuid4())
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 1. 创建任务
                cursor.execute("""
                    INSERT INTO distribution_tasks (qr_token, platform, poi_location, expire_time, title_template)
                    VALUES (?, ?, ?, ?, ?)
                """, (qr_token, platform, poi_location, expire_time, title_template))
                
                task_id = cursor.lastrowid
                
                # 2. 批量插入视频
                if video_files:
                    video_data = [(task_id, f) for f in video_files]
                    cursor.executemany("""
                        INSERT INTO task_videos (task_id, file_path, status)
                        VALUES (?, ?, 'AVAILABLE')
                    """, video_data)
                
                conn.commit()
                return {"success": True, "task_id": task_id, "qr_token": qr_token}
                
        except Exception as e:
            print(f"Error creating task: {e}")
            return {"success": False, "error": str(e)}

    def add_videos_to_task(self, task_id, video_files):
        """
        向现有任务追加视频
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                video_data = [(task_id, f) for f in video_files]
                cursor.executemany("""
                    INSERT INTO task_videos (task_id, file_path, status)
                    VALUES (?, ?, 'AVAILABLE')
                """, video_data)
                conn.commit()
                return {"success": True, "count": len(video_files)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_task_status(self, task_id):
        """
        获取任务状态统计
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 获取任务详情
                cursor.execute("SELECT * FROM distribution_tasks WHERE task_id = ?", (task_id,))
                task = cursor.fetchone()
                if not task:
                    return None
                
                # 获取统计数据
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'AVAILABLE' THEN 1 ELSE 0 END) as available,
                        SUM(CASE WHEN status = 'DISTRIBUTED' THEN 1 ELSE 0 END) as distributed
                    FROM task_videos 
                    WHERE task_id = ?
                """, (task_id,))
                stats = cursor.fetchone()
                
                return {
                    "task": dict(task),
                    "stats": {
                        "total": stats['total'],
                        "available": stats['available'],
                        "distributed": stats['distributed']
                    }
                }
        except Exception as e:
            print(f"Error getting task status: {e}")
            return None

    def get_all_tasks(self):
        """
        获取所有派发任务列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        t.*,
                        COUNT(v.video_id) as total_videos,
                        SUM(CASE WHEN v.status = 'AVAILABLE' THEN 1 ELSE 0 END) as available_count,
                        SUM(CASE WHEN v.status = 'DISTRIBUTED' THEN 1 ELSE 0 END) as distributed_count
                    FROM distribution_tasks t
                    LEFT JOIN task_videos v ON t.task_id = v.task_id
                    GROUP BY t.task_id
                    ORDER BY t.created_at DESC
                """)
                
                tasks = [dict(row) for row in cursor.fetchall()]
                return tasks
        except Exception as e:
            print(f"Error getting all tasks: {e}")
            return []

    def claim_video_atomically(self, qr_token, claimer_id):
        """
        原子操作：领取视频
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 1. 开启立即事务 (SQLite specific for concurrency)
                conn.execute("BEGIN IMMEDIATE TRANSACTION;")
                
                try:
                    # 2. 查找任务 ID
                    cursor.execute("SELECT task_id, expire_time FROM distribution_tasks WHERE qr_token = ?", (qr_token,))
                    task = cursor.fetchone()
                    
                    if not task:
                        conn.execute("ROLLBACK;")
                        return {"success": False, "error": "Task not found"}
                    
                    # 检查过期
                    if task['expire_time']:
                        try:
                            # 尝试解析 ISO 格式时间字符串
                            expire_dt = datetime.fromisoformat(task['expire_time'])
                            if datetime.now() > expire_dt:
                                conn.execute("ROLLBACK;")
                                return {"success": False, "error": "Task expired"}
                        except ValueError:
                            # 如果解析失败，尝试其他格式或忽略
                            pass 

                    # 3. 锁定一条可用视频
                    # 注意：SQLite 的 BEGIN IMMEDIATE 已经锁定了数据库写入，
                    # 所以这里的 SELECT 不需要 FOR UPDATE (SQLite 不支持 FOR UPDATE)
                    # 只要我们在同一个事务中读取然后更新即可。
                    
                    cursor.execute("""
                        SELECT video_id, file_path, t.title_template, t.poi_location
                        FROM task_videos v
                        JOIN distribution_tasks t ON v.task_id = t.task_id
                        WHERE t.qr_token = ? AND v.status = 'AVAILABLE'
                        LIMIT 1
                    """, (qr_token,))
                    
                    video_record = cursor.fetchone()
                    
                    if video_record:
                        # 4. 更新状态
                        cursor.execute("""
                            UPDATE task_videos 
                            SET status = 'DISTRIBUTED', claimer_id = ?, distribution_time = CURRENT_TIMESTAMP
                            WHERE video_id = ?
                        """, (claimer_id, video_record['video_id']))
                        
                        conn.commit()
                        
                        return {
                            "success": True,
                            "data": {
                                "video_path": video_record['file_path'],
                                "title": video_record['title_template'], # 实际可能需要根据模板生成
                                "poi": video_record['poi_location']
                            }
                        }
                    else:
                        conn.execute("ROLLBACK;")
                        return {"success": False, "error": "No videos available"}
                        
                except Exception as e:
                    conn.execute("ROLLBACK;")
                    raise e
                    
        except Exception as e:
            print(f"Claim error: {e}")
            return {"success": False, "error": str(e)}

    def claim_video_by_task(self, task_id, claimer_id):
        """
        按 task_id 领取一条可用视频（用于发布/派发），并标记为已分发
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute("BEGIN IMMEDIATE TRANSACTION;")
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT v.video_id, v.file_path, t.title_template, t.poi_location, t.platform
                    FROM task_videos v
                    JOIN distribution_tasks t ON v.task_id = t.task_id
                    WHERE v.task_id = ? AND v.status = 'AVAILABLE'
                    LIMIT 1
                    """,
                    (task_id,)
                )
                row = cursor.fetchone()

                if not row:
                    conn.execute("ROLLBACK;")
                    return {"success": False, "error": "No videos available"}

                cursor.execute(
                    """
                    UPDATE task_videos
                    SET status = 'DISTRIBUTED', claimer_id = ?, distribution_time = CURRENT_TIMESTAMP
                    WHERE video_id = ?
                    """,
                    (claimer_id, row["video_id"]),
                )
                conn.commit()

                return {
                    "success": True,
                    "data": {
                        "video_path": row["file_path"],
                        "title": row["title_template"],
                        "poi": row["poi_location"],
                        "platform": row["platform"],
                    },
                }
        except Exception as e:
            print(f"Claim by task error: {e}")
            return {"success": False, "error": str(e)}

# 全局实例
distribution_manager = DistributionManager()
