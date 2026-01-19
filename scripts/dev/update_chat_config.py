"""手动更新 chat 配置的脚本"""
import sqlite3
import json

# ⚠️ 请替换为你在前端填写的真实 API Key
API_KEY = "在这里填写你的真实 API Key"

# 其他配置（从截图获取）
config = {
    'service_type': 'chat',
    'provider': 'openai_compatible',
    'api_key': API_KEY,
    'base_url': 'https://api.siliconflow.cn/v1',
    'model_name': 'Qwen/Qwen2.5-7B-Instruct',
    'extra_config': json.dumps({
        'temperature': 0.7,
        'max_tokens': 2000
    }),
    'is_active': 1
}

conn = sqlite3.connect('syn_backend/db/database.db')
cursor = conn.cursor()

# 更新配置
cursor.execute("""
    UPDATE ai_model_configs
    SET provider = ?,
        api_key = ?,
        base_url = ?,
        model_name = ?,
        extra_config = ?,
        is_active = ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE service_type = ?
""", (
    config['provider'],
    config['api_key'],
    config['base_url'],
    config['model_name'],
    config['extra_config'],
    config['is_active'],
    config['service_type']
))

conn.commit()

# 验证更新
cursor.execute('SELECT provider, model_name, is_active FROM ai_model_configs WHERE service_type = ?', ('chat',))
row = cursor.fetchone()
print('Config updated:')
print(f'  Provider: {row[0]}')
print(f'  Model: {row[1]}')
print(f'  Active: {row[2]}')

conn.close()
print('\nConfig has been updated successfully!')
print('You can now test the /api/v1/ai/chat endpoint.')
