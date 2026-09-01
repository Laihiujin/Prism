"""
Persona 代理池：从 Persona 代理网关状态中，按国家动态查找可用代理端口。

这些端口由独立官方 mihomo 网关提供（tools/persona-studio/proxies/），
导入订阅后自动为每个节点分配独立 mixed 端口。
此模块读取网关的 port_map，找到属于目标国家的节点并返回其端口。
- direct: 直连（不注入代理，使用本机网络 + 本机 locale/时区）
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi_app.core.config import settings

# 预定义地区元信息（locale / 时区固定，端口动态获取）
REGION_META: Dict[str, Dict[str, Any]] = {
    "direct": {"name": "直连", "country": None, "locale": None, "timezone_id": None},
    "sg":     {"name": "新加坡", "country": "SG",   "locale": "en-SG",   "timezone_id": "Asia/Singapore"},
    "jp":     {"name": "日本",   "country": "JP",   "locale": "ja-JP",   "timezone_id": "Asia/Tokyo"},
    "us":     {"name": "美国",   "country": "US",   "locale": "en-US",   "timezone_id": "America/New_York"},
    "de":     {"name": "德国",   "country": "DE",   "locale": "de-DE",   "timezone_id": "Europe/Berlin"},
    "tw":     {"name": "台湾",   "country": "TW",   "locale": "zh-TW",   "timezone_id": "Asia/Taipei"},
    "hk":     {"name": "香港",   "country": "HK",   "locale": "zh-HK",   "timezone_id": "Asia/Hong_Kong"},
}

# emoji prefix → region key (用于在节点名中匹配国家)
COUNTRY_PREFIXES = [
    ("🇸🇬 ", "sg"),
    ("🇯🇵 ", "jp"),
    ("🇺🇸 ", "us"),
    ("🇩🇪 ", "de"),
    ("🇹🇼 ", "tw"),
    ("🇭🇰 ", "hk"),
]

PROXIES_STATE_PATH = Path(settings.BASE_DIR).parent / "tools" / "persona-studio" / "proxies" / "gateway.json"


def _load_gateway_state() -> Optional[Dict[str, Any]]:
    """加载网关状态文件."""
    try:
        return json.loads(PROXIES_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _find_port_for_country(port_map: Dict[str, int], country_prefix: str) -> Optional[int]:
    """在 port_map 中找到第一个以该前缀开头的节点的端口."""
    for name, port in port_map.items():
        if name.startswith(country_prefix):
            return port
    return None


def resolve_persona_proxy(region: Optional[str]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """按地区解析出 persona 的 proxy 配置与 profile 对齐信息.

    Returns:
        (proxy_config, profile_opts)
        - proxy_config: {"server": "http://127.0.0.1:<port>", "country": "..."} 或 None(直连)
        - profile_opts: {"locale": "...", "timezone_id": "...", "country": "...", "region": "..."}
    """
    region = (region or "direct").strip().lower()
    meta = REGION_META.get(region, REGION_META["direct"])

    if region == "direct" or not meta.get("country"):
        # 直连模式
        return None, {
            "country": meta.get("country"),
            "locale": meta.get("locale"),
            "timezone_id": meta.get("timezone_id"),
            "region": region,
        }

    # 从网关端口映射中动态查找该地区的节点端口
    state = _load_gateway_state()
    port_map = (state or {}).get("port_map", {})

    # 找到该地区最好的一个节点端口（优先含 [ h12 ] 的，其次任意）
    port = None
    prefix = None
    for emoji, rkey in COUNTRY_PREFIXES:
        if rkey != region:
            continue
        prefix = emoji
        port = _find_port_for_country(port_map, emoji)
        break

    if not port:
        # 未导入订阅或没有该国的节点
        return None, {
            "country": meta.get("country"),
            "locale": meta.get("locale"),
            "timezone_id": meta.get("timezone_id"),
            "region": region,
        }

    server = f"http://127.0.0.1:{port}"
    return (
        {"server": server, "country": meta.get("country")},
        {
            "country": meta.get("country"),
            "locale": meta.get("locale"),
            "timezone_id": meta.get("timezone_id"),
            "region": region,
        },
    )


def list_proxies() -> Dict[str, Dict[str, Any]]:
    """返回可用的代理地区（含名称、国家、当前端口）."""
    result = {}
    state = _load_gateway_state()
    port_map = (state or {}).get("port_map", {})

    for key, meta in REGION_META.items():
        if key == "direct":
            result[key] = {"name": meta["name"], "country": None, "has_proxy": False}
            continue
        prefix = None
        for emoji, rkey in COUNTRY_PREFIXES:
            if rkey == key:
                prefix = emoji
                break
        port = _find_port_for_country(port_map, prefix or "") if prefix else None
        result[key] = {
            "name": meta["name"],
            "country": meta.get("country"),
            "has_proxy": port is not None,
            "current_port": port,
        }
    return result
