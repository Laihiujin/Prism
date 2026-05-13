import sqlite3

import pytest

from ai_service.model_manager import ModelManager
from fastapi_app.api.v1.ai.router import get_ai_config


@pytest.fixture(autouse=True)
def isolated_ai_config_db(tmp_path, monkeypatch):
    db_path = tmp_path / "database.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE ai_model_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_type TEXT NOT NULL UNIQUE,
            provider TEXT NOT NULL,
            api_key TEXT NOT NULL,
            base_url TEXT,
            model_name TEXT,
            extra_config TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.executemany(
        """
        INSERT INTO ai_model_configs (service_type, provider, api_key, base_url, model_name, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        [
            ("chat", "siliconflow", "sk-test-chat-key", "https://api.siliconflow.cn/v1", "deepseek-ai/DeepSeek-V3"),
            ("cover_generation", "volcengine", "sk-test-cover-key", None, "jimeng-4.0"),
            ("function_calling", "openai", "sk-test-func-key", "https://api.openai.com/v1", "gpt-4o"),
        ],
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("SYNAPSE_DATABASE_PATH", str(db_path))
    monkeypatch.setattr(get_ai_config.__globals__["settings"], "DATABASE_PATH", str(db_path))
    return db_path


def test_get_ai_config():
    config = get_ai_config("cover_generation")

    assert config is not None
    assert config["provider"] == "volcengine"
    assert config["api_key"] == "sk-test-cover-key"
    assert config["model_name"] == "jimeng-4.0"


def test_model_manager():
    manager = ModelManager()

    assert manager.current_provider == "siliconflow"
    assert manager.current_model == "deepseek-ai/DeepSeek-V3"
    assert manager.get_current_provider() is not None


@pytest.mark.asyncio
async def test_openclaw_agent_config(isolated_ai_config_db):
    conn = sqlite3.connect(isolated_ai_config_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ai_model_configs WHERE service_type = 'function_calling' AND is_active = 1")
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    db_config = dict(row)
    assert db_config["provider"] == "openai"
    assert db_config["api_key"] == "sk-test-func-key"
