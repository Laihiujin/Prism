"""cc-switch 桥接单元测试：各 app_type 的 settings_config 解析。

覆盖 cc-switch 自由格式 JSON 结构的解析（对齐其 provider.rs 分支逻辑），
以及 API 层的 app_type 校验与密钥掩码。
"""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi_app.agent.ccswitch_bridge import (
    _build_provider,
    _extract_credentials,
    _extract_models,
    get_ccswitch_db_path,
    list_providers,
    _models_url_candidates,
)


class FakeRow(dict):
    pass


def _row(app_type: str, settings: dict, is_current: int = 1, meta: str = "{}"):
    row = FakeRow()
    row["id"] = f"{app_type}-test"
    row["app_type"] = app_type
    row["name"] = f"Test {app_type}"
    row["settings_config"] = json.dumps(settings)
    row["meta"] = meta
    row["is_current"] = is_current
    row["category"] = "test"
    return row


def test_hermes_flat():
    p = _build_provider(_row("hermes", {
        "base_url": "https://api.deepseek.com/v1", "api_key": "sk-1",
        "models": [{"id": "deepseek-chat", "name": "DeepSeek Chat"}],
    }))
    assert p["base_url"] == "https://api.deepseek.com/v1"
    assert p["api_key"] == "sk-1"
    assert p["api_mode"] == "chat_completions"
    assert p["models"][0]["id"] == "deepseek-chat"


def test_claude_env_nested():
    p = _build_provider(_row("claude", {
        "env": {
            "ANTHROPIC_BASE_URL": "https://api.moonshot.cn/anthropic",
            "ANTHROPIC_AUTH_TOKEN": "sk-claude",
            "ANTHROPIC_MODEL": "kimi-k2.7-code",
        },
    }))
    assert p["base_url"] == "https://api.moonshot.cn/anthropic"
    assert p["api_key"] == "sk-claude"
    assert p["api_mode"] == "anthropic"
    assert p["models"][0]["id"] == "kimi-k2.7-code"


def test_claude_api_key_field_fallback():
    p = _build_provider(_row("claude", {
        "env": {"ANTHROPIC_BASE_URL": "https://x", "ANTHROPIC_API_KEY": "sk-2"},
    }))
    assert p["api_key"] == "sk-2"


def test_codex_toml_config():
    p = _build_provider(_row("codex", {
        "auth": {"OPENAI_API_KEY": "sk-codex"},
        "config": (
            'model_provider = "openai"\n'
            '[model_providers.openai]\n'
            'base_url = "https://api.openai.com/v1"\n'
            'model = "gpt-5.5"\n'
        ),
    }))
    assert p["base_url"] == "https://api.openai.com/v1"
    assert p["api_key"] == "sk-codex"
    assert p["api_mode"] == "responses"
    assert p["models"][0]["id"] == "gpt-5.5"


def test_gemini_env():
    p = _build_provider(_row("gemini", {
        "env": {
            "GOOGLE_GEMINI_BASE_URL": "https://generativelanguage.googleapis.com",
            "GEMINI_API_KEY": "sk-gemini",
        },
    }))
    assert p["base_url"] == "https://generativelanguage.googleapis.com"
    assert p["api_key"] == "sk-gemini"
    assert p["api_mode"] == "gemini"


def test_grokbuild_toml():
    p = _build_provider(_row("grokbuild", {
        "config": (
            '[models]\ndefault = "grok-4"\n'
            '[model.grok-4]\n'
            'base_url = "https://api.x.ai/v1"\n'
            'api_key = "sk-grok"\n'
            'model = "grok-4"\n'
        ),
    }))
    assert p["base_url"] == "https://api.x.ai/v1"
    assert p["api_key"] == "sk-grok"
    assert p["models"][0]["id"] == "grok-4"


def test_opencode_options():
    p = _build_provider(_row("opencode", {
        "options": {"baseURL": "https://api.example.com/v1", "apiKey": "sk-opencode", "model": "m1"},
    }))
    assert p["base_url"] == "https://api.example.com/v1"
    assert p["api_key"] == "sk-opencode"


def test_openclaw_camelcase():
    p = _build_provider(_row("openclaw", {
        "baseUrl": "https://api.example.com/v1", "apiKey": "sk-oc",
        "models": {"providers": {"p1": {"models": {"m1": {}, "m2": {}}}}},
    }))
    assert p["base_url"] == "https://api.example.com/v1"
    assert p["api_key"] == "sk-oc"
    assert {m["id"] for m in p["models"]} == {"m1", "m2"}


def test_pi_flat():
    p = _build_provider(_row("pi", {"baseUrl": "https://api.example.com/v1", "apiKey": "sk-pi"}))
    assert p["base_url"] == "https://api.example.com/v1"
    assert p["api_key"] == "sk-pi"


def test_models_url_candidates():
    assert _models_url_candidates("https://api.openai.com/v1") == ["https://api.openai.com/v1/models"]
    assert _models_url_candidates("https://api.anthropic.com") == [
        "https://api.anthropic.com/v1/models",
        "https://api.anthropic.com/models",
    ]
    assert _models_url_candidates("https://x.ai/v1/models") == ["https://x.ai/v1/models"]


def test_list_providers_reads_temp_db(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "cc-switch.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE providers ("
        " id TEXT NOT NULL, app_type TEXT NOT NULL, name TEXT NOT NULL,"
        " settings_config TEXT NOT NULL, website_url TEXT, category TEXT,"
        " created_at INTEGER, sort_index INTEGER, notes TEXT, icon TEXT,"
        " icon_color TEXT, meta TEXT NOT NULL DEFAULT '{}',"
        " is_current BOOLEAN NOT NULL DEFAULT 0,"
        " in_failover_queue BOOLEAN NOT NULL DEFAULT 0,"
        " PRIMARY KEY (id, app_type))"
    )
    conn.execute(
        "INSERT INTO providers (id, app_type, name, settings_config, is_current) VALUES (?,?,?,?,?)",
        ("kimi", "claude", "Kimi", json.dumps({
            "env": {"ANTHROPIC_BASE_URL": "https://api.moonshot.cn/anthropic",
                    "ANTHROPIC_AUTH_TOKEN": "sk-claude"},
        }), 1),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("CCSWITCH_DB_PATH", str(db_path))
    assert str(get_ccswitch_db_path()) == str(db_path.resolve())

    providers = list_providers("claude")
    assert len(providers) == 1
    assert providers[0]["name"] == "Kimi"
    assert providers[0]["base_url"] == "https://api.moonshot.cn/anthropic"
    assert providers[0]["api_key"] == "sk-claude"


def test_extract_credentials_unknown_type_fallback():
    base, key = _extract_credentials({"base_url": "https://x", "api_key": "k"}, "future-type")
    assert base == "https://x"
    assert key == "k"
