"""
Account Runtime 分布式锁（Redis per-account Browser Runtime Lock）。

保证任意时刻同一个 account_id 只能存在一个活跃 Browser Runtime，
避免 Persona Profile / Patchright Persistent Profile 被多个 Celery Worker、
API 请求或数据回收任务并发操作。

锁 key:  prism:runtime:account:{account_id}

设计要点：
- 唯一 token（uuid）标识持有者；释放/续期必须校验 token（Lua 原子操作），
  禁止误删其他 Worker 的锁。
- TTL 防止死锁；长任务通过 heartbeat 线程自动续期（lease renewal）。
- 锁属于 Account Runtime 上层，PersonaBackend / PatchrightBackend 不自行实现。

统一链路：
Task/API → AccountRuntimeLock → BrowserBackend → Persona/Patchright
        → Platform Adapter → release（try/finally）

错误语义：
- RuntimeLockConflict    锁已被其他操作持有（HTTP → 409 ACCOUNT_RUNTIME_BUSY）
- RuntimeLockUnavailable Redis 不可用或锁未启用（HTTP → 503）
"""
from __future__ import annotations

import json
import socket
import threading
import time
import uuid
from typing import Any, Dict, Optional

from loguru import logger

from fastapi_app.cache.redis_client import get_redis
from fastapi_app.core.config import settings

# 锁前缀
LOCK_PREFIX = "prism:runtime:account:"

# 释放锁的 Lua 脚本：解析 JSON 校验 token，仅匹配时删除
_RELEASE_LUA = """
local raw = redis.call('get', KEYS[1])
if not raw then
    return 0
end
local data = cjson.decode(raw)
if data and data.token == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""

# 续期 Lua 脚本：解析 JSON 校验 token，仅匹配时延长 TTL
_RENEW_LUA = """
local raw = redis.call('get', KEYS[1])
if not raw then
    return 0
end
local data = cjson.decode(raw)
if data and data.token == ARGV[1] then
    return redis.call('pexpire', KEYS[1], ARGV[2])
end
return 0
"""

# 读取锁内容并返回 TTL
_STATUS_LUA = """
local raw = redis.call('get', KEYS[1])
if not raw then
    return nil
end
local ttl = redis.call('pttl', KEYS[1])
return {raw, tostring(ttl)}
"""


class RuntimeLockConflict(Exception):
    """锁已被其他操作持有（HTTP → 409 ACCOUNT_RUNTIME_BUSY）。"""

    def __init__(self, account_id: str, status: Dict[str, Any]):
        self.account_id = account_id
        self.status = status
        super().__init__(
            f"账号 {account_id} 的 Browser Runtime 正被其他操作占用"
            f"（operation={status.get('operation')}）"
        )


class RuntimeLockUnavailable(Exception):
    """Redis 不可用或 Runtime 锁未启用（HTTP → 503）。"""


def _worker_id() -> str:
    return f"{socket.gethostname()}:{uuid.uuid4().hex[:6]}"


class AccountRuntimeLockService:
    """统一管理 Redis 分布式锁。"""

    def __init__(
        self,
        redis: Optional[Any] = None,
        ttl: Optional[int] = None,
        enabled: Optional[bool] = None,
    ):
        self.redis = redis if redis is not None else get_redis()
        self.default_ttl = ttl if ttl is not None else getattr(
            settings, "PRISM_RUNTIME_LOCK_TTL", 300
        )
        self.enabled = enabled if enabled is not None else getattr(
            settings, "PRISM_RUNTIME_LOCK_ENABLED", True
        )

    # ─── 基础 ────────────────────────────────────────────────

    def _key(self, account_id: str) -> str:
        return f"{LOCK_PREFIX}{account_id}"

    def _require_redis(self):
        if not self.enabled:
            raise RuntimeLockUnavailable(
                "Account Runtime 锁未启用（PRISM_RUNTIME_LOCK_ENABLED=false）"
            )
        if self.redis is None:
            raise RuntimeLockUnavailable(
                "Redis 不可用，无法获取 Account Runtime 锁（检查 REDIS_URL）"
            )

    # ─── 获取 ────────────────────────────────────────────────

    def acquire(
        self,
        account_id: str,
        operation: str,
        task_id: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        尝试获取锁（非阻塞）。成功返回锁信息（含 token）；已被占用返回 None。
        SET NX PX 原子操作。
        """
        self._require_redis()
        ttl_s = ttl or self.default_ttl
        token = uuid.uuid4().hex
        now = time.time()
        payload = {
            "token": token,
            "account_id": account_id,
            "operation": operation,
            "task_id": task_id,
            "worker_id": _worker_id(),
            "acquired_at": now,
            "expires_at": now + ttl_s,
            "ttl": ttl_s,
        }
        try:
            ok = self.redis.set(
                self._key(account_id),
                json.dumps(payload),
                nx=True,
                px=int(ttl_s * 1000),
            )
        except Exception as e:
            logger.error(f"[RuntimeLock] acquire 失败 {account_id}: {e}")
            raise RuntimeLockUnavailable(f"Redis 操作失败: {e}")
        if not ok:
            return None
        logger.info(
            f"[RuntimeLock] 获取锁 {account_id} op={operation} task={task_id} ttl={ttl_s}s"
        )
        return payload

    def acquire_or_raise(
        self,
        account_id: str,
        operation: str,
        task_id: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> Dict[str, Any]:
        """获取锁；已被占用则抛 RuntimeLockConflict（含安全状态信息）。"""
        lock = self.acquire(account_id, operation, task_id=task_id, ttl=ttl)
        if lock is None:
            status = self.status(account_id)
            raise RuntimeLockConflict(account_id, status)
        return lock

    # ─── 释放（token 校验）───────────────────────────────────

    def release(self, account_id: str, token: str) -> bool:
        """释放锁。仅当当前持有者 token 匹配才删除（Lua 原子），
        禁止误删其他 Worker 的锁。"""
        if self.redis is None:
            return False
        try:
            result = self.redis.eval(_RELEASE_LUA, 1, self._key(account_id), token)
            released = bool(result)
        except Exception as e:
            logger.error(f"[RuntimeLock] release 失败 {account_id}: {e}")
            return False
        if released:
            logger.info(f"[RuntimeLock] 释放锁 {account_id}")
        else:
            logger.warning(
                f"[RuntimeLock] 释放被拒 {account_id}：token 不匹配或锁已过期"
            )
        return released

    # ─── 续期（heartbeat / lease renewal）────────────────────

    def renew(self, account_id: str, token: str, ttl: Optional[int] = None) -> bool:
        """续期：仅当 token 匹配时延长 TTL。"""
        if self.redis is None:
            return False
        ttl_s = ttl or self.default_ttl
        try:
            result = self.redis.eval(
                _RENEW_LUA, 1, self._key(account_id), token, int(ttl_s * 1000)
            )
            return bool(result)
        except Exception as e:
            logger.error(f"[RuntimeLock] renew 失败 {account_id}: {e}")
            return False

    # ─── 状态查询 ────────────────────────────────────────────

    def status(self, account_id: str) -> Dict[str, Any]:
        """查询锁状态（安全信息，不含敏感数据）。"""
        if self.redis is None:
            return {"locked": False, "reason": "redis_unavailable"}
        try:
            raw = self.redis.eval(_STATUS_LUA, 1, self._key(account_id))
        except Exception as e:
            logger.error(f"[RuntimeLock] status 失败 {account_id}: {e}")
            return {"locked": False, "reason": "redis_error"}
        if not raw:
            return {"locked": False}
        try:
            data = json.loads(raw[0])
            ttl_ms = int(raw[1]) if len(raw) > 1 and raw[1] else 0
        except Exception:
            return {"locked": True, "operation": "unknown"}
        return {
            "locked": True,
            "operation": data.get("operation"),
            "task_id": data.get("task_id"),
            "worker_id": data.get("worker_id"),
            "acquired_at": data.get("acquired_at"),
            "expires_at": data.get("expires_at"),
            "ttl_remaining": round(ttl_ms / 1000, 1) if ttl_ms > 0 else 0,
        }


class LockHeartbeat:
    """后台心跳线程：长任务期间自动续期，防止 TTL 到期被误解锁。

    必须与 release 配对使用（try/finally）；线程为 daemon，
    进程异常退出时不会阻塞，锁靠 TTL 自动恢复。
    """

    def __init__(
        self,
        lock_service: AccountRuntimeLockService,
        account_id: str,
        token: str,
        ttl: Optional[int] = None,
        interval_ratio: float = 0.3,
    ):
        self.lock_service = lock_service
        self.account_id = account_id
        self.token = token
        self.ttl = ttl
        self.interval = (ttl or lock_service.default_ttl) * interval_ratio
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name=f"runtime-lock-hb-{self.account_id}", daemon=True
        )
        self._thread.start()

    def _run(self):
        while not self._stop.wait(self.interval):
            try:
                ok = self.lock_service.renew(self.account_id, self.token, self.ttl)
                if not ok:
                    logger.warning(
                        f"[RuntimeLock] 心跳续期失败 {self.account_id}"
                        "（token 不匹配或锁丢失，停止续期）"
                    )
                    return
            except Exception as e:
                logger.error(f"[RuntimeLock] 心跳异常 {self.account_id}: {e}")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None


# 全局单例
_runtime_lock_service: Optional[AccountRuntimeLockService] = None


def get_runtime_lock_service() -> AccountRuntimeLockService:
    """获取 Account Runtime 锁服务单例。"""
    global _runtime_lock_service
    if _runtime_lock_service is None:
        _runtime_lock_service = AccountRuntimeLockService()
    return _runtime_lock_service
