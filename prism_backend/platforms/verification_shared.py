"""Redis-backed OTP exchange between API and publishing workers."""
import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class VerificationManager:
    ttl = 1800
    index_key = "prism:verification:pending"

    def __init__(self, redis_client=None):
        self._redis = redis_client

    @property
    def redis(self):
        if self._redis is None:
            from fastapi_app.cache.redis_client import get_redis
            self._redis = get_redis()
        if self._redis is None:
            raise RuntimeError("验证码回传需要 Redis 服务")
        return self._redis

    def _key(self, account_id, kind):
        digest = hashlib.sha256(str(account_id).encode("utf-8")).hexdigest()
        return f"prism:verification:{kind}:{digest}"

    def request_verification(self, account_id, platform, message="请输入验证码", code_length=6, *, task_id=None, account=None):
        account_id = str(account_id)
        event = {"id": account_id, "platform": platform, "account": str(account or account_id), "task_id": task_id, "expires_at": time.time() + self.ttl,
                 "message": message, "code_length": code_length,
                 "timestamp": datetime.now().isoformat()}
        with self.redis.pipeline() as pipe:
            pipe.delete(self._key(account_id, "code"))
            pipe.set(self._key(account_id, "event"), json.dumps(event, ensure_ascii=False), ex=self.ttl)
            pipe.zadd(self.index_key, {account_id: time.time()})
            pipe.execute()
        logger.info("[Verification] Requested verification (platform=%s)", platform)
        return event

    def request_resend(self, account_id):
        raw = self.redis.get(self._key(account_id, "event"))
        if not raw:
            return False
        event = json.loads(raw)
        if not event.get("can_resend"):
            return False
        if not self.redis.set(self._key(account_id, "resend_cooldown"), "1", nx=True, ex=60):
            raise ValueError("请等待60秒后重新获取验证码")
        self.redis.set(self._key(account_id, "resend"), "1", ex=self.ttl)
        return True

    async def wait_for_code(self, account_id, timeout=120, on_resend=None):
        deadline = time.monotonic() + timeout
        try:
            while time.monotonic() < deadline:
                if on_resend:
                    with self.redis.pipeline() as pipe:
                        pipe.get(self._key(account_id, "resend"))
                        pipe.delete(self._key(account_id, "resend"))
                        resend_requested, _ = pipe.execute()
                    if resend_requested:
                        try:
                            await on_resend()
                        except Exception:
                            logger.warning("SMS resend failed; continuing to wait for user code")
                code = self.redis.lpop(self._key(account_id, "code"))
                if code:
                    logger.info("[Verification] Reply received")
                    return code
                await asyncio.sleep(0.5)
            return None
        finally:
            self.cleanup_queue(account_id)

    def submit_code(self, account_id, code):
        raw = self.redis.get(self._key(account_id, "event"))
        if not raw:
            return False
        event = json.loads(raw)
        code = code.strip()
        if len(code) != event.get("code_length", 6) or not code.isascii() or not code.isdigit():
            return False
        with self.redis.pipeline() as pipe:
            pipe.rpush(self._key(account_id, "code"), code)
            pipe.expire(self._key(account_id, "code"), self.ttl)
            pipe.delete(self._key(account_id, "event"))
            pipe.zrem(self.index_key, account_id)
            pipe.execute()
        return True

    def get_pending_events(self):
        events = []
        for account_id in self.redis.zrange(self.index_key, 0, -1):
            raw = self.redis.get(self._key(account_id, "event"))
            if raw:
                events.append(json.loads(raw))
            else:
                self.redis.zrem(self.index_key, account_id)
        return events

    def cleanup_queue(self, account_id):
        with self.redis.pipeline() as pipe:
            pipe.delete(self._key(account_id, "event"), self._key(account_id, "code"), self._key(account_id, "resend"), self._key(account_id, "resend_cooldown"))
            pipe.zrem(self.index_key, account_id)
            pipe.execute()


verification_manager = VerificationManager()
