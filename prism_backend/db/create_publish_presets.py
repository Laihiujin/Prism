import sqlite3
from pathlib import Path
import os

# 获取数据库路径
current_dir = Path(__file__).parent
DB_PATH = current_dir / "database.db"

def create_publish_presets_table():
    """创建发布预设表"""
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # 创建 publish_presets 表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS publish_presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            platform TEXT NOT NULL,
            accounts TEXT NOT NULL,
            material_ids TEXT,
            title TEXT,
            description TEXT,
            tags TEXT,
            schedule_enabled INTEGER DEFAULT 0,
            videos_per_day INTEGER DEFAULT 1,
            schedule_date TEXT,
            time_point TEXT DEFAULT '10:00',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            usage_count INTEGER DEFAULT 0
        )
        ''')
        
        conn.commit()
        print(f"✅ publish_presets 表创建成功 at {DB_PATH}")

if __name__ == "__main__":
    create_publish_presets_table()
