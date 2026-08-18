"""
平台上传实现注册表（统一入口）

目标：
- 发布链路只依赖这里获取 uploader（platform layer）
- 具体实现可逐步从旧 uploader/* 迁移到 platforms/*
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, Optional, Protocol


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


_uploaders_by_code: Dict[int, PlatformUploader] | None = None
_UPLOADER_SPECS: Dict[int, tuple[str, str]] = {
    1: ("platforms.xiaohongshu.upload", "xiaohongshu_upload"),
    2: ("platforms.tencent.upload", "tencent_upload"),
    3: ("platforms.douyin.upload", "douyin_upload"),
    4: ("platforms.kuaishou.upload", "kuaishou_upload"),
    5: ("platforms.bilibili.upload", "bilibili_upload"),
}


def _build_registry() -> Dict[int, PlatformUploader]:
    registry: Dict[int, PlatformUploader] = {}
    for platform_code, (module_name, attr_name) in _UPLOADER_SPECS.items():
        module = importlib.import_module(module_name)
        registry[platform_code] = getattr(module, attr_name)
    return registry


def get_uploader_by_platform_code(platform_code: int) -> PlatformUploader:
    global _uploaders_by_code
    if _uploaders_by_code is None:
        _uploaders_by_code = _build_registry()
    if platform_code not in _uploaders_by_code:
        raise ValueError(f"Unsupported platform_code: {platform_code}")
    return _uploaders_by_code[platform_code]


def normalize_platform_code(value: Any) -> Optional[int]:
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
        mapping = {
            "xiaohongshu": 1,
            "xhs": 1,
            "tencent": 2,
            "channels": 2,
            "wechat": 2,
            "douyin": 3,
            "kuaishou": 4,
            "ks": 4,
            "bilibili": 5,
            "bili": 5,
        }
        return mapping.get(s)
    return None
