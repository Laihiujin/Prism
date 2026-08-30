"""
HTTP 层 Runtime 锁集成测试（FakeRedis 桩，验证 /runtime 端点 + 409 冲突语义）。
"""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_runtime_lock import FakeRedis  # noqa: E402


def _patch_singleton(redis=None):
    """把 runtime_lock_service 单例替换为 FakeRedis 实例。"""
    import fastapi_app.services.runtime_lock_service as m
    from fastapi_app.services.runtime_lock_service import AccountRuntimeLockService
    svc = AccountRuntimeLockService(redis=redis if redis is not None else FakeRedis(), ttl=30)
    m._runtime_lock_service = svc
    return svc


def test_runtime_endpoint_unlocked():
    from fastapi.testclient import TestClient
    from fastapi_app.main import app
    _patch_singleton()
    c = TestClient(app)
    r = c.get("/api/v1/accounts/rt_acct_1/runtime")
    assert r.status_code == 200
    body = r.json()["result"]
    assert body["locked"] is False
    assert body["account_id"] == "rt_acct_1"
    assert body["browser_backend"] == "patchright"  # 无账号记录 → 默认


def test_runtime_endpoint_locked():
    from fastapi.testclient import TestClient
    from fastapi_app.main import app
    svc = _patch_singleton()
    c = TestClient(app)
    svc.acquire("rt_acct_2", "publish", task_id="task-777")
    r = c.get("/api/v1/accounts/rt_acct_2/runtime")
    body = r.json()["result"]
    assert body["locked"] is True
    assert body["operation"] == "publish"
    assert body["task_id"] == "task-777"
    assert body["ttl_remaining"] is not None
    # 释放后解锁
    lock = svc.status("rt_acct_2")
    # 用 acquire 拿到的 token 释放
    # 重新获取 token：直接读状态没有 token，这里用 acquire 返回的
    # 简化：清空锁
    svc.redis.delete(svc._key("rt_acct_2"))
    r2 = c.get("/api/v1/accounts/rt_acct_2/runtime")
    assert r2.json()["result"]["locked"] is False


def test_browser_start_conflict_409():
    """浏览器启动时同账号已有 Runtime → 409 ACCOUNT_RUNTIME_BUSY（不真正启动浏览器）。"""
    from fastapi.testclient import TestClient
    from fastapi_app.main import app
    svc = _patch_singleton()
    c = TestClient(app)
    # 预先占用锁 → start 应返回 409 语义（status=error + code）
    svc.acquire("rt_acct_3", "data_collect", task_id="task-busy")
    r = c.post("/api/v1/accounts/rt_acct_3/browser/start", json={"headless": True})
    assert r.status_code == 200  # 我们以业务 status 返回（不抛 HTTPException）
    body = r.json()
    assert body.get("code") == "ACCOUNT_RUNTIME_BUSY", body
    assert body.get("runtime", {}).get("operation") == "data_collect"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except Exception as e:
            import traceback
            print(f"FAIL  {fn.__name__}: {e!r}")
            traceback.print_exc()
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
