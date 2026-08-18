import sqlite3
from pathlib import Path

# 获取数据库路径
current_dir = Path(__file__).parent
DB_PATH = current_dir / "database.db"

def add_usage_count_column():
    """为 publish_presets 表添加 usage_count 字段"""
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # 检查列是否已存在
        cursor.execute("PRAGMA table_info(publish_presets)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'usage_count' not in columns:
            cursor.execute('''
                ALTER TABLE publish_presets 
                ADD COLUMN usage_count INTEGER DEFAULT 0
            ''')
            conn.commit()
            print(f"✅ 已为 publish_presets 表添加 usage_count 字段")
        else:
            print(f"ℹ️  usage_count 字段已存在")

if __name__ == "__main__":
    add_usage_count_column()
