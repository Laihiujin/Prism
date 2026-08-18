import sqlite3
import json
import os

# 数据库文件路径（如果不存在会自动创建）
db_file = './database.db'

# 如果数据库已存在，则删除旧的表（可选）
# if os.path.exists(db_file):
#     os.remove(db_file)

# 连接到SQLite数据库（如果文件不存在则会自动创建）
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# 创建账号记录表
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type INTEGER NOT NULL,
    filePath TEXT NOT NULL,  -- 存储文件路径
    userName TEXT NOT NULL,
    status INTEGER DEFAULT 0
)
''')

# 创建文件记录表
cursor.execute('''CREATE TABLE IF NOT EXISTS file_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- 唯一标识每条记录
    filename TEXT NOT NULL,               -- 文件名
    filesize REAL,                        -- 文件大小（单位：MB）
    upload_time DATETIME DEFAULT CURRENT_TIMESTAMP, -- 上传时间
    file_path TEXT,                       -- 文件路径
    status TEXT DEFAULT 'pending',        -- 素材状态（pending/published）
    published_at DATETIME,                -- 最近发布日期
    last_platform INTEGER,                -- 最近使用的平台编码
    last_accounts TEXT                    -- 最近使用的账号列表（JSON）
)
''')


# 提交更改
conn.commit()
print("✅ 表创建成功")
# 关闭连接
conn.close()
