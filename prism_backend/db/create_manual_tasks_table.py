"""
创建人工任务管理表
用于存储需要人工处理的发布任务（如需要短信验证的任务）
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "task_queue.db"

def create_manual_tasks_table():
    """创建人工任务表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建人工任务表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS manual_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT UNIQUE NOT NULL,
            task_type TEXT NOT NULL,
            platform TEXT NOT NULL,
            account_id TEXT NOT NULL,
            account_name TEXT,
            material_id TEXT,
            material_name TEXT,
            title TEXT,
            description TEXT,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_error TEXT,
            metadata TEXT
        )
    """)
    
    # 创建索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_manual_tasks_status 
        ON manual_tasks(status)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_manual_tasks_platform 
        ON manual_tasks(platform)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_manual_tasks_account 
        ON manual_tasks(account_id)
    """)
    
    conn.commit()
    conn.close()
    print("✅ 人工任务表创建成功")

if __name__ == "__main__":
    create_manual_tasks_table()
