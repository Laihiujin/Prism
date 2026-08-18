"""
Platform Adapter Base Class - 平台适配器抽象基类

定义所有平台必须实现的接口
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class LoginStatus(Enum):
    """登录状态"""
    WAITING = "waiting"           # 等待扫码
    SCANNED = "scanned"           # 已扫码
    CONFIRMED = "confirmed"       # 已确认/登录成功
    FAILED = "failed"             # 登录失败
    EXPIRED = "expired"           # 二维码过期


@dataclass
class QRCodeData:
    """二维码数据"""
    session_id: str               # 会话ID (token/qrcode_key)
    qr_url: str                   # 二维码URL
    qr_image: str                 # base64图片 (data:image/png;base64,...)
    expires_in: int = 300         # 过期时间(秒)


@dataclass
class UserInfo:
    """用户信息"""
    user_id: Optional[str] = None
    name: Optional[str] = None
    username: Optional[str] = None
    avatar: Optional[str] = None
    # 平台特定字段
    extra: Optional[Dict[str, Any]] = None


@dataclass
class LoginResult:
    """登录结果"""
    status: LoginStatus
    message: str = ""
    cookies: Optional[Dict[str, Any]] = None
    user_info: Optional[UserInfo] = None
    full_state: Optional[Dict[str, Any]] = None  # Playwright storage_state


class PlatformAdapter(ABC):
    """平台适配器抽象基类"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.platform_name: str = "unknown"

    @abstractmethod
    async def get_qrcode(self) -> QRCodeData:
        """
        生成登录二维码

        Returns:
            QRCodeData: 二维码数据 (session_id, qr_url, qr_image)
        """
        pass

    @abstractmethod
    async def poll_status(self, session_id: str) -> LoginResult:
        """
        轮询登录状态

        Args:
            session_id: 会话ID (从get_qrcode返回)

        Returns:
            LoginResult: 登录结果 (status, cookies, user_info)
        """
        pass

    @abstractmethod
    async def cleanup_session(self, session_id: str):
        """
        清理会话 (关闭浏览器等资源)

        Args:
            session_id: 会话ID
        """
        pass

    async def supports_api_login(self) -> bool:
        """是否支持纯API登录 (无需Playwright)"""
        return False
