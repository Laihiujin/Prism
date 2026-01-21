"""
登录会话管理器
同时支持内存和 Redis 存储，提供兜底机制
"""
import json
from typing import Optional, Dict, Any
from datetime import datetime
from loguru import logger
from fastapi_app.cache.redis_client import get_redis
from fastapi_app.core.timezone_utils import now_beijing_iso


class SessionManager:
    """
    统一的会话管理器

    - 内存优先：快速访问
    - Redis 兜底：持久化和分布式支持
    - 自动同步：写入时同时更新内存和 Redis
    """

    def __init__(self, platform_name: str):
        """
        Args:
            platform_name: 平台名称 (douyin/kuaishou/tencent/xiaohongshu)
        """
        self.platform_name = platform_name
        self._memory_sessions: Dict[str, Dict[str, Any]] = {}
        self.redis = get_redis()
        self._redis_prefix = f"login_session:{platform_name}:"
        self._session_ttl = 3600  # 1小时过期

    def _redis_key(self, session_id: str) -> str:
        """生成 Redis key"""
        return f"{self._redis_prefix}{session_id}"

    def create_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """
        创建会话（同时写入内存和 Redis）

        Args:
            session_id: 会话ID
            session_data: 会话数据（包含 browser, playwright, page 等）

        Returns:
            bool: 是否创建成功
        """
        try:
            # 添加创建时间
            if "created_at" not in session_data:
                session_data["created_at"] = now_beijing_iso()

            # ✅ 写入内存
            self._memory_sessions[session_id] = session_data

            # ✅ 写入 Redis（只存储可序列化的元数据）
            if self.redis:
                metadata = {
                    "session_id": session_id,
                    "platform": self.platform_name,
                    "created_at": session_data.get("created_at"),
                    "status": "active"
                }
                self.redis.setex(
                    self._redis_key(session_id),
                    self._session_ttl,
                    json.dumps(metadata, ensure_ascii=False)
                )
                logger.debug(f"[{self.platform_name}] Session {session_id} created in memory + Redis")
            else:
                logger.warning(f"[{self.platform_name}] Redis unavailable, session only in memory")

            return True
        except Exception as e:
            logger.error(f"[{self.platform_name}] Failed to create session {session_id}: {e}")
            return False

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话（内存优先，Redis 兜底）

        Args:
            session_id: 会话ID

        Returns:
            Optional[Dict]: 会话数据，不存在返回 None
        """
        # ✅ 优先从内存读取
        if session_id in self._memory_sessions:
            logger.debug(f"[{self.platform_name}] Session {session_id} found in memory")
            return self._memory_sessions[session_id]

        # ✅ 兜底从 Redis 读取（仅元数据）
        if self.redis:
            try:
                redis_data = self.redis.get(self._redis_key(session_id))
                if redis_data:
                    metadata = json.loads(redis_data)
                    logger.warning(
                        f"[{self.platform_name}] Session {session_id} found in Redis but not in memory. "
                        "Browser/Playwright instances lost (service restart?)"
                    )
                    # 返回 None，让调用者知道需要重新创建会话
                    return None
            except Exception as e:
                logger.error(f"[{self.platform_name}] Failed to read from Redis: {e}")

        logger.debug(f"[{self.platform_name}] Session {session_id} not found")
        return None

    def remove_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        移除会话（同时从内存和 Redis 删除）

        Args:
            session_id: 会话ID

        Returns:
            Optional[Dict]: 被移除的会话数据
        """
        # ✅ 从内存移除
        session = self._memory_sessions.pop(session_id, None)

        # ✅ 从 Redis 移除
        if self.redis:
            try:
                self.redis.delete(self._redis_key(session_id))
                logger.debug(f"[{self.platform_name}] Session {session_id} removed from memory + Redis")
            except Exception as e:
                logger.error(f"[{self.platform_name}] Failed to delete from Redis: {e}")

        return session

    def update_session_status(self, session_id: str, status: str) -> bool:
        """
        更新会话状态（仅更新 Redis）

        Args:
            session_id: 会话ID
            status: 状态 (active/confirmed/expired)

        Returns:
            bool: 是否更新成功
        """
        if not self.redis:
            return False

        try:
            redis_data = self.redis.get(self._redis_key(session_id))
            if redis_data:
                metadata = json.loads(redis_data)
                metadata["status"] = status
                metadata["updated_at"] = now_beijing_iso()
                self.redis.setex(
                    self._redis_key(session_id),
                    self._session_ttl,
                    json.dumps(metadata, ensure_ascii=False)
                )
                logger.debug(f"[{self.platform_name}] Session {session_id} status updated to {status}")
                return True
        except Exception as e:
            logger.error(f"[{self.platform_name}] Failed to update session status: {e}")

        return False

    def list_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        列出所有活跃会话（仅内存）

        Returns:
            Dict: session_id -> session_data
        """
        return self._memory_sessions.copy()

    def cleanup_expired_redis_sessions(self) -> int:
        """
        清理 Redis 中的过期会话元数据

        Returns:
            int: 清理的会话数量
        """
        if not self.redis:
            return 0

        try:
            # 扫描所有该平台的会话
            pattern = f"{self._redis_prefix}*"
            keys = []
            for key in self.redis.scan_iter(match=pattern):
                keys.append(key)

            cleaned = 0
            for key in keys:
                # Redis 的 SETEX 会自动过期，这里只是统计
                if not self.redis.exists(key):
                    cleaned += 1

            if cleaned > 0:
                logger.info(f"[{self.platform_name}] Cleaned {cleaned} expired Redis sessions")

            return cleaned
        except Exception as e:
            logger.error(f"[{self.platform_name}] Failed to cleanup Redis sessions: {e}")
            return 0


# 为各平台创建单例实例
douyin_session_manager = SessionManager("douyin")
kuaishou_session_manager = SessionManager("kuaishou")
tencent_session_manager = SessionManager("tencent")
xiaohongshu_session_manager = SessionManager("xiaohongshu")
