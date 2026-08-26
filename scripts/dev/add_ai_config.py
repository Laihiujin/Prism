"""添加 AI chat 配置到数据库"""
import sqlite3
import json

# 请替换为你的实际 API Key
API_KEY = "sk-your-api-key-here"  # ⚠️ 替换为实际的 API Key
BASE_URL = "https://api.siliconflow.cn/v1"
MODEL_NAME = "deepseek-ai/DeepSeek-V3"

conn = sqlite3.connect('prism_backend/db/database.db')
cursor = conn.cursor()

# 检查是否已存在配置
cursor.execute("SELECT id FROM ai_model_configs WHERE service_type = 'chat'")
existing = cursor.fetchone()

if existing:
    print("❌ 已存在 chat 配置，正在更新...")
    cursor.execute("""
        UPDATE ai_model_configs
        SET provider = 'openai_compatible',
            api_key = ?,
            base_url = ?,
            model_name = ?,
            is_active = 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE service_type = 'chat'
    """, (API_KEY, BASE_URL, MODEL_NAME))
    print("✅ chat 配置已更新")
else:
    print("📝 正在添加 chat 配置...")
    cursor.execute("""
        INSERT INTO ai_model_configs
        (service_type, provider, api_key, base_url, model_name, extra_config, is_active)
        VALUES ('chat', 'openai_compatible', ?, ?, ?, '{}', 1)
    """, (API_KEY, BASE_URL, MODEL_NAME))
    print("✅ chat 配置已添加")

conn.commit()

# 验证配置
cursor.execute("SELECT service_type, provider, model_name, is_active FROM ai_model_configs WHERE service_type = 'chat'")
row = cursor.fetchone()
if row:
    print(f"\n当前配置: service_type={row[0]}, provider={row[1]}, model={row[2]}, active={row[3]}")
else:
    print("⚠️ 未找到配置")

conn.close()
print("\n⚠️ 配置完成后，请重启后端服务使配置生效！")
