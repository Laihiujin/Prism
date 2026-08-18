"""
速率限制器 - 控制API调用频率

功能:
1. 平台级别限流
2. 账号级别限流
3. 令牌桶算法实现
4. 异步支持
"""

import asyncio
import time
from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict


class TokenBucket:
    """
    令牌桶算法实现
    
    原理:
    - 桶以固定速率生成令牌
    - 每次请求消耗1个令牌
    - 桶满时停止生成令牌
    - 无令牌时请求被限流
    """
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        初始化令牌桶
        
        Args:
            capacity: 桶容量（最大令牌数）
            refill_rate: 令牌生成速率（个/秒）
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def _refill(self):
        """补充令牌"""
        now = time.time()
        elapsed = now - self.last_refill
        
        # 计算应该生成的令牌数
        new_tokens = elapsed * self.refill_rate
        
        if new_tokens > 0:
            self.tokens = min(self.capacity, self.tokens + new_tokens)
            self.last_refill = now
    
    async def consume(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """
        消cost 令牌
        
        Args:
            tokens: 需要消耗的令牌数
            timeout: 超时时间（秒），None表示无限等待
        
        Returns:
            是否成功消耗令牌
        """
        start_time = time.time()
        
        while True:
            async with self._lock:
                await self._refill()
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
            
            # 检查超时
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False
            
            # 等待一小段时间后重试
            await asyncio.sleep(0.1)
    
    async def get_available_tokens(self) -> float:
        """获取当前可用令牌数"""
        async with self._lock:
            await self._refill()
            return self.tokens


class RateLimiter:
    """
    速率限制器
    
    支持:
    - 平台级别限流（全局）
    - 账号级别限流（细粒度）
    - 自定义限流规则
    """
    
    # 平台限流配置（请求/分钟）
    PLATFORM_LIMITS = {
        "douyin": {
            "requests_per_minute": 3,
            "min_interval_seconds": 20
        },
        "kuaishou": {
            "requests_per_minute": 2,
            "min_interval_seconds": 30
        },
        "xiaohongshu": {
            "requests_per_minute": 2,
            "min_interval_seconds": 30
        },
        "channels": {
            "requests_per_minute": 1,
            "min_interval_seconds": 60
        },
        "bilibili": {
            "requests_per_minute": 2,
            "min_interval_seconds": 30
        }
    }
    
    def __init__(self):
        """初始化速率限制器"""
        self.platform_buckets: Dict[str, TokenBucket] = {}
        self.account_buckets: Dict[str, TokenBucket] = {}
        self.last_request_time: Dict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()
        
        # 初始化平台级别令牌桶
        for platform, config in self.PLATFORM_LIMITS.items():
            capacity = config["requests_per_minute"]
            refill_rate = capacity / 60  # 每秒生成的令牌数
            self.platform_buckets[platform] = TokenBucket(capacity, refill_rate)
    
    async def acquire(
        self,
        platform: str,
        account_id: Optional[str] = None,
        timeout: Optional[float] = 30
    ) -> bool:
        """
        获取执行许可
        
        Args:
            platform: 平台名称
            account_id: 账号ID（可选，用于账号级别限流）
            timeout: 超时时间（秒）
        
        Returns:
            是否获得许可
        """
        # 1. 检查平台级别限流
        platform_bucket = self.platform_buckets.get(platform)
        if not platform_bucket:
            print(f"⚠️ [RateLimiter] 未知平台: {platform}，跳过限流")
            return True
        
        # 2. 检查最小时间间隔
        key = f"{platform}_{account_id}" if account_id else platform
        now = time.time()
        
        async with self._lock:
            last_time = self.last_request_time.get(key, 0)
            min_interval = self.PLATFORM_LIMITS[platform]["min_interval_seconds"]
            
            wait_time = min_interval - (now - last_time)
            if wait_time > 0:
                print(f"⏳ [RateLimiter] {key} 需要等待 {wait_time:.1f}秒")
                await asyncio.sleep(wait_time)
        
        # 3. 消耗平台令牌
        success = await platform_bucket.consume(tokens=1, timeout=timeout)
        
        if not success:
            print(f"❌ [RateLimiter] {platform} 限流超时")
            return False
        
        # 4. 更新最后请求时间
        async with self._lock:
            self.last_request_time[key] = time.time()
        
        print(f"✅ [RateLimiter] {key} 获得执行许可")
        return True
    
    async def get_platform_status(self, platform: str) -> Dict:
        """
        获取平台限流状态
        
        Args:
            platform: 平台名称
        
        Returns:
            状态信息
        """
        bucket = self.platform_buckets.get(platform)
        if not bucket:
            return {"error": "未知平台"}
        
        available = await bucket.get_available_tokens()
        config = self.PLATFORM_LIMITS[platform]
        
        return {
            "platform": platform,
            "available_tokens": round(available, 2),
            "capacity": config["requests_per_minute"],
            "min_interval_seconds": config["min_interval_seconds"],
            "last_request": self.last_request_time.get(platform, 0)
        }
    
    async def reset_platform(self, platform: str):
        """
        重置平台限流状态
        
        Args:
            platform: 平台名称
        """
        if platform in self.platform_buckets:
            config = self.PLATFORM_LIMITS[platform]
            capacity = config["requests_per_minute"]
            refill_rate = capacity / 60
            self.platform_buckets[platform] = TokenBucket(capacity, refill_rate)
            
            # 清除时间记录
            keys_to_remove = [k for k in self.last_request_time.keys() if k.startswith(platform)]
            for key in keys_to_remove:
                del self.last_request_time[key]
            
            print(f"🔄 [RateLimiter] 已重置平台限流: {platform}")


# 全局限流器实例
_rate_limiter_instance: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    获取全局限流器实例（单例模式）
    
    Returns:
        RateLimiter实例
    """
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = RateLimiter()
    return _rate_limiter_instance
