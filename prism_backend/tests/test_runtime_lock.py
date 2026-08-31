"""
Account Runtime Lock 验收测试（无 Redis 依赖，用内存桩验证锁语义）。

验证项（对应验收标准）：
1. 同账号两个并发 acquire，仅一个成功
2. 不同账号可以并发
3. 释放只允许匹配 token（错误 token 无法释放）
4. TTL 到期后锁自动恢复（无需手动释放）
5. heartbeat 续期能保护长任务不被错误解锁
6. RuntimeLockConflict 携带安全状态信息（operation/task_id）
7. RuntimeLockUnavailable（Redis 不可用 / 未启用）
"""
import time
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi_app.services.runtime_lock_service import (
    AccountRuntimeLockService,
    LockHeartbeat,
    RuntimeLockConflict,
    RuntimeLockUnavailable,
)


class FakeRedis:
    """内存版 Redis 桩：实现锁所需的最小语义（含 Lua eval 兼容）。"""

    def __init__(self):
        self._data = {}  # key -> (value, expire_at_monotonic)
        self._lock = threading.Lock()

    def _get_locked(self, key):
        """调用方必须已持有 self._lock。"""
        if key not in self._data:
            return None
        value, expire_at = self._data[key]
        if expire_at and expire_at <= time.monotonic():
            del self._data[key]
            return None
        return value

    def set(self, key, value, nx=False, px=None):
        with self._lock:
            if nx and self._get_locked(key) is not None:
                return False
            expire_at = (time.monotonic() + px / 1000.0) if px else None
            self._data[key] = (value, expire_at)
            return True

    def get(self, key):
        with self._lock:
            return self._get_locked(key)

    def delete(self, key):
        with self._lock:
            return self._data.pop(key, None) is not None

    def pttl(self, key):
        with self._lock:
            if key not in self._data:
                return -2
            value, expire_at = self._data[key]
            if expire_at is None:
                return -1
            ms = int((expire_at - time.monotonic()) * 1000)
            return max(ms, 0)

    def eval(self, script, numkeys, *args):
        # 锁脚本很简单：我们按用途特判
        key = args[0]
        with self._lock:
            if "del" in script:
                token = args[1]
                current = self._get_locked(key)
                if current is not None:
                    import json
                    try:
                        data = json.loads(current)
                        if data.get("token") == token:
                            self._data.pop(key, None)
                            return 1
                    except Exception:
                        if current == token:
                            self._data.pop(key, None)
                            return 1
                return 0
            if "pexpire" in script:
                token = args[1]
                ttl_ms = int(args[2])
                current = self._get_locked(key)
                if current is None:
                    return 0
                import json
                try:
                    data = json.loads(current)
                    if data.get("token") != token:
                        return 0
                except Exception:
                    if current != token:
                        return 0
                self._data[key] = (current, time.monotonic() + ttl_ms / 1000.0)
                return 1
            if "pttl" in script:
                current = self._get_locked(key)
                if current is None:
                    return []
                value, expire_at = self._data[key]
                ttl_ms = -1 if expire_at is None else int((expire_at - time.monotonic()) * 1000)
                return [current, str(max(ttl_ms, 0))]
        raise NotImplementedError(f"unexpected lua: {script[:40]}")


def make_service(redis=None, ttl=5, enabled=True):
    return AccountRuntimeLockService(
        redis=redis if redis is not None else FakeRedis(),
        ttl=ttl,
        enabled=enabled,
    )
def test_same_account_mutex():
    """同账号并发 acquire 只有一个成功。"""
    svc = make_service()
    a = svc.acquire("acct_1", "publish", task_id="t1")
    b = svc.acquire("acct_1", "data_collect", task_id="t2")
    assert a is not None
    assert b is None, "同账号第二个 acquire 必须失败"


def test_different_accounts_concurrent():
    """不同账号可以并发。"""
    svc = make_service()
    a = svc.acquire("acct_1", "publish")
    b = svc.acquire("acct_2", "publish")
    assert a is not None and b is not None


def test_release_token_match():
    """释放只允许匹配 token。"""
    svc = make_service()
    lock = svc.acquire("acct_1", "publish", task_id="t1")
    # 错误 token 释放失败
    assert svc.release("acct_1", "wrong-token") is False
    assert svc.status("acct_1")["locked"] is True
    # 正确 token 释放成功
    assert svc.release("acct_1", lock["token"]) is True
    assert svc.status("acct_1")["locked"] is False


def test_ttl_auto_recovery():
    """TTL 到期后锁自动恢复（Worker crash 场景）。"""
    svc = make_service(ttl=1)
    lock = svc.acquire("acct_1", "publish")
    assert lock is not None
    assert svc.status("acct_1")["locked"] is True
    time.sleep(1.2)
    assert svc.status("acct_1")["locked"] is False, "TTL 到期后应自动恢复"
    # 到期后可以重新获取
    lock2 = svc.acquire("acct_1", "publish")
    assert lock2 is not None


def test_heartbeat_renews():
    """heartbeat 续期保护长任务不被错误解锁。"""
    svc = make_service(ttl=2)
    lock = svc.acquire("acct_1", "publish", task_id="long-task")
    hb = LockHeartbeat(svc, "acct_1", lock["token"], ttl=2, interval_ratio=0.3)
    hb.start()
    try:
        time.sleep(2.5)  # 超过原始 TTL，但 heartbeat 续期中
        assert svc.status("acct_1")["locked"] is True, "heartbeat 应保持锁有效"
    finally:
        hb.stop()
    svc.release("acct_1", lock["token"])


def test_conflict_status_info():
    """冲突异常携带安全状态信息（operation/task_id），不暴露敏感数据。"""
    svc = make_service()
    svc.acquire("acct_1", "publish", task_id="task-xyz")
    try:
        svc.acquire_or_raise("acct_1", "data_collect", task_id="task-abc")
        assert False, "应抛出冲突"
    except RuntimeLockConflict as e:
        assert e.status["operation"] == "publish"
        assert e.status["task_id"] == "task-xyz"
        # 不暴露敏感字段
        assert "password" not in str(e.status)


def test_unavailable_when_disabled():
    """未启用时抛 RuntimeLockUnavailable。"""
    svc = make_service(enabled=False)
    try:
        svc.acquire("acct_1", "publish")
        assert False, "未启用时应抛错"
    except RuntimeLockUnavailable:
        pass


def test_redis_none_unavailable():
    """Redis 不可用时抛 RuntimeLockUnavailable（fail-closed，不静默放行）。

    注：当本机 Redis 在线时，redis=None 会回退真实连接，因此这里用
    一个指向未监听端口的客户端模拟不可用。
    """
    import redis as redis_pkg
    dead = redis_pkg.Redis.from_url("redis://127.0.0.1:6399/15", socket_connect_timeout=0.3)
    svc = AccountRuntimeLockService(redis=dead, enabled=True)
    try:
        svc.acquire("acct_1", "publish")
        assert False, "Redis 不可用时应抛错"
    except RuntimeLockUnavailable:
        pass


def test_concurrent_threads_same_account():
    """多线程并发抢同一账号锁：持锁期间其他线程必须失败（真互斥）。"""
    svc = make_service()
    results = {}
    barrier = threading.Barrier(2)

    def holder():
        lock = svc.acquire("acct_9", "publish", ttl=5)
        results["holder"] = lock is not None
        if lock:
            barrier.wait()          # 让 contender 同时尝试
            time.sleep(1.0)         # 持锁期间
            svc.release("acct_9", lock["token"])

    def contender():
        barrier.wait()              # 与 holder 同步
        lock = svc.acquire("acct_9", "data_collect", ttl=5)
        results["contender"] = lock is not None
        if lock:
            svc.release("acct_9", lock["token"])

    t1 = threading.Thread(target=holder)
    t2 = threading.Thread(target=contender)
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert results.get("holder") is True, "holder 应成功获取锁"
    assert results.get("contender") is False, "持锁期间 contender 必须失败"
    assert svc.status("acct_9")["locked"] is False, "释放后应解锁"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:
            print(f"ERROR {fn.__name__}: {e!r}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
