"""
平台注册表（统一入口，单一事实来源）

本模块是 Prism 所有「平台」相关映射的**唯一权威来源**：
    平台代码 int  →  平台名 / 别名 / 登录与发布 URL / 上传实现

任何需要「平台别名 → 平台代码」或「平台代码 → 上传器」的地方，都应
从这里获取，避免各处散落硬编码（原先是 login / uploader / 前端各自
维护一份编码映射，极易出现 6/7 显示成裸数字这类问题）。

发布链路只依赖 `get_uploader_by_platform_code(platform_code)` 获得
平台适配器（platform layer）；`platforms/*` 是新一代实现，旧的
`uploader/*` 逐步迁移到 `platforms/*`。

注意（见 AGENTS.md）：生产登录**必须走浏览器模式**，不要在这里或
上传器里引入 HTTP 逆向登录。本模块只负责映射，不负责登录。
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, List, Optional, Protocol


class PlatformUploader(Protocol):
    platform_code: int
    platform_name: str

    async def upload(
        self,
        account_file: str,
        title: str,
        file_path: str,
        tags: list,
        **kwargs,
    ) -> Dict[str, Any]: ...


# 单一事实来源：平台代码 → 元信息。
# uploader = ("模块路径", "属性名")，指向 platforms/<platform>.upload 里的适配器。
_PLATFORM_META: dict[int, dict[str, Any]] = {
    1: {
        "name": "小红书",
        "aliases": ["xiaohongshu", "xhs", "redbook"],
        "login_url": "https://creator.xiaohongshu.com",
        "publish_url": "https://creator.xiaohongshu.com/publish/publish",
        "uploader": ("platforms.xiaohongshu.upload", "xiaohongshu_upload"),
    },
    2: {
        "name": "视频号",
        "aliases": ["tencent", "channels", "wechat"],
        "login_url": "https://channels.weixin.qq.com",
        "publish_url": "https://channels.weixin.qq.com/platform/post/create",
        "uploader": ("platforms.tencent.upload", "tencent_upload"),
    },
    3: {
        "name": "抖音",
        "aliases": ["douyin"],
        "login_url": "https://creator.douyin.com/creator-micro/login?enter_from=qr",
        "publish_url": "https://creator.douyin.com/creator-micro/content/upload",
        "uploader": ("platforms.douyin.upload", "douyin_upload"),
    },
    4: {
        "name": "快手",
        "aliases": ["kuaishou", "ks"],
        "login_url": "https://cp.kuaishou.com/profile",
        "publish_url": "https://cp.kuaishou.com/article/publish/video",
        "uploader": ("platforms.kuaishou.upload", "kuaishou_upload"),
    },
    5: {
        "name": "B站",
        "aliases": ["bilibili", "bili"],
        "login_url": "https://member.bilibili.com/platform/home",
        "publish_url": "https://member.bilibili.com/platform/upload/video/frame",
        "uploader": ("platforms.bilibili.upload", "bilibili_upload"),
    },
    6: {
        "name": "TikTok",
        "aliases": ["tiktok", "tk"],
        "login_url": "https://www.tiktok.com/login?lang=en",
        "publish_url": "https://www.tiktok.com/tiktokstudio/upload",
        "uploader": ("platforms.tiktok.upload", "tiktok_upload"),
    },
    7: {
        "name": "YouTube",
        "aliases": ["youtube", "yt"],
        "login_url": "https://studio.youtube.com",
        "publish_url": "https://studio.youtube.com",
        "uploader": ("platforms.youtube.upload", "youtube_upload"),
    },
    8: {
        "name": "百家号",
        "aliases": ["baijiahao", "baijia"],
        "login_url": "https://baijiahao.baidu.com/builder/theme/bjh/login",
        "publish_url": "https://baijiahao.baidu.com/builder/rc/edit?type=videoV2",
        "uploader": ("platforms.baijiahao.upload", "baijiahao_upload"),
    },
}

# 从 _PLATFORM_META 派生别名 → 代码 映射，避免两份列表漂移。
_ALIAS_TO_CODE: dict[str, int] = {
    alias: code for code, meta in _PLATFORM_META.items() for alias in meta["aliases"]
}

_uploaders_by_code: Dict[int, PlatformUploader] | None = None


def _build_registry() -> Dict[int, PlatformUploader]:
    registry: Dict[int, PlatformUploader] = {}
    for platform_code, meta in _PLATFORM_META.items():
        module_name, attr_name = meta["uploader"]
        module = importlib.import_module(module_name)
        registry[platform_code] = getattr(module, attr_name)
    return registry


def get_uploader_by_platform_code(platform_code: int) -> PlatformUploader:
    """按平台代码获取上传适配器。"""
    global _uploaders_by_code
    if _uploaders_by_code is None:
        _uploaders_by_code = _build_registry()
    if platform_code not in _uploaders_by_code:
        raise ValueError(f"Unsupported platform_code: {platform_code}")
    return _uploaders_by_code[platform_code]


def normalize_platform_code(value: Any) -> Optional[int]:
    """把任意平台标识（代码 / 别名 / 数字字符串）归一化为平台代码。

    支持:
    - int: 直接返回
    - 数字字符串 "6": 返回 6
    - 别名 "xhs" / "tiktok" / "channels": 返回对应代码
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        if not s:
            return None
        if s.isdigit():
            return int(s)
        return _ALIAS_TO_CODE.get(s)
    return None


def get_platform_meta(platform: Any) -> Optional[Dict[str, Any]]:
    """按代码或别名返回平台元信息（name / aliases / login_url / publish_url）。

    返回的 dict 是副本，调用方可安全修改而不会污染注册表。
    """
    code = normalize_platform_code(platform)
    if code is None or code not in _PLATFORM_META:
        return None
    return {**_PLATFORM_META[code], "code": code}


def list_platforms() -> List[Dict[str, Any]]:
    """列出全部平台元信息（按代码升序）。"""
    return [
        {**_PLATFORM_META[code], "code": code, "uploader": None}
        for code in sorted(_PLATFORM_META)
    ]
