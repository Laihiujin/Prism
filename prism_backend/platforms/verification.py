"""Short-lived verification requests shared between API and publishing workers."""
import asyncio
import json
import re
import time
import uuid
from datetime import datetime, timezone
from fastapi_app.cache.redis_client import get_redis


class VerificationManager:
    prefix = "prism:verification:"

    def __init__(self, redis_client=None):
        self.redis_client = redis_client

    def _redis(self):
        client = self.redis_client if self.redis_client is not None else get_redis()
        if client is None:
            raise RuntimeError("验证码回传服务不可用，请检查 Redis")
        return client

    def _resolve(self, account_id):
        client = self._redis()
        if client.exists(self.prefix + "event:" + account_id):
            return account_id
        value = client.get(self.prefix + "account:" + account_id)
        return value.decode() if isinstance(value, bytes) else value

    def request_verification(self, account_id, platform, message="请输入验证码", code_length=6):
        request_id = str(uuid.uuid4())
        event = {"id": request_id, "platform": platform, "account": account_id, "message": message,
                 "code_length": code_length, "timestamp": datetime.now(timezone.utc).isoformat()}
        client = self._redis()
        pipe = client.pipeline()
        pipe.setex(self.prefix + "event:" + request_id, 180, json.dumps(event, ensure_ascii=False))
        pipe.setex(self.prefix + "account:" + account_id, 180, request_id)
        pipe.zadd(self.prefix + "pending", {request_id: time.time() + 180})
        pipe.execute()
        return event

    async def wait_for_code(self, account_id, timeout=120):
        request_id = self._resolve(account_id)
        if not request_id:
            return None
        client = self._redis()
        deadline = time.monotonic() + timeout
        try:
            while time.monotonic() < deadline:
                code = client.lpop(self.prefix + "code:" + request_id)
                if code:
                    return code.decode() if isinstance(code, bytes) else code
                await asyncio.sleep(0.5)
            return None
        finally:
            self.cleanup_queue(request_id)

    def submit_code(self, account_id, code):
        request_id = self._resolve(account_id)
        if not request_id or not re.fullmatch(r"[0-9]{4,8}", code or ""):
            return False
        client = self._redis()
        raw = client.get(self.prefix + "event:" + request_id)
        if not raw or len(code) != json.loads(raw).get("code_length", 6):
            return False
        # Enqueue and mark accepted atomically, including an expiry race check.
        accepted = client.eval("""
            if redis.call('EXISTS', KEYS[1]) == 0 or redis.call('EXISTS', KEYS[2]) == 1 then
                return 0
            end
            redis.call('SET', KEYS[2], '1', 'EX', 180)
            redis.call('RPUSH', KEYS[3], ARGV[1])
            redis.call('EXPIRE', KEYS[3], 120)
            return 1
        """, 3, self.prefix + "event:" + request_id,
            self.prefix + "submitted:" + request_id, self.prefix + "code:" + request_id, code)
        return bool(accepted)

    def get_pending_events(self):
        client = self._redis()
        client.zremrangebyscore(self.prefix + "pending", "-inf", time.time())
        events = []
        for value in client.zrange(self.prefix + "pending", 0, -1):
            request_id = value.decode() if isinstance(value, bytes) else value
            raw = client.get(self.prefix + "event:" + request_id)
            if raw and not client.exists(self.prefix + "submitted:" + request_id):
                events.append(json.loads(raw))
        return events

    def cleanup_queue(self, account_id):
        request_id = self._resolve(account_id)
        if not request_id:
            return
        client = self._redis()
        client.delete(self.prefix + "event:" + request_id, self.prefix + "code:" + request_id, self.prefix + "submitted:" + request_id)
        client.zrem(self.prefix + "pending", request_id)


verification_manager = VerificationManager()
