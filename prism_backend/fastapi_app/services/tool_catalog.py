"""声明式工具注册中心 —— Prism 能力暴露为 tool 的单一事实源。

新增一个「可给 agent/CLI/API 调用的能力」只需在下面 ``TOOLS`` 加一条 ``ToolSpec``，
三层暴露自动覆盖：
  1. MCP tool  (agent/mcp_server.py)  -> Prism MCP & Hermes MCP 的 tools/list + tools/call
  2. API       (api/v1/tool_catalog/router.py) -> POST /api/v1/tool-catalog/<name>
  3. CLI       (prism_cli.py)         -> prism tool list / prism tool invoke <name> ...

约定：
- ``name``：唯一小写下划线（MCP tool 名、CLI 子命令、API 路径共用）。
- ``parameters``：JSON Schema（{"type":"object","properties":...,"required":[...]}），
  会被 MCP 的 inputSchema、API 的 body 校验、CLI 的参数推导复用。
- ``handler``：实际处理逻辑。async 或 sync 均可；接收 ``**kwargs``（与 parameters 对齐），
  返回 dict。约定首层用 ``{"output": ...}`` 或 ``{"success": bool, "data": ...}``；
  抛异常会被 ``invoke`` 兜成 ``{"error": ...}``。

维护者：登记真实能力时，handler 内对重依赖（浏览器/上传器）用函数内延迟 import，
避免 tool_catalog 顶层 import 拖慢启动或触发副作用。
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Any]
    category: str = ""
    output_summary: str = ""


def prism_tool(name=None, description=None, category="", parameters=None, output_summary=""):
    """标记一个函数为「可暴露的能力」——供自动遍历扫描器发现。

    用法（写在任意被扫描目录的 .py 里）::

        from fastapi_app.services.tool_catalog import prism_tool

        @prism_tool(description="两个数相加", category="demo")
        def add(a: int, b: int = 1) -> dict:
            \"\"\"加法。\\n\\n:param a: 第一个数\\n:param b: 第二个数\\n\"\"\"
            return {"sum": a + b}

    扫描器（tool_auto_scanner）会遍历代码库，自动为每个 ``@prism_tool`` 函数生成
    ToolSpec 并注册 → 自动暴露到 MCP / API / CLI / 前端，无需手写登记。
    装饰器参数均可选；不给 name 用函数名，不给 description/parameters 会从
    docstring + 函数签名自动推导。
    """

    def deco(fn):
        fn._prism_tool = {
            "name": name or fn.__name__,
            "description": description,
            "category": category,
            "parameters": parameters,
            "output_summary": output_summary,
            "_handler": fn,
        }
        return fn

    return deco


def register_auto(spec: ToolSpec) -> Optional[ToolSpec]:
    """注册一个由自动扫描发现的工具；若与已有工具重名则跳过（手动登记优先）。"""
    if spec.name in TOOLS:
        return None
    TOOLS[spec.name] = spec
    return spec


# ---------------------------------------------------------------------------
# 内置轻量 handler（不依赖任何外部服务，便于验证三层链路与单测）
# ---------------------------------------------------------------------------

async def _echo_handler(**kwargs: Any) -> Dict[str, Any]:
    """原样返回入参，用于连通性验证。"""
    return {"output": kwargs}


async def _douyin_preview_handler(**kwargs: Any) -> Dict[str, Any]:
    """抖音预览模式：跑完上传+填表+封面+自主声明后停在发布前，绝不真正发布。（本轮新增能力）"""
    from pathlib import Path

    from uploader.douyin_uploader.main_refactored import DouYinVideo

    file_path = kwargs.get("file_path")
    if not file_path:
        raise ValueError("file_path is required")
    if not Path(file_path).is_file():
        raise FileNotFoundError(file_path)

    # 解包 platform_settings.douyin（面板新增字段：whoCanSee/savePermission/hotspot/collection/miniProgram/coverOrientation/coverFile）
    ps = {}
    try:
        ps = (kwargs.get("platform_settings") or {}).get("douyin", {}) or {}
        if not isinstance(ps, dict):
            ps = {}
    except Exception:
        ps = {}

    poi_name = ""
    if isinstance(ps.get("poi"), dict):
        poi_name = ps.get("poi", {}).get("name", "")

    app = DouYinVideo(
        title=kwargs.get("title") or Path(file_path).stem,
        file_path=file_path,
        tags=kwargs.get("tags") or [],
        publish_date=kwargs.get("publish_date") or 0,
        account_file=kwargs.get("account_file") or "cookiesFile/douyin_Siuyechu_.json",
        desc=kwargs.get("desc") or "",
        publish_strategy="immediate",
        debug=bool(kwargs.get("debug", False)),
        headless=bool(kwargs.get("headless", True)),
        preview_only=True,          # 预览：停发布前
        random_cover=bool(kwargs.get("random_cover", False) or ps.get("useAIRandomCover", False)),
        location=kwargs.get("location") or poi_name,
        declaration=kwargs.get("declaration") or ps.get("declaration"),
        who_can_see=ps.get("whoCanSee", ""),
        save_permission=ps.get("savePermission", ""),
        hotspot=ps.get("hotspot", ""),
        collection=ps.get("collection", ""),
        miniProgram=ps.get("miniProgram") or None,
        cover_orientation=ps.get("coverOrientation", "landscape"),
    )
    await app.main()                # 核心：跑到发布前停住，未真正发布
    return {
        "success": True,
        "preview_only": True,
        "message": "抖音预览流程结束，已停在「发布」前，未真正发布",
        "file": file_path,
    }


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

TOOLS: Dict[str, ToolSpec] = {}


def _register(spec: ToolSpec) -> ToolSpec:
    old = TOOLS.get(spec.name)
    if old is not None:
        raise ValueError(f"duplicate tool name: {spec.name}")
    TOOLS[spec.name] = spec
    return spec


_register(ToolSpec(
    name="echo",
    description="回显输入参数，用于验证工具链路连通性。",
    parameters={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "任意回显内容", "default": ""},
        },
    },
    handler=_echo_handler,
    category="system",
    output_summary="返回 'message' 等入参",
))

_register(ToolSpec(
    name="douyin_preview",
    description=(
        "抖音上传「预览模式」：完整跑上传+填表+封面+自主声明等步骤，但停在点「发布」前，"
        "绝不真正发布。用于安全验证发布链路，可配合 --headed 可见窗口调试。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "本地视频文件绝对路径"},
            "account_file": {"type": "string", "description": "抖音账号 cookie json，相对 prism_backend/ 或绝对路径", "default": "cookiesFile/douyin_Siuyechu_.json"},
            "title": {"type": "string", "description": "作品标题；缺省用文件名"},
            "desc": {"type": "string", "description": "作品描述", "default": ""},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "话题列表", "default": []},
            "publish_date": {"type": "integer", "description": "发布时间时间戳（0=立即）", "default": 0},
            "headless": {"type": "boolean", "description": "无头浏览器；false 则开可见窗口便于观察", "default": True},
            "debug": {"type": "boolean", "description": "debug 日志", "default": False},
            "random_cover": {"type": "boolean", "description": "随机选推荐封面", "default": False},
        },
        "required": ["file_path"],
    },
    handler=_douyin_preview_handler,
    category="douyin",
    output_summary="跑完预览流程，停在发布前返回（不真正发布）",
))


async def _generate_ai_metadata_handler(**kwargs: Any) -> Dict[str, Any]:
    """AI 生成标题+话题并按平台落地（网感规则 + 平台字数/话题上限 + 可选语言）。"""
    from fastapi_app.db.session import main_db_pool
    from ai_service.metadata_generation_service import generate_metadata_for_files

    file_ids = kwargs.get("file_ids") or []
    if not file_ids:
        raise ValueError("file_ids is required")

    with main_db_pool.get_connection() as conn:
        summary = await generate_metadata_for_files(
            db=conn,
            file_ids=file_ids,
            force_regenerate=bool(kwargs.get("force_regenerate", False)),
            platform=kwargs.get("platform"),
            language=kwargs.get("language"),
        )
    return {"success": True, "data": summary}


_register(ToolSpec(
    name="generate_ai_metadata",
    description=(
        "AI 生成视频标题+标签并写入素材，支持平台网感文案规则与中英双语。\n"
        "传 platform=douyin/xiaohongshu/kuaishou/bilibili/video_account/tiktok 时启用对应平台规则；"
        "language=zh/en/bilingual 控制输出语言（TikTok 默认 bilingual）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "file_ids": {"type": "array", "items": {"type": "integer"}, "description": "视频文件ID列表"},
            "force_regenerate": {"type": "boolean", "description": "是否强制重新生成（即使已有AI内容）", "default": False},
            "platform": {"type": "string", "description": "目标平台 douyin/xiaohongshu/kuaishou/bilibili/video_account/tiktok；为空则通用生成", "default": ""},
            "language": {"type": "string", "description": "输出语言 zh/en/bilingual；TikTok 默认 bilingual（中英双语）", "default": ""},
        },
        "required": ["file_ids"],
    },
    handler=_generate_ai_metadata_handler,
    category="title_topic",
    output_summary="返回每条素材的 ai_title / ai_tags（按平台落地）",
))


# ---------------------------------------------------------------------------
# 访问与调用
# ---------------------------------------------------------------------------

def get(name: str) -> Optional[ToolSpec]:
    return TOOLS.get(name)


def all_tools() -> List[ToolSpec]:
    return list(TOOLS.values())


async def invoke(name: str, **kwargs: Any) -> Dict[str, Any]:
    """统一调用入口：按需适配 async/sync handler，异常兜底为 {'error': ...}。"""
    spec = TOOLS.get(name)
    if spec is None:
        return {"error": f"unknown tool: {name}"}
    try:
        result = spec.handler(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, dict):
            return result
        return {"output": result}
    except Exception as exc:  # noqa: BLE001 - 工具失败的统一呈现
        return {"error": f"{type(exc).__name__}: {exc}"}


# 便捷：python -m fastapi_app.services.tool_catalog 可打印工具清单（自检用）
def _main() -> None:
    import json

    print(json.dumps([{"name": t.name, "category": t.category, "description": t.description} for t in all_tools()], ensure_ascii=False, indent=2))


# —— 自动遍历：扫描代码库里的 @prism_tool 函数并注册（手动登记优先）——
from .tool_auto_scanner import register_auto_tools  # noqa: E402

register_auto_tools()


if __name__ == "__main__":
    _main()
