"""
mihomo 代理网关工具集 —— 供 Hermes Agent 调用。

包含两个工具：
1. proxy_gateway     —— 通过后端 API 管理代理网关（导入订阅 / 状态 / 重载 / 取消 / 节点测试）
2. mihomo_control    —— 直接操作本机 mihomo 外部控制器（版本 / 实时流量 / 连接 / 配置）

mihomo 二进制位于 tools/persona-studio/proxies/mihomo（官方 v1.19.10），
由 PM2 以 persona-proxy 应用托管，external-controller 127.0.0.1:9093，
secret: persona_gateway。后端管理端点: /api/v1/persona-proxy/*
"""
import os
from typing import Any, Dict, List, Optional

import httpx

from .tool_runtime import BaseTool, ToolResult

# 后端 API 基础 URL（本地）
API_BASE_URL = os.getenv("AGENT_API_BASE_URL", os.getenv("MANUS_API_BASE_URL", "http://localhost:7000/api/v1"))

# mihomo 外部控制器
MIHOMO_BASE = "http://127.0.0.1:9093"
MIHOMO_SECRET = "persona_gateway"

MIHOMO_HEADERS = {"Authorization": f"Bearer {MIHOMO_SECRET}"}

# 端口 -> 常见国家标记（用于节点路由说明）
_COUNTRY_BY_FLAG = {
    "🇸🇬": "新加坡(SG)", "🇯🇵": "日本(JP)", "🇺🇸": "美国(US)",
    "🇩🇪": "德国(DE)", "🇹🇼": "台湾(TW)", "🇭🇰": "香港(HK)",
}


def _flag_of(name: str) -> str:
    for flag in _COUNTRY_BY_FLAG:
        if name.startswith(flag):
            return _COUNTRY_BY_FLAG[flag]
    return "未知地区"


async def _api_get(path: str, timeout: float = 30.0) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(f"{API_BASE_URL}{path}")
        r.raise_for_status()
        return r.json()


async def _api_put(path: str, payload: Dict[str, Any], timeout: float = 60.0) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.put(f"{API_BASE_URL}{path}", json=payload)
        r.raise_for_status()
        return r.json()


async def _api_delete(path: str, timeout: float = 30.0) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.delete(f"{API_BASE_URL}{path}")
        r.raise_for_status()
        return r.json()


# ============================================
# 代理网关管理工具
# ============================================

class ProxyGatewayTool(BaseTool):
    """代理网关管理工具"""

    name: str = "proxy_gateway"
    description: str = (
        "管理本机 mihomo 代理网关（每个订阅节点一个独立 mixed 端口，8001 起）。"
        "支持：导入订阅 URL 并自动分配端口、查看当前状态（节点/端口/监听）、"
        "热重载配置、取消导入释放端口、测试某个端口的实际出口地区。"
        "订阅 URL 形如 https://xxx/sub?token=...；节点名含国家旗帜如 🇯🇵 日本 1 [ h12 ]。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["status", "import", "reload", "clear", "test_node", "list_nodes"],
                "description": "操作类型：status=查看状态; import=导入订阅; reload=热重载; clear=取消导入; test_node=测试节点出口; list_nodes=列出全部节点端口",
            },
            "subscription_url": {
                "type": "string",
                "description": "订阅 URL（仅 action=import 时必填）",
            },
            "node_name": {
                "type": "string",
                "description": "节点名称（仅 action=test_node 时必填），如 '🇯🇵 日本 1 [ h12 ]'",
            },
        },
        "required": ["action"],
    }

    async def execute(
        self,
        action: str,
        subscription_url: Optional[str] = None,
        node_name: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        try:
            if action == "status":
                data = await _api_get("/persona-proxy")
                result = data.get("result", {})
                port_map = result.get("port_map", {})
                ports = result.get("ports", {})
                listening = sum(1 for v in ports.values() if v)

                lines = []
                lines.append(f"订阅: {result.get('subscription_url') or '(未导入)'}")
                lines.append(f"更新: {result.get('updated_at') or '-'}")
                lines.append(f"网关控制: {'在线' if result.get('controller_ok') else '离线'}")
                lines.append(f"节点数: {len(port_map)}  监听中: {listening}/{len(port_map)}")
                lines.append("")
                if port_map:
                    lines.append("节点端口列表:")
                    for name in sorted(port_map, key=lambda n: port_map[n]):
                        port = port_map[name]
                        status = "✓监听" if ports.get(name) else "✗未监听"
                        lines.append(f"  {port}  {status}  {name}")
                else:
                    lines.append("（暂无节点，请先用 import 导入订阅）")
                return ToolResult(output="\n".join(lines))

            elif action == "list_nodes":
                data = await _api_get("/persona-proxy")
                result = data.get("result", {})
                port_map = result.get("port_map", {})
                ports = result.get("ports", {})
                if not port_map:
                    return ToolResult(output="暂无节点，请先导入订阅。")
                lines = [f"共 {len(port_map)} 个节点，每个节点一个独立端口："]
                for name in sorted(port_map, key=lambda n: port_map[n]):
                    port = port_map[name]
                    status = "✓" if ports.get(name) else "✗"
                    lines.append(f"  {port} {status} [{_flag_of(name)}] {name}")
                return ToolResult(output="\n".join(lines))

            elif action == "import":
                if not subscription_url or not subscription_url.startswith(("http://", "https://")):
                    return ToolResult(error="import 需要提供合法的 subscription_url（http/https 开头）")
                data = await _api_put("/persona-proxy/subscription", {"url": subscription_url})
                result = data.get("result", {})
                reload_ok = result.get("reload", {}).get("ok")
                port_map = result.get("port_map", {})
                lines = [
                    f"✅ 导入成功：解析 {result.get('total_nodes', 0)} 个节点",
                    f"热重载: {'成功' if reload_ok else '失败'}",
                ]
                if port_map:
                    lines.append("端口分配示例:")
                    for name in sorted(port_map, key=lambda n: port_map[n])[:10]:
                        lines.append(f"  {port_map[name]}  {name}")
                    if len(port_map) > 10:
                        lines.append(f"  ... 共 {len(port_map)} 个")
                return ToolResult(output="\n".join(lines))

            elif action == "reload":
                async with httpx.AsyncClient(timeout=30.0) as client:
                    r = await client.post(f"{API_BASE_URL}/persona-proxy/reload")
                    r.raise_for_status()
                    data = r.json()
                reload_ok = data.get("result", {}).get("reload", {}).get("ok")
                return ToolResult(output=f"热重载 {'成功 ✅' if reload_ok else '失败 ❌'}")

            elif action == "clear":
                data = await _api_delete("/persona-proxy/subscription")
                cleared = data.get("result", {}).get("cleared", False)
                return ToolResult(output=f"已取消导入，{'所有端口已释放' if cleared else '状态已清空'} ✅")

            elif action == "test_node":
                if not node_name:
                    return ToolResult(error="test_node 需要提供 node_name")
                data = await _api_get("/persona-proxy")
                result = data.get("result", {})
                port_map = result.get("port_map", {})
                if node_name not in port_map:
                    return ToolResult(error=f"节点 '{node_name}' 不存在。可用节点: {', '.join(list(port_map)[:5])}...")
                port = port_map[node_name]
                proxy_url = f"http://127.0.0.1:{port}"
                async with httpx.AsyncClient(
                    timeout=15.0,
                    proxy=proxy_url,
                ) as client:
                    try:
                        r = await client.get("http://ip-api.com/json/?fields=countryCode,country,query")
                        info = r.json()
                        country = info.get("country", "?")
                        code = info.get("countryCode", "?")
                        ip = info.get("query", "?")
                        return ToolResult(
                            output=f"✅ 节点 '{node_name}' (端口 {port}) 出口: {country}({code}) IP={ip}"
                        )
                    except Exception as e:
                        return ToolResult(error=f"测试节点 '{node_name}' (端口 {port}) 失败: {e}")

            else:
                return ToolResult(error=f"未知 action: {action}")

        except Exception as e:
            return ToolResult(error=f"代理网关操作失败: {str(e)}")


# ============================================
# mihomo 运行时控制工具
# ============================================

class MihomoControlTool(BaseTool):
    """mihomo 运行时控制工具"""

    name: str = "mihomo_control"
    description: str = (
        "直接操作本机 mihomo 内核（官方 v1.19.10，external-controller 127.0.0.1:9093）。"
        "支持：查看版本与运行信息、实时流量采样、当前活跃连接、全局代理配置、"
        "测试某个代理节点是否可用（alive）。用于排查代理网关运行状况。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["info", "traffic", "connections", "configs", "proxy_status"],
                "description": "操作类型：info=版本信息; traffic=实时流量; connections=活跃连接; configs=全局配置; proxy_status=内置代理状态",
            },
            "proxy_name": {
                "type": "string",
                "description": "代理名称（仅 proxy_status 时可选，如 GLOBAL/DIRECT）",
            },
        },
        "required": ["action"],
    }

    async def execute(self, action: str, proxy_name: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if action == "info":
                    r = await client.get(f"{MIHOMO_BASE}/version", headers=MIHOMO_HEADERS)
                    info = r.json()
                    return ToolResult(
                        output=f"mihomo 版本: {info.get('version')}  meta: {info.get('meta', False)}"
                    )

                elif action == "traffic":
                    # mihomo /traffic 是 SSE 流式接口，空闲时不推数据、取消时可能挂起，
                    # 因此用 /connections 的累计下载/上传字节数作为流量指标（可靠、即时）。
                    try:
                        r = await client.get(f"{MIHOMO_BASE}/connections", headers=MIHOMO_HEADERS)
                        data = r.json()

                        def fmt(n):
                            for unit in ["B", "KB", "MB", "GB"]:
                                if n < 1024:
                                    return f"{n:.1f}{unit}"
                                n /= 1024
                            return f"{n:.1f}TB"

                        down = fmt(data.get("downloadTotal", 0))
                        up = fmt(data.get("uploadTotal", 0))
                        conns = len(data.get("connections") or [])
                        return ToolResult(output=f"累计流量: 下载 {down}  上传 {up}  当前连接 {conns} 条")
                    except Exception as e:
                        return ToolResult(error=f"获取流量失败: {e}")

                elif action == "connections":
                    r = await client.get(f"{MIHOMO_BASE}/connections", headers=MIHOMO_HEADERS)
                    data = r.json()
                    conns = data.get("connections") or []
                    lines = [f"当前活跃连接: {len(conns)} 条"]
                    lines.append(f"累计下载: {data.get('downloadTotal', 0)} B  累计上传: {data.get('uploadTotal', 0)} B")
                    for c in conns[:10]:
                        md = c.get("metadata", {})
                        lines.append(
                            f"  {md.get('sourceIP')}:{md.get('sourcePort')} -> "
                            f"{md.get('destinationIP')}:{md.get('destinationPort')} "
                            f"host={md.get('host')} chain={c.get('chains', [])}"
                        )
                    if len(conns) > 10:
                        lines.append(f"  ... 共 {len(conns)} 条")
                    return ToolResult(output="\n".join(lines))

                elif action == "configs":
                    r = await client.get(f"{MIHOMO_BASE}/configs", headers=MIHOMO_HEADERS)
                    c = r.json()
                    lines = [
                        f"模式: {c.get('mode')}",
                        f"mixed-port: {c.get('mixed-port')}  socks-port: {c.get('socks-port')}  port: {c.get('port')}",
                        f"allow-lan: {c.get('allow-lan')}  ipv6: {c.get('ipv6')}",
                        f"TUN: {'开启' if (c.get('tun') or {}).get('enable') else '关闭'}",
                        f"log-level: {c.get('log-level')}",
                    ]
                    return ToolResult(output="\n".join(lines))

                elif action == "proxy_status":
                    r = await client.get(f"{MIHOMO_BASE}/proxies", headers=MIHOMO_HEADERS)
                    proxies = r.json().get("proxies", {})
                    if proxy_name:
                        if proxy_name not in proxies:
                            return ToolResult(error=f"代理 '{proxy_name}' 不存在")
                        p = proxies[proxy_name]
                        return ToolResult(
                            output=f"{proxy_name}: type={p.get('type')} alive={p.get('alive')} now={p.get('now')}"
                        )
                    lines = ["内置代理列表:"]
                    for name in sorted(proxies):
                        p = proxies[name]
                        alive = "✓" if p.get("alive") else "✗"
                        lines.append(f"  {alive} {name}  type={p.get('type')} now={p.get('now')}")
                    return ToolResult(output="\n".join(lines))

                else:
                    return ToolResult(error=f"未知 action: {action}")

        except Exception as e:
            return ToolResult(error=f"mihomo 控制失败: {str(e)}")
