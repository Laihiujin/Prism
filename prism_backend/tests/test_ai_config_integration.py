import asyncio
import os
import sqlite3
import sys
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent
if str(_BASE_DIR) not in sys.path:
    sys.path.append(str(_BASE_DIR))

from ai_service.model_manager import ModelManager
from fastapi_app.api.v1.ai.router import get_ai_config

DB_PATH = os.getenv("SYNAPSE_DATABASE_PATH") or str(_BASE_DIR / "db" / "database.db")


def setup_test_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ai_model_configs WHERE service_type IN ('chat', 'cover_generation', 'function_calling')")
    cursor.execute(
        """
        INSERT INTO ai_model_configs (service_type, provider, api_key, base_url, model_name, is_active)
        VALUES
        ('chat', 'siliconflow', 'sk-test-chat-key', 'https://api.siliconflow.cn/v1', 'deepseek-ai/DeepSeek-V2.5', 1),
        ('cover_generation', 'volcengine', 'sk-test-cover-key', NULL, 'jimeng-4.0', 1),
        ('function_calling', 'openai', 'sk-test-func-key', 'https://api.openai.com/v1', 'gpt-4o', 1)
        """
    )
    conn.commit()
    conn.close()
    print("Inserted test data into ai_model_configs")


def test_get_ai_config():
    print("\n--- Test get_ai_config ---")
    config = get_ai_config("cover_generation")
    if config:
        print(f"Loaded cover config: provider={config['provider']}, model={config.get('model_name')}")
        assert config["provider"] == "volcengine"
        assert config["api_key"] == "sk-test-cover-key"
    else:
        raise AssertionError("cover_generation config not found")


def test_model_manager():
    print("\n--- Test ModelManager ---")
    manager = ModelManager()
    print(f"Current Provider: {manager.current_provider}")
    print(f"Current Model: {manager.current_model}")
    assert manager.current_provider == "siliconflow"
    assert manager.current_model == "deepseek-ai/DeepSeek-V2.5"

    provider = manager.get_current_provider()
    if provider:
        print(f"Provider instance ready: {provider.provider_name}, API Key: {provider.api_key[:5]}...")
    else:
        raise AssertionError("Provider instance was not created")


async def test_openclaw_agent_config():
    print("\n--- Test OpenClaw agent config ---")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ai_model_configs WHERE service_type = 'function_calling' AND is_active = 1")
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise AssertionError("Function-calling config not found")

    db_config = dict(row)
    print("Loaded function-calling config:")
    print(f"  Provider: {db_config['provider']}")
    print(f"  Model: {db_config.get('model_name')}")
    print(f"  API Key: {db_config['api_key'][:10]}...")
    assert db_config["provider"] == "openai"
    assert db_config["api_key"] == "sk-test-func-key"


if __name__ == "__main__":
    setup_test_db()
    test_get_ai_config()
    test_model_manager()
    asyncio.run(test_openclaw_agent_config())
