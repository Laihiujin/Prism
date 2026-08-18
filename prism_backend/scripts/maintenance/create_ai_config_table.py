"""
AI模型配置数据库表
用于存储不同AI服务的API密钥和配置
"""

import sqlite3
import os
from pathlib import Path

# 默认使用仓库内数据库；可通过环境变量覆盖
_BASE_DIR = Path(__file__).resolve().parents[2]  # syn_backend
DB_PATH = os.getenv("SYNAPSE_DATABASE_PATH") or str(_BASE_DIR / "db" / "database.db")

def create_ai_config_table():
    """创建AI配置表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建AI配置表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_model_configs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service_type TEXT NOT NULL UNIQUE,  -- 'chat', 'cover_generation', 'function_calling'
        provider TEXT NOT NULL,              -- 'siliconflow', 'volcengine', 'openai', etc.
        api_key TEXT NOT NULL,
        base_url TEXT,                       -- API基础URL（可选）
        model_name TEXT,                     -- 默认模型名称
        extra_config TEXT,                   -- JSON格式的额外配置
        is_active INTEGER DEFAULT 1,         -- 是否启用
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.commit()
    conn.close()
    print("✅ AI配置表创建成功")

if __name__ == "__main__":
    create_ai_config_table()
