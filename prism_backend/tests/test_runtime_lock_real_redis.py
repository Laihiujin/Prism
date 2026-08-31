"""
真实 Redis 集成测试：验证 AccountRuntimeLockService 在生产 Redis 上的行为。
运行前提：本机 Redis 已启动（redis-server --daemonize yes，端口 6379）。
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi_app.cache.redis_client import get_redis
from fastapi_app.services.runtime_lock_service import (
    AccountRuntimeLockService,
    LockHeartbeat,
    RuntimeLockConflict,
)


def _clean():
    r = get_redis()
    for k in r.scan_iter("prism:runtime:account:*"):
        r.delete(k)


def test_real_redis_mutex():
    """同账号互斥（真实 Redis SET NX）。"""
    _clean()
    svc = AccountRuntimeLockService(redis=get_redis(), ttl=30)
    a = svc.acquire("real_acct_1", "publish", task_id="t1")
    b = svc.acquire("real_acct_1", "data_collect", task_id="t2")
    assert a is not None and b is None
    svc.release("real_acct_1", a["token"])


def test_real_redis_token_release():
    """错误 token 无法释放（Lua 原子比较）。"""
    _clean()
    svc = AccountRuntimeLockService(redis=get_redis(), ttl=30)
    lock = svc.acquire("real_acct_2", "publish", task_id="t1")
    assert svc.release("real_acct_2", "WRONG") is False
    assert svc.status("real_acct_2")["locked"] is True
    assert svc.release("real_acct_2", lock["token"]) is True
    assert svc.status("real_acct_2")["locked"] is False


def test_real_redis_ttl_expiry():
    """TTL 到期自动恢复（Worker crash 场景）。"""
    _clean()
    svc = AccountRuntimeLockService(redis=get_redis(), ttl=1)
    lock = svc.acquire("real_acct_3", "publish")
    assert svc.status("real_acct_3")["locked"] is True
    time.sleep(1.3)
    assert svc.status("real_acct_3")["locked"] is False
    assert svc.acquire("real_acct_3", "publish") is not None


def test_real_redis_heartbeat():
    """heartbeat 续期保护长任务。"""
    _clean()
    svc = AccountRuntimeLockService(redis=get_redis(), ttl=2)
    lock = svc.acquire("real_acct_4", "publish", task_id="long")
    hb = LockHeartbeat(svc, "real_acct_4", lock["token"], ttl=2, interval_ratio=0.3)
    hb.start()
    try:
        time.sleep(2.5)
        assert svc.status("real_acct_4")["locked"] is True
    finally:
        hb.stop()
    svc.release("real_acct_4", lock["token"])


def test_real_redis_conflict():
    """冲突异常携带状态信息。"""
    _clean()
    svc = AccountRuntimeLockService(redis=get_redis(), ttl=30)
    svc.acquire("real_acct_5", "publish", task_id="task-busy")
    try:
        svc.acquire_or_raise("real_acct_5", "data_collect")
        assert False
    except RuntimeLockConflict as e:
        assert e.status["operation"] == "publish"
        assert e.status["task_id"] == "task-busy"


def test_real_redis_http_runtime_endpoint():
    """HTTP /runtime 端点对接真实 Redis。"""
    from fastapi.testclient import TestClient
    from fastapi_app.main import app
    import fastapi_app.services.runtime_lock_service as m
    m._runtime_lock_service = AccountRuntimeLockService(redis=get_redis(), ttl=30)
    c = TestClient(app)
    r = c.get("/api/v1/accounts/real_http_acct/runtime")
    assert r.status_code == 200
    assert r.json()["result"]["locked"] is False


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
