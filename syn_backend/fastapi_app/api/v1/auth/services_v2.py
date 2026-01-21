"""
新版登录服务 - 桥接层
将 app_new.platforms 适配器桥接到现有 API 接口

此文件将逐步替换 services.py 中的实现
"""
import sys
from pathlib import Path
from typing import Tuple, Dict, Any

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app_new.platforms import (
    BilibiliAdapter,
    DouyinAdapter,
    KuaishouAdapter,
    XiaohongshuAdapter,
    TencentAdapter,
    LoginStatus
)
from .schemas import PlatformType

try:
    from config.conf import PLAYWRIGHT_HEADLESS
except Exception:
    PLAYWRIGHT_HEADLESS = True


def get_adapter_config() -> Dict[str, Any]:
    """获取适配器配置"""
    return {
        "headless": PLAYWRIGHT_HEADLESS
    }


class BilibiliLoginServiceV2:
    """B站登录服务 V2 (使用新适配器)"""

    @staticmethod
    async def get_qrcode() -> Tuple[str, str, str]:
        """
        生成二维码
        Returns: (session_id, qr_url, qr_image)
        """
        adapter = BilibiliAdapter(get_adapter_config())
        qr_data = await adapter.get_qrcode()
        return qr_data.session_id, qr_data.qr_url, qr_data.qr_image

    @staticmethod
    async def poll_status(session_id: str) -> Dict[str, Any]:
        """
        轮询登录状态
        Returns: {"status": "waiting|scanned|confirmed|expired|failed", "data": {...}}
        """
        adapter = BilibiliAdapter(get_adapter_config())
        result = await adapter.poll_status(session_id)

        response = {
            "status": result.status.value,
            "message": result.message
        }

        if result.status == LoginStatus.CONFIRMED:
            response["data"] = {
                "cookies": result.cookies,
                "user_info": {
                    "user_id": result.user_info.user_id or "",
                    "username": result.user_info.username or result.user_info.name or "",
                    "name": result.user_info.name or "",
                    "avatar": result.user_info.avatar or ""
                }
            }

        return response

    @staticmethod
    async def supports_api_login() -> bool:
        return True

    @staticmethod
    def get_sse_type() -> None:
        return None


class DouyinLoginServiceV2:
    """抖音登录服务 V2 (使用新适配器)"""

    @staticmethod
    async def get_qrcode() -> Tuple[str, str, str]:
        adapter = DouyinAdapter(get_adapter_config())
        qr_data = await adapter.get_qrcode()
        return qr_data.session_id, qr_data.qr_url, qr_data.qr_image

    @staticmethod
    async def poll_status(session_id: str) -> Dict[str, Any]:
        adapter = DouyinAdapter(get_adapter_config())
        result = await adapter.poll_status(session_id)

        response = {
            "status": result.status.value,
            "message": result.message
        }

        if result.status == LoginStatus.CONFIRMED:
            response["data"] = {
                "cookies": result.cookies,
                "user_info": {
                    "user_id": result.user_info.user_id or "",
                    "username": result.user_info.username or result.user_info.name or "",
                    "name": result.user_info.name or "",
                    "avatar": result.user_info.avatar or ""
                },
                "full_state": result.full_state
            }

        return response

    @staticmethod
    async def supports_api_login() -> bool:
        return True

    @staticmethod
    def get_sse_type() -> None:
        return None


class KuaishouLoginServiceV2:
    """快手登录服务 V2 (使用新适配器)"""

    @staticmethod
    async def get_qrcode() -> Tuple[str, str, str]:
        adapter = KuaishouAdapter(get_adapter_config())
        qr_data = await adapter.get_qrcode()
        return qr_data.session_id, qr_data.qr_url, qr_data.qr_image

    @staticmethod
    async def poll_status(session_id: str) -> Dict[str, Any]:
        adapter = KuaishouAdapter(get_adapter_config())
        result = await adapter.poll_status(session_id)

        response = {
            "status": result.status.value,
            "message": result.message
        }

        if result.status == LoginStatus.CONFIRMED:
            response["data"] = {
                "cookies": result.cookies,
                "user_info": {
                    "user_id": result.user_info.user_id or "",
                    "username": result.user_info.username or result.user_info.name or "",
                    "name": result.user_info.name or "",
                    "avatar": result.user_info.avatar or ""
                },
                "full_state": result.full_state
            }

        return response

    @staticmethod
    async def supports_api_login() -> bool:
        return True

    @staticmethod
    def get_sse_type() -> None:
        return None


class XiaohongshuLoginServiceV2:
    """小红书登录服务 V2 (使用新适配器)"""

    @staticmethod
    async def get_qrcode() -> Tuple[str, str, str]:
        adapter = XiaohongshuAdapter(get_adapter_config())
        qr_data = await adapter.get_qrcode()
        return qr_data.session_id, qr_data.qr_url, qr_data.qr_image

    @staticmethod
    async def poll_status(session_id: str) -> Dict[str, Any]:
        adapter = XiaohongshuAdapter(get_adapter_config())
        result = await adapter.poll_status(session_id)

        response = {
            "status": result.status.value,
            "message": result.message
        }

        if result.status == LoginStatus.CONFIRMED:
            # 小红书返回cookie字符串
            response["data"] = {
                "cookie": result.cookies.get("cookie", "") if result.cookies else "",
                "login_info": {
                    "user_id": result.user_info.user_id or "",
                    "name": result.user_info.name or "",
                    "avatar": result.user_info.avatar or ""
                },
                "full_state": result.full_state
            }

        return response

    @staticmethod
    async def supports_api_login() -> bool:
        return True

    @staticmethod
    def get_sse_type() -> None:
        return None


class TencentLoginServiceV2:
    """视频号登录服务 V2 (使用新适配器)"""

    @staticmethod
    async def get_qrcode() -> Tuple[str, str, str]:
        adapter = TencentAdapter(get_adapter_config())
        qr_data = await adapter.get_qrcode()
        return qr_data.session_id, qr_data.qr_url, qr_data.qr_image

    @staticmethod
    async def poll_status(session_id: str) -> Dict[str, Any]:
        adapter = TencentAdapter(get_adapter_config())
        result = await adapter.poll_status(session_id)

        response = {
            "status": result.status.value,
            "message": result.message
        }

        if result.status == LoginStatus.CONFIRMED:
            user_info_data = {
                "user_id": result.user_info.user_id or "",
                "name": result.user_info.name or "",
                "avatar": result.user_info.avatar or ""
            }
            # 添加 finder_username
            if result.user_info.extra and "finder_username" in result.user_info.extra:
                user_info_data["finder_username"] = result.user_info.extra["finder_username"]

            response["data"] = {
                "cookies": result.cookies,
                "user_info": user_info_data,
                "full_state": result.full_state
            }

        return response

    @staticmethod
    async def supports_api_login() -> bool:
        return True

    @staticmethod
    def get_sse_type() -> None:
        return None


# 统一获取服务函数 (V2版本)
def get_login_service_v2(platform: PlatformType):
    """
    获取登录服务 V2 (使用新适配器)
    """
    service_map = {
        PlatformType.BILIBILI: BilibiliLoginServiceV2,
        PlatformType.XIAOHONGSHU: XiaohongshuLoginServiceV2,
        PlatformType.DOUYIN: DouyinLoginServiceV2,
        PlatformType.KUAISHOU: KuaishouLoginServiceV2,
        PlatformType.TENCENT: TencentLoginServiceV2,
    }
    return service_map[platform]
