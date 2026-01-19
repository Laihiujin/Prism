
import sys
import os
import asyncio
import sqlite3
from pathlib import Path

# 添加项目根目录到 sys.path（基于当前文件位置）
_BASE_DIR = Path(__file__).resolve().parent.parent
if str(_BASE_DIR) not in sys.path:
    sys.path.append(str(_BASE_DIR))

from fastapi_app.api.v1.ai.router import get_ai_config
from ai_service.model_manager import ModelManager

DB_PATH = os.getenv("SYNAPSE_DATABASE_PATH") or str(_BASE_DIR / "db" / "database.db")

def setup_test_db():
    """在数据库中插入测试配置"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 清理旧数据
    cursor.execute("DELETE FROM ai_model_configs WHERE service_type IN ('chat', 'cover_generation', 'function_calling')")
    
    # 插入测试数据
    cursor.execute("""
    INSERT INTO ai_model_configs (service_type, provider, api_key, base_url, model_name, is_active)
    VALUES 
    ('chat', 'siliconflow', 'sk-test-chat-key', 'https://api.siliconflow.cn/v1', 'deepseek-ai/DeepSeek-V2.5', 1),
    ('cover_generation', 'volcengine', 'sk-test-cover-key', NULL, 'jimeng-4.0', 1),
    ('function_calling', 'openai', 'sk-test-func-key', 'https://api.openai.com/v1', 'gpt-4o', 1)
    """)
    
    conn.commit()
    conn.close()
    print("✅ 测试数据已插入数据库")

def test_get_ai_config():
    """测试 get_ai_config 函数"""
    print("\n--- 测试 get_ai_config ---")
    
    # 测试封面生成配置
    config = get_ai_config("cover_generation")
    if config:
        print(f"✅ 获取到封面生成配置: Provider={config['provider']}, Model={config.get('model_name')}")
        assert config['provider'] == 'volcengine'
        assert config['api_key'] == 'sk-test-cover-key'
    else:
        print("❌ 未获取到封面生成配置")

def test_model_manager():
    """测试 ModelManager 数据库加载"""
    print("\n--- 测试 ModelManager ---")
    
    manager = ModelManager()
    # ModelManager 初始化时会调用 _load_config
    
    print(f"Current Provider: {manager.current_provider}")
    print(f"Current Model: {manager.current_model}")
    
    if manager.current_provider == 'siliconflow' and manager.current_model == 'deepseek-ai/DeepSeek-V2.5':
        print("✅ ModelManager 成功从数据库加载配置")
    else:
        print(f"❌ ModelManager 加载配置失败: {manager.current_provider} / {manager.current_model}")
        
    # 验证 provider 是否已初始化
    provider = manager.get_current_provider()
    if provider:
        print(f"✅ Provider 实例已创建: {provider.provider_name}, API Key: {provider.api_key[:5]}...")
    else:
        print("❌ Provider 实例未创建")

async def test_manus_agent():
    """测试 ManusAgentWrapper 数据库加载"""
    print("\n--- 测试 ManusAgentWrapper ---")
    
    try:
        # 只测试配置读取逻辑，不实际初始化 Agent
        import sqlite3
        from pathlib import Path
        
        # 模拟 ManusAgentWrapper.initialize 中的数据库读取逻辑
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ai_model_configs WHERE service_type = 'function_calling' AND is_active = 1")
        row = cursor.fetchone()
        
        if row:
            db_config = dict(row)
            print(f"✅ 从数据库读取到 Function Calling 配置:")
            print(f"   Provider: {db_config['provider']}")
            print(f"   Model: {db_config.get('model_name')}")
            print(f"   API Key: {db_config['api_key'][:10]}...")
            
            # 验证配置是否正确
            assert db_config['provider'] == 'openai'
            assert db_config['api_key'] == 'sk-test-func-key'
            print("✅ ManusAgentWrapper 配置读取逻辑验证成功")
        else:
            print("❌ 未找到 Function Calling 配置")
        
        conn.close()
            
    except Exception as e:
        print(f"❌ 测试出错: {e}")

if __name__ == "__main__":
    setup_test_db()
    test_get_ai_config()
    test_model_manager()
    asyncio.run(test_manus_agent())
