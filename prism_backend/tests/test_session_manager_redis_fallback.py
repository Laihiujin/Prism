from __future__ import annotations

import sys
import types


class BrokenRedis:
    def setex(self, *args, **kwargs):
        raise ConnectionError("offline")


def test_memory_session_survives_redis_outage(monkeypatch):
    fake_redis_module = types.ModuleType("fastapi_app.cache.redis_client")
    fake_redis_module.get_redis = lambda: BrokenRedis()
    fake_time_module = types.ModuleType("fastapi_app.core.timezone_utils")
    fake_time_module.now_beijing_iso = lambda: "2026-08-17T00:00:00+08:00"
    monkeypatch.setitem(sys.modules, "fastapi_app.cache.redis_client", fake_redis_module)
    monkeypatch.setitem(sys.modules, "fastapi_app.core.timezone_utils", fake_time_module)

    sys.modules.pop("prism_backend.app_new.session_manager", None)
    from prism_backend.app_new.session_manager import SessionManager

    manager = SessionManager("douyin-test")
    assert manager.create_session("attempt-1", {"page": object()}) is True
    assert manager.get_session("attempt-1") is not None
