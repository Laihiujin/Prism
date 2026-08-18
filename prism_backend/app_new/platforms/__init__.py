"""
Platform Adapters - 平台适配器模块

每个平台的登录、二维码、用户信息提取逻辑的独立实现
"""

from .base import PlatformAdapter, LoginResult, QRCodeData, UserInfo, LoginStatus
from .bilibili import BilibiliAdapter
from .douyin import DouyinAdapter
from .kuaishou import KuaishouAdapter
from .xiaohongshu import XiaohongshuAdapter
from .tencent import TencentAdapter

__all__ = [
    "PlatformAdapter",
    "LoginResult",
    "QRCodeData",
    "UserInfo",
    "LoginStatus",
    "BilibiliAdapter",
    "DouyinAdapter",
    "KuaishouAdapter",
    "XiaohongshuAdapter",
    "TencentAdapter",
]
