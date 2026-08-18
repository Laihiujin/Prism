import sqlite3
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
BASE_DIR = Path(__file__).parent.parent.parent
load_dotenv(Path(BASE_DIR / ".env"))

# 配置路径
db_rel_path = os.getenv("DB_PATH_REL", "syn_backend/db/database.db")
DB_PATH = Path(BASE_DIR / db_rel_path)

def add_columns():
    print(f"💾 数据库路径: {DB_PATH}")
    
    if not DB_PATH.exists():
        print("❌ 数据库不存在")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    columns_to_add = {
        "title": "TEXT",
        "description": "TEXT",
        "tags": "TEXT",
        "cover_image": "TEXT"
    }
    
    # 获取现有列
    cursor.execute("PRAGMA table_info(file_records)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    for col, col_type in columns_to_add.items():
        if col not in existing_columns:
            print(f"➕ 添加列: {col} ({col_type})")
            try:
                cursor.execute(f"ALTER TABLE file_records ADD COLUMN {col} {col_type}")
            except Exception as e:
                print(f"❌ 添加列失败 {col}: {e}")
        else:
            print(f"✅ 列已存在: {col}")
            
    conn.commit()
    conn.close()
    print("🎉 数据库迁移完成")

if __name__ == "__main__":
    add_columns()
