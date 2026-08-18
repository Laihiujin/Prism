import sqlite3
import os
import uuid
from pathlib import Path
from datetime import datetime
from config.conf import BASE_DIR

from dotenv import load_dotenv

# 加载环境变量
load_dotenv(Path(BASE_DIR / ".env"))

# 配置路径
db_rel_path = os.getenv("DB_PATH_REL", "syn_backend/db/database.db")
video_rel_path = os.getenv("VIDEO_DIR_NAME", "syn_backend/videoFile")

DB_PATH = Path(BASE_DIR / db_rel_path)
VIDEO_DIR = Path(BASE_DIR / video_rel_path)

def sync_files_to_db():
    print(f"📂 正在扫描视频目录: {VIDEO_DIR}")
    print(f"💾 数据库路径: {DB_PATH}")
    
    if not VIDEO_DIR.exists():
        print("❌ 视频目录不存在")
        return

    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 确保表存在
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS file_records (
        id TEXT PRIMARY KEY,
        filename TEXT NOT NULL,
        upload_time TEXT NOT NULL,
        status TEXT DEFAULT 'ready',
        title TEXT,
        description TEXT,
        tags TEXT
    )
    ''')
    
    # 获取数据库中已有的文件
    cursor.execute("SELECT filename FROM file_records")
    existing_files = {row[0] for row in cursor.fetchall()}
    
    # 扫描文件夹
    added_count = 0
    for file_path in VIDEO_DIR.glob("*"):
        if file_path.is_file() and not file_path.name.startswith('.'):
            filename = file_path.name
            
            # 如果文件不在数据库中，则添加
            if filename not in existing_files:
                # 生成ID (注意：原表ID是INTEGER PRIMARY KEY，这里让它自动生成或使用UUID的哈希)
                # 但通常ID是自增的，所以我们不需要在INSERT中指定ID
                
                upload_time = datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                filesize = file_path.stat().st_size / (1024 * 1024) # MB
                rel_path = f"videoFile/{filename}"
                
                print(f"➕ 添加文件到数据库: {filename}")
                try:
                    cursor.execute(
                        "INSERT INTO file_records (filename, filesize, upload_time, file_path, status, note) VALUES (?, ?, ?, ?, ?, ?)",
                        (filename, filesize, upload_time, rel_path, 'ready', filename)
                    )
                    added_count += 1
                except Exception as e:
                    print(f"❌ 添加失败 {filename}: {e}")

    
    conn.commit()
    conn.close()
    
    print(f"\n✅ 同步完成! 新增了 {added_count} 个文件记录。")
    print("🔄 请刷新前端素材管理页面查看。")

if __name__ == "__main__":
    sync_files_to_db()
