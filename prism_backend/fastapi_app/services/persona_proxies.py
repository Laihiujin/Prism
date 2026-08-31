"""
Persona 代理池：把本机 per-country 代理端口（7771–7776）映射为 persona profile 的代理。

这些端口由独立的官方 mihomo 网关提供（tools/persona-studio/proxies/），
每个地区一个 mixed 代理端口，路由到对应国家的节点。
persona 创建/更新 profile 时会注入该代理，并按 country 对齐 locale / 时区，让指纹更真实。
- direct: 直连（不注入代理，使用本机网络 + 本机 locale/时区）
"""
from typing import Any, Dict, Optional, Tuple

# region -> 代理信息
# server: ClashParty mixed 代理地址；country: 用于 locale/时区对齐
PERSONA_PROXIES: Dict[str, Dict[str, Any]] = {
    "direct": {"name": "直连", "server": None, "country": None, "locale": None, "timezone": None},
    "sg": {"name": "新加坡", "server": "http://127.0.0.1:7771", "country": "SG", "locale": "en-SG", "timezone": "Asia/Singapore"},
    "jp": {"name": "日本", "server": "http://127.0.0.1:7772", "country": "JP", "locale": "ja-JP", "timezone": "Asia/Tokyo"},
    "us": {"name": "美国", "server": "http://127.0.0.1:7773", "country": "US", "locale": "en-US", "timezone": "America/New_York"},
    "de": {"name": "德国", "server": "http://127.0.0.1:7774", "country": "DE", "locale": "de-DE", "timezone": "Europe/Berlin"},
    "tw": {"name": "台湾", "server": "http://127.0.0.1:7775", "country": "TW", "locale": "zh-TW", "timezone": "Asia/Taipei"},
    "hk": {"name": "香港", "server": "http://127.0.0.1:7776", "country": "HK", "locale": "zh-HK", "timezone": "Asia/Hong_Kong"},
}


def list_proxies() -> Dict[str, Dict[str, Any]]:
    """返回可用的代理地区（含名称，不含内部 server/时区细节）。"""
    return {k: {"name": v["name"], "country": v.get("country")} for k, v in PERSONA_PROXIES.items()}


def resolve_proxy(region: Optional[str]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """按地区解析出 persona 的 proxy 配置与 profile 对齐信息。

    Returns:
        (proxy_config, profile_opts)
        - proxy_config: {"server": "...", "country": "..."} 或 None(直连)
        - profile_opts: {"locale": "...", "timezone_id": "...", "country": "..."}
    """
    region = (region or "direct").strip().lower()
    p = PERSONA_PROXIES.get(region)
    if not p:
        p = PERSONA_PROXIES["direct"]
    if not p.get("server"):
        # 直连：不注入代理
        return None, {
            "country": p.get("country"),
            "locale": p.get("locale"),
            "timezone_id": p.get("timezone"),
            "region": region,
        }
    return (
        {"server": p["server"], "country": p["country"]},
        {
            "country": p.get("country"),
            "locale": p.get("locale"),
            "timezone_id": p.get("timezone"),
            "region": region,
        },
    )
