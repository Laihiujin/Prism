"""每平台发布/登录/校验工具包 —— 每平台一个独立模块。

模块划分（改其中一个平台不影响其他平台）：
  douyin / kuaishou / xiaohongshu  视频 + 图文/笔记 + 登录 + 校验
  bilibili / channels / baijiahao / tiktok / youtube  视频 + 登录 + 校验（无图文）

每个平台模块导出 ``SPECS: list[ToolSpec]``。这里汇总注册到 ``tool_catalog``，
三层自动暴露：MCP tool / API（/api/v1/tool-catalog/<name>）/ CLI（prism tool invoke <name>）。
"""

from __future__ import annotations

from typing import List

from . import (
    baijiahao, bilibili, channels, douyin, kuaishou, tiktok, xiaohongshu, youtube,
)
from ..tool_catalog import ToolSpec

_PLATFORM_MODULES = (
    douyin, kuaishou, xiaohongshu, bilibili, channels, baijiahao, tiktok, youtube,
)


def build_publish_tool_specs() -> List[ToolSpec]:
    """汇总所有平台模块的 SPECS，注册前按 name 去重（同名前者优先）。"""
    specs: List[ToolSpec] = []
    seen: set[str] = set()
    for module in _PLATFORM_MODULES:
        for spec in getattr(module, "SPECS", []):
            if spec.name in seen:
                continue
            seen.add(spec.name)
            specs.append(spec)
    return specs
