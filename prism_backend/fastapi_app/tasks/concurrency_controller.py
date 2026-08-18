"""
分布式并发控制器
基于 Redis 实现动态并发控制，支持多维度限流
"""
from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from typing import Optional, Dict, Any
from loguru import logger

from fastapi_app.cache.redis_client import get_redis


class ConcurrencyController:
    """分布式并发控制器"""

    def __init__(self):
        self.redis = get_redis()
        self.config_key = "concurrency:config"
        self.semaphore_prefix = "concurrency:semaphore:"
        self.stats_prefix = "concurrency:stats:"

    def _get_config(self) -> Dict[str, Any]:
        """获取并发控制配置"""
        if not self.redis:
            return self._default_config()

        try:
            config_json = self.redis.get(self.config_key)
            if config_json:
                import json
                return json.loads(config_json)
        except Exception as e:
            logger.error(f"[Concurrency] Failed to get config: {e}")

        return self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        """默认配置"""
        return {
            "global_max": 0,            # 全局并发无限制（0表示不限制）
            "platform_max": {           # 平台级并发无限制（所有平台都设为0）
                "douyin": 0,            # 抖音不限制
                "xiaohongshu": 0,       # 小红书不限制
                "kuaishou": 0,
                "bilibili": 0,
                "channels": 0
            },
            "account_max": 0,           # 每个账号最大1个并发（防止同账号冲突）
            "task_type_max": {          # 任务类型级并发无限制
                "publish": 0,           # 发布任务不限制
                "batch_publish": 0      # 批量发布任务不限制
            },
            "enabled": True,            # 是否启用并发控制
            "timeout": 300              # 令牌超时时间（秒）
        }

    def update_config(self, config: Dict[str, Any]) -> bool:
        """更新并发控制配置"""
        if not self.redis:
            return False

        try:
            import json
            self.redis.set(
                self.config_key,
                json.dumps(config, ensure_ascii=False),
                ex=86400 * 30  # 配置保存30天
            )
            logger.info(f"[Concurrency] Config updated: {config}")
            return True
        except Exception as e:
            logger.error(f"[Concurrency] Failed to update config: {e}")
            return False

    @contextmanager
    def acquire(
        self,
        platform: Optional[str] = None,
        account_id: Optional[str] = None,
        task_type: str = "publish",
        timeout: Optional[int] = None
    ):
        """
        获取并发令牌（上下文管理器）

        Args:
            platform: 平台名称（douyin, xiaohongshu等）
            account_id: 账号ID
            task_type: 任务类型
            timeout: 超时时间（秒），None 表示使用配置中的默认值

        Yields:
            bool: 是否成功获取令牌

        Usage:
            with concurrency_controller.acquire(platform="douyin", account_id="123"):
                # 执行任务
                pass
        """
        config = self._get_config()

        # 如果未启用并发控制，直接放行
        if not config.get("enabled", True):
            yield True
            return

        if not self.redis:
            logger.warning("[Concurrency] Redis not available, skipping concurrency control")
            yield True
            return

        timeout = timeout or config.get("timeout", 300)
        token = str(uuid.uuid4())
        acquired_locks = []

        try:
            # 1. 尝试获取全局并发令牌（0表示无限制）
            global_max = config.get("global_max", 0)
            if global_max > 0:  # 只有大于0才进行限制
                if not self._acquire_semaphore("global", global_max, token, timeout):
                    logger.warning(f"[Concurrency] Global limit reached ({global_max}), waiting...")
                    # 等待获取
                    if not self._wait_and_acquire("global", global_max, token, timeout, max_wait=30):
                        raise ConcurrencyLimitException("全局并发限制，请稍后重试")
                acquired_locks.append(("global", token))
            else:
                logger.debug("[Concurrency] Global concurrency unlimited (global_max=0)")

            # 2. 尝试获取平台级别令牌
            if platform:
                platform_max = config.get("platform_max", {}).get(platform, 0)
                if platform_max > 0:  # 只有大于0才进行限制
                    semaphore_key = f"platform:{platform}"
                    if not self._acquire_semaphore(semaphore_key, platform_max, token, timeout):
                        logger.warning(f"[Concurrency] Platform {platform} limit reached ({platform_max}), waiting...")
                        if not self._wait_and_acquire(semaphore_key, platform_max, token, timeout, max_wait=30):
                            raise ConcurrencyLimitException(f"平台 {platform} 并发限制，请稍后重试")
                    acquired_locks.append((semaphore_key, token))

            # 3. 尝试获取账号级别令牌（最严格）
            if account_id:
                account_max = config.get("account_max", 1)
                if account_max > 0:  # 只有大于0才进行限制
                    semaphore_key = f"account:{account_id}"
                    if not self._acquire_semaphore(semaphore_key, account_max, token, timeout):
                        logger.warning(f"[Concurrency] Account {account_id} is busy, waiting...")
                        if not self._wait_and_acquire(semaphore_key, account_max, token, timeout, max_wait=60):
                            raise ConcurrencyLimitException(f"账号 {account_id} 正在执行任务，请稍后重试")
                    acquired_locks.append((semaphore_key, token))

            # 4. 尝试获取任务类型令牌
            if task_type:
                task_type_max = config.get("task_type_max", {}).get(task_type, 0)
                if task_type_max > 0:  # 只有大于0才进行限制
                    semaphore_key = f"task_type:{task_type}"
                    if not self._acquire_semaphore(semaphore_key, task_type_max, token, timeout):
                        logger.warning(f"[Concurrency] Task type {task_type} limit reached ({task_type_max})")
                        if not self._wait_and_acquire(semaphore_key, task_type_max, token, timeout, max_wait=30):
                            raise ConcurrencyLimitException(f"任务类型 {task_type} 并发限制")
                    acquired_locks.append((semaphore_key, token))

            # 记录统计信息
            self._record_stats(platform, account_id, task_type, "acquired")

            logger.debug(f"[Concurrency] Acquired locks: {acquired_locks}")
            yield True

        except ConcurrencyLimitException:
            raise
        except Exception as e:
            logger.error(f"[Concurrency] Acquire error: {e}")
            raise
        finally:
            # 释放所有已获取的令牌
            for semaphore_key, token in acquired_locks:
                self._release_semaphore(semaphore_key, token)

            # 记录统计信息
            if acquired_locks:
                self._record_stats(platform, account_id, task_type, "released")

    def _acquire_semaphore(self, key: str, max_count: int, token: str, timeout: int) -> bool:
        """
        尝试获取信号量令牌

        Args:
            key: 信号量键
            max_count: 最大并发数
            token: 令牌ID
            timeout: 超时时间

        Returns:
            bool: 是否成功获取
        """
        semaphore_key = f"{self.semaphore_prefix}{key}"
        now = time.time()
        expire_time = now + timeout

        try:
            # 清理过期的令牌
            self.redis.zremrangebyscore(semaphore_key, 0, now)

            # 尝试添加令牌
            current_count = self.redis.zcard(semaphore_key)
            if current_count < max_count:
                self.redis.zadd(semaphore_key, {token: expire_time})
                self.redis.expire(semaphore_key, timeout + 60)  # 额外60秒确保清理
                logger.debug(f"[Concurrency] Acquired {key}: {current_count + 1}/{max_count}")
                return True

            return False
        except Exception as e:
            logger.error(f"[Concurrency] Acquire semaphore error: {e}")
            return False

    def _wait_and_acquire(
        self,
        key: str,
        max_count: int,
        token: str,
        timeout: int,
        max_wait: int = 30,
        poll_interval: float = 0.5
    ) -> bool:
        """
        等待并获取信号量令牌

        Args:
            key: 信号量键
            max_count: 最大并发数
            token: 令牌ID
            timeout: 令牌超时时间
            max_wait: 最大等待时间（秒）
            poll_interval: 轮询间隔（秒）

        Returns:
            bool: 是否成功获取
        """
        start_time = time.time()
        while time.time() - start_time < max_wait:
            if self._acquire_semaphore(key, max_count, token, timeout):
                return True
            time.sleep(poll_interval)

        return False

    def _release_semaphore(self, key: str, token: str):
        """释放信号量令牌"""
        semaphore_key = f"{self.semaphore_prefix}{key}"
        try:
            removed = self.redis.zrem(semaphore_key, token)
            if removed:
                logger.debug(f"[Concurrency] Released {key}")
        except Exception as e:
            logger.error(f"[Concurrency] Release semaphore error: {e}")

    def _record_stats(
        self,
        platform: Optional[str],
        account_id: Optional[str],
        task_type: str,
        action: str
    ):
        """记录并发统计信息"""
        try:
            stats_key = f"{self.stats_prefix}counters"
            self.redis.hincrby(stats_key, f"{action}:total", 1)

            if platform:
                self.redis.hincrby(stats_key, f"{action}:platform:{platform}", 1)

            if task_type:
                self.redis.hincrby(stats_key, f"{action}:task_type:{task_type}", 1)

            # 设置过期时间
            self.redis.expire(stats_key, 86400)  # 保存24小时
        except Exception as e:
            logger.error(f"[Concurrency] Record stats error: {e}")

    def get_current_usage(self) -> Dict[str, Any]:
        """获取当前并发使用情况"""
        if not self.redis:
            return {}

        config = self._get_config()
        now = time.time()
        usage = {
            "global": {
                "current": 0,
                "max": config.get("global_max", 10)
            },
            "platforms": {},
            "task_types": {}
        }

        try:
            # 全局使用量
            global_key = f"{self.semaphore_prefix}global"
            self.redis.zremrangebyscore(global_key, 0, now)
            usage["global"]["current"] = self.redis.zcard(global_key)

            # 平台使用量
            for platform, max_count in config.get("platform_max", {}).items():
                platform_key = f"{self.semaphore_prefix}platform:{platform}"
                self.redis.zremrangebyscore(platform_key, 0, now)
                usage["platforms"][platform] = {
                    "current": self.redis.zcard(platform_key),
                    "max": max_count
                }

            # 任务类型使用量
            for task_type, max_count in config.get("task_type_max", {}).items():
                task_type_key = f"{self.semaphore_prefix}task_type:{task_type}"
                self.redis.zremrangebyscore(task_type_key, 0, now)
                usage["task_types"][task_type] = {
                    "current": self.redis.zcard(task_type_key),
                    "max": max_count
                }

            return usage
        except Exception as e:
            logger.error(f"[Concurrency] Get usage error: {e}")
            return usage

    def get_stats(self) -> Dict[str, Any]:
        """获取并发统计信息"""
        if not self.redis:
            return {}

        try:
            stats_key = f"{self.stats_prefix}counters"
            counters = self.redis.hgetall(stats_key)
            return {k: int(v) for k, v in counters.items()}
        except Exception as e:
            logger.error(f"[Concurrency] Get stats error: {e}")
            return {}


class ConcurrencyLimitException(Exception):
    """并发限制异常"""
    pass


# 全局单例
concurrency_controller = ConcurrencyController()
