from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from .schemas import PlatformType

try:
    from config.conf import PLAYWRIGHT_HEADLESS
except Exception:
    PLAYWRIGHT_HEADLESS = True


def get_adapter_config() -> Dict[str, Any]:
    return {"headless": PLAYWRIGHT_HEADLESS}


def _load_adapter(platform: PlatformType):
    module_name = {
        PlatformType.BILIBILI: "app_new.platforms.bilibili",
        PlatformType.DOUYIN: "app_new.platforms.douyin",
        PlatformType.KUAISHOU: "app_new.platforms.kuaishou",
        PlatformType.XIAOHONGSHU: "app_new.platforms.xiaohongshu",
        PlatformType.TENCENT: "app_new.platforms.tencent",
    }[platform]
    class_name = {
        PlatformType.BILIBILI: "BilibiliAdapter",
        PlatformType.DOUYIN: "DouyinAdapter",
        PlatformType.KUAISHOU: "KuaishouAdapter",
        PlatformType.XIAOHONGSHU: "XiaohongshuAdapter",
        PlatformType.TENCENT: "TencentAdapter",
    }[platform]
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def _confirmed_status():
    base_module = importlib.import_module("app_new.platforms.base")
    return getattr(base_module, "LoginStatus").CONFIRMED


class BilibiliLoginServiceV2:
    @staticmethod
    async def get_qrcode() -> Tuple[str, str, str]:
        adapter = _load_adapter(PlatformType.BILIBILI)(get_adapter_config())
        qr_data = await adapter.get_qrcode()
        return qr_data.session_id, qr_data.qr_url, qr_data.qr_image

    @staticmethod
    async def poll_status(session_id: str) -> Dict[str, Any]:
        adapter = _load_adapter(PlatformType.BILIBILI)(get_adapter_config())
        result = await adapter.poll_status(session_id)
        response = {"status": result.status.value, "message": result.message}
        if result.status == _confirmed_status():
            response["data"] = {
                "cookies": result.cookies,
                "user_info": {
                    "user_id": result.user_info.user_id or "",
                    "username": result.user_info.username or result.user_info.name or "",
                    "name": result.user_info.name or "",
                    "avatar": result.user_info.avatar or "",
                },
            }
        return response

    @staticmethod
    async def supports_api_login() -> bool:
        return True

    @staticmethod
    def get_sse_type() -> None:
        return None


class DouyinLoginServiceV2:
    @staticmethod
    async def get_qrcode() -> Tuple[str, str, str]:
        adapter = _load_adapter(PlatformType.DOUYIN)(get_adapter_config())
        qr_data = await adapter.get_qrcode()
        return qr_data.session_id, qr_data.qr_url, qr_data.qr_image

    @staticmethod
    async def poll_status(session_id: str) -> Dict[str, Any]:
        adapter = _load_adapter(PlatformType.DOUYIN)(get_adapter_config())
        result = await adapter.poll_status(session_id)
        response = {"status": result.status.value, "message": result.message}
        if result.status == _confirmed_status():
            response["data"] = {
                "cookies": result.cookies,
                "user_info": {
                    "user_id": result.user_info.user_id or "",
                    "username": result.user_info.username or result.user_info.name or "",
                    "name": result.user_info.name or "",
                    "avatar": result.user_info.avatar or "",
                },
                "full_state": result.full_state,
            }
        return response

    @staticmethod
    async def supports_api_login() -> bool:
        return True

    @staticmethod
    def get_sse_type() -> None:
        return None


class KuaishouLoginServiceV2:
    @staticmethod
    async def get_qrcode() -> Tuple[str, str, str]:
        adapter = _load_adapter(PlatformType.KUAISHOU)(get_adapter_config())
        qr_data = await adapter.get_qrcode()
        return qr_data.session_id, qr_data.qr_url, qr_data.qr_image

    @staticmethod
    async def poll_status(session_id: str) -> Dict[str, Any]:
        adapter = _load_adapter(PlatformType.KUAISHOU)(get_adapter_config())
        result = await adapter.poll_status(session_id)
        response = {"status": result.status.value, "message": result.message}
        if result.status == _confirmed_status():
            response["data"] = {
                "cookies": result.cookies,
                "user_info": {
                    "user_id": result.user_info.user_id or "",
                    "username": result.user_info.username or result.user_info.name or "",
                    "name": result.user_info.name or "",
                    "avatar": result.user_info.avatar or "",
                },
                "full_state": result.full_state,
            }
        return response

    @staticmethod
    async def supports_api_login() -> bool:
        return True

    @staticmethod
    def get_sse_type() -> None:
        return None


class XiaohongshuLoginServiceV2:
    @staticmethod
    async def get_qrcode() -> Tuple[str, str, str]:
        adapter = _load_adapter(PlatformType.XIAOHONGSHU)(get_adapter_config())
        qr_data = await adapter.get_qrcode()
        return qr_data.session_id, qr_data.qr_url, qr_data.qr_image

    @staticmethod
    async def poll_status(session_id: str) -> Dict[str, Any]:
        adapter = _load_adapter(PlatformType.XIAOHONGSHU)(get_adapter_config())
        result = await adapter.poll_status(session_id)
        response = {"status": result.status.value, "message": result.message}
        if result.status == _confirmed_status():
            response["data"] = {
                "cookie": result.cookies.get("cookie", "") if result.cookies else "",
                "login_info": {
                    "user_id": result.user_info.user_id or "",
                    "name": result.user_info.name or "",
                    "avatar": result.user_info.avatar or "",
                },
                "full_state": result.full_state,
            }
        return response

    @staticmethod
    async def supports_api_login() -> bool:
        return True

    @staticmethod
    def get_sse_type() -> None:
        return None


class TencentLoginServiceV2:
    @staticmethod
    async def get_qrcode() -> Tuple[str, str, str]:
        adapter = _load_adapter(PlatformType.TENCENT)(get_adapter_config())
        qr_data = await adapter.get_qrcode()
        return qr_data.session_id, qr_data.qr_url, qr_data.qr_image

    @staticmethod
    async def poll_status(session_id: str) -> Dict[str, Any]:
        adapter = _load_adapter(PlatformType.TENCENT)(get_adapter_config())
        result = await adapter.poll_status(session_id)
        response = {"status": result.status.value, "message": result.message}
        if result.status == _confirmed_status():
            user_info_data = {
                "user_id": result.user_info.user_id or "",
                "name": result.user_info.name or "",
                "avatar": result.user_info.avatar or "",
            }
            if result.user_info.extra and "finder_username" in result.user_info.extra:
                user_info_data["finder_username"] = result.user_info.extra["finder_username"]
            response["data"] = {
                "cookies": result.cookies,
                "user_info": user_info_data,
                "full_state": result.full_state,
            }
        return response

    @staticmethod
    async def supports_api_login() -> bool:
        return True

    @staticmethod
    def get_sse_type() -> None:
        return None


def get_login_service_v2(platform: PlatformType):
    service_map = {
        PlatformType.BILIBILI: BilibiliLoginServiceV2,
        PlatformType.XIAOHONGSHU: XiaohongshuLoginServiceV2,
        PlatformType.DOUYIN: DouyinLoginServiceV2,
        PlatformType.KUAISHOU: KuaishouLoginServiceV2,
        PlatformType.TENCENT: TencentLoginServiceV2,
    }
    return service_map[platform]
