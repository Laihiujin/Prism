"""
通用验证码处理模块
支持各平台在登录、发布等场景下的短信/图形验证码处理
"""
import asyncio
import logging
from queue import Queue, Empty
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class VerificationManager:
    """验证码管理器 - 统一处理各平台的验证码验证流程"""

    def __init__(self):
        self.otp_events = []  # 待处理的验证码事件列表
        self.input_queues: Dict[str, Queue] = {}  # 账号ID -> 验证码输入队列

    def request_verification(self,
                           account_id: str,
                           platform: int,
                           message: str = "请输入验证码",
                           code_length: int = 6) -> Dict[str, Any]:
        """
        发起验证码请求，通知前端弹窗

        Args:
            account_id: 账号ID（用于区分不同的验证请求）
            platform: 平台代码 (1=小红书, 2=视频号, 3=抖音, 4=快手, 5=B站)
            message: 提示信息
            code_length: 验证码长度

        Returns:
            事件对象
        """
        event = {
            "id": account_id,
            "platform": platform,
            "account": account_id,
            "message": message,
            "code_length": code_length,
            "timestamp": datetime.now().isoformat()
        }
        self.otp_events.append(event)

        # 确保该账号有对应的输入队列
        if account_id not in self.input_queues:
            self.input_queues[account_id] = Queue()

        logger.info(f"[Verification] Verification request initiated: {account_id} (platform={platform})")
        return event

    async def wait_for_code(self,
                           account_id: str,
                           timeout: int = 120) -> Optional[str]:
        """
        等待用户输入验证码（阻塞式）

        Args:
            account_id: 账号ID
            timeout: 超时时间（秒）

        Returns:
            验证码字符串，超时返回 None
        """
        logger.info(f"[Verification] Waiting for code: {account_id} (timeout={timeout}s)")

        for _ in range(timeout):
            if account_id in self.input_queues:
                try:
                    code = self.input_queues[account_id].get(block=False)
                    logger.info(f"[Verification] Code received: {account_id} -> {code}")
                    return code
                except Empty:
                    pass
            await asyncio.sleep(1)

        logger.warning(f"[Verification] Code timeout: {account_id}")
        return None

    def submit_code(self, account_id: str, code: str) -> bool:
        """
        前端提交验证码（通过 /api/v1/verification/submit-code 调用）

        Args:
            account_id: 账号ID
            code: 验证码

        Returns:
            是否成功提交
        """
        if account_id not in self.input_queues:
            self.input_queues[account_id] = Queue()

        self.input_queues[account_id].put(code)
        logger.info(f"[Verification] Code submitted: {account_id}")
        return True

    def get_pending_events(self) -> list:
        """
        获取待处理的验证码事件（前端轮询接口调用）

        Returns:
            事件列表（获取后清空）
        """
        events = self.otp_events[:]
        self.otp_events = []
        return events

    def cleanup_queue(self, account_id: str):
        """清理指定账号的验证码队列"""
        if account_id in self.input_queues:
            del self.input_queues[account_id]
            logger.debug(f"[Verification] Queue cleaned: {account_id}")


# 全局单例
verification_manager = VerificationManager()
