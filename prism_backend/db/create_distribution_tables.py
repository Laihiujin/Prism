import sqlite3
from pathlib import Path
import os

# 获取数据库路径
current_dir = Path(__file__).parent
DB_PATH = current_dir / "database.db"

def create_distribution_tables():
    """创建二维码派发功能所需的数据表"""
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # 1. 派发任务表 (distribution_tasks)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS distribution_tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            qr_token TEXT UNIQUE NOT NULL,
            platform TEXT NOT NULL,
            poi_location TEXT,
            expire_time DATETIME,
            title_template TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 2. 任务视频资源池表 (task_videos)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_videos (
            video_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            status TEXT DEFAULT 'AVAILABLE',
            claimer_id TEXT,
            distribution_time DATETIME,
            FOREIGN KEY (task_id) REFERENCES distribution_tasks(task_id)
        )
        ''')
        
        conn.commit()
        print(f"✅ 派发系统数据表 (distribution_tasks, task_videos) 创建成功: {DB_PATH}")

if __name__ == "__main__":
    create_distribution_tables()
