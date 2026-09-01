"""
Persona 代理网关服务 —— 每个订阅节点分配独立端口。

职责：
1. 从订阅 URL 抓取节点（支持 base64 明文 / Clash YAML 两种格式）。
2. 为每个节点分配独立端口（8001 起），生成对应 listener。
3. 生成 tools/persona-studio/proxies/config.yaml + nodes.yaml。
4. 通过 mihomo external-controller 热重载（PUT /configs?force=true），无需重启进程。

数据文件：
- PROXIES_DIR = tools/persona-studio/proxies/
- config.yaml / nodes.yaml / gateway.json
"""
from __future__ import annotations

import base64
import json
import socket
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml

from fastapi_app.core.config import settings

# ---------------------------------------------------------------------------
# 路径与常量
# ---------------------------------------------------------------------------
PROXIES_DIR = Path(settings.BASE_DIR).parent / "tools" / "persona-studio" / "proxies"
CONFIG_PATH = PROXIES_DIR / "config.yaml"
NODES_PATH = PROXIES_DIR / "nodes.yaml"
STATE_PATH = PROXIES_DIR / "gateway.json"

CONTROLLER_URL = "http://127.0.0.1:9093"
CONTROLLER_SECRET = "persona_gateway"

BASE_PORT = 8001  # 每个节点的端口起点

# 过滤掉不可靠节点
_BAD_MARKERS = ("- UDP", "[ IPv6", "[ 0.5x")

CONFIG_HEADER = """# Persona 代理网关 (独立官方 mihomo) —— 由后端自动生成
# 每个订阅节点分配独立端口（8001 起），均为 HTTP+SOCKS mixed 代理。
# 更新请用 Prism「代理网关」页面，勿手改（会被覆盖）。

port: 0
socks-port: 0
mixed-port: 0
redir-port: 0
tproxy-port: 0
allow-lan: false
mode: global
log-level: info
ipv6: true
external-controller: 127.0.0.1:9093
secret: persona_gateway

dns:
  enable: true
  ipv6: false
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  nameserver:
    - 223.5.5.5
    - 119.29.29.29
  default-nameserver:
    - 223.5.5.5

"""

# ---------------------------------------------------------------------------
# 订阅抓取与解析
# ---------------------------------------------------------------------------

def fetch_subscription(url: str) -> str:
    req = requests.get(url, headers={"User-Agent": "clash.meta"}, timeout=20)
    req.raise_for_status()
    return req.text


def _b64decode_safe(s: str) -> Optional[str]:
    try:
        s = s.strip()
        s += "=" * (-len(s) % 4)
        return base64.b64decode(s, validate=False).decode("utf-8", errors="replace")
    except Exception:
        return None


def _parse_ss(uri: str) -> Optional[Dict[str, Any]]:
    """ss://BASE64(method:password)@host:port#name 或 ss://BASE64(whole)"""
    rest = uri[len("ss://"):]
    name = ""
    if "#" in rest:
        rest, frag = rest.split("#", 1)
        name = requests.utils.unquote(frag).strip()
    if "@" in rest:
        userinfo, hostport = rest.rsplit("@", 1)
        decoded = _b64decode_safe(userinfo) or userinfo
        if ":" not in decoded:
            return None
        method, password = decoded.split(":", 1)
        hostport = hostport.split("/")[0].split("?")[0]
        if ":" not in hostport:
            return None
        host, port_s = hostport.rsplit(":", 1)
    else:
        decoded = _b64decode_safe(rest) or rest
        if "@" not in decoded:
            return None
        userinfo, hostport = decoded.rsplit("@", 1)
        if ":" not in userinfo:
            return None
        method, password = userinfo.split(":", 1)
        hostport = hostport.split("/")[0].split("?")[0]
        if ":" not in hostport:
            return None
        host, port_s = hostport.rsplit(":", 1)
        name = name or host
    try:
        port = int(port_s)
    except ValueError:
        return None
    return {"name": name or host, "type": "ss", "server": host, "port": port, "cipher": method, "password": password}


def _parse_vmess(uri: str) -> Optional[Dict[str, Any]]:
    rest = uri[len("vmess://"):]
    decoded = _b64decode_safe(rest)
    if not decoded:
        return None
    try:
        obj = json.loads(decoded)
    except Exception:
        return None
    return {
        "name": obj.get("ps") or obj.get("name") or obj.get("add", ""),
        "type": "vmess",
        "server": obj.get("add"),
        "port": int(obj.get("port", 0)),
        "uuid": obj.get("id"),
        "alterId": int(obj.get("aid", 0)),
        "cipher": obj.get("scy") or "auto",
        "udp": True,
        "tls": obj.get("tls") == "tls",
        "servername": obj.get("sni") or "",
        "sni": obj.get("sni") or "",
        "network": obj.get("net") or "tcp",
    }


def _parse_trojan_vless(uri: str) -> Optional[Dict[str, Any]]:
    scheme_end = uri.index("://")
    scheme = uri[:scheme_end]
    rest = uri[scheme_end + 3:]
    password, rest2 = rest.split("@", 1) if "@" in rest else ("", rest)
    if "#" in rest2:
        hostport, frag = rest2.split("#", 1)
        name = requests.utils.unquote(frag).strip()
    else:
        hostport = rest2
        name = ""
    params = {}
    if "?" in hostport:
        hostport, qs = hostport.split("?", 1)
        for kv in qs.split("&"):
            if "=" in kv:
                k, v = kv.split("=", 1)
                params[k] = requests.utils.unquote(v)
    if ":" not in hostport:
        return None
    host, port_s = hostport.rsplit(":", 1)
    try:
        port = int(port_s)
    except ValueError:
        return None
    node: Dict[str, Any] = {
        "name": name or host,
        "type": scheme,
        "server": host,
        "port": port,
        "password" if scheme == "trojan" else "uuid": password,
        "udp": True,
        "sni": params.get("sni") or params.get("host") or host,
        "network": params.get("type") or "tcp",
    }
    if scheme == "vless":
        node["flow"] = params.get("flow", "")
    return node


def _parse_hysteria2(uri: str) -> Optional[Dict[str, Any]]:
    rest = uri[len("hysteria2://"):] if uri.startswith("hysteria2://") else uri[len("hy2://"):]
    if "#" in rest:
        rest, frag = rest.split("#", 1)
        name = requests.utils.unquote(frag).strip()
    else:
        name = ""
    password, rest2 = rest.split("@", 1) if "@" in rest else ("", rest)
    params = {}
    if "?" in rest2:
        rest2, qs = rest2.split("?", 1)
        for kv in qs.split("&"):
            if "=" in kv:
                k, v = kv.split("=", 1)
                params[k] = requests.utils.unquote(v)
    rest2 = rest2.split("/")[0]
    if ":" not in rest2:
        return None
    host, port_s = rest2.rsplit(":", 1)
    try:
        port = int(port_s)
    except ValueError:
        return None
    return {
        "name": name or host,
        "type": "hysteria2",
        "server": host,
        "port": port,
        "password": password,
        "sni": params.get("sni") or host,
        "skip-cert-verify": True,
        "obfs": params.get("obfs", ""),
        "obfs-password": params.get("obfs-password", ""),
    }


_SCHEME_TAGS = ("vmess:", "trojan:", "vless:", "ss:", "hy2:", "hysteria2:")


def _display_name(name: str) -> str:
    n = (name or "").strip()
    for tag in _SCHEME_TAGS:
        if n.startswith(tag):
            return n[len(tag):]
    return n


def _is_good(name: str) -> bool:
    return not any(m in name for m in _BAD_MARKERS)


def _parse_plain_links(text: str) -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []
    for raw_line in text.splitlines():
        uri = raw_line.strip()
        if not uri or uri.startswith("#"):
            continue
        try:
            node = None
            if uri.startswith("ss://"):
                node = _parse_ss(uri)
            elif uri.startswith("vmess://"):
                node = _parse_vmess(uri)
            elif uri.startswith("trojan://") or uri.startswith("vless://"):
                node = _parse_trojan_vless(uri)
            elif uri.startswith("hysteria2://") or uri.startswith("hy2://"):
                node = _parse_hysteria2(uri)
            if node and node.get("server"):
                node["name"] = _display_name(node["name"])
                nodes.append(node)
        except Exception:
            continue
    return nodes


def _parse_yaml_proxies(text: str) -> List[Dict[str, Any]]:
    try:
        obj = yaml.safe_load(text)
    except Exception:
        return []
    if not isinstance(obj, dict):
        return []
    proxies = obj.get("proxies")
    if not isinstance(proxies, list):
        return []
    nodes = []
    for p in proxies:
        if isinstance(p, dict) and p.get("name") and p.get("server"):
            p["name"] = _display_name(p["name"])
            nodes.append(p)
    return nodes


def parse_subscription(text: str) -> List[Dict[str, Any]]:
    text = text.strip()
    decoded = _b64decode_safe(text)
    if decoded and decoded.lstrip().startswith(("vmess://", "trojan://", "ss://", "vless://", "hysteria2://", "hy2://")):
        return _parse_plain_links(decoded)
    try:
        obj = yaml.safe_load(text)
        if isinstance(obj, dict) and isinstance(obj.get("proxies"), list) and obj["proxies"]:
            return _parse_yaml_proxies(text)
    except Exception:
        pass
    return _parse_plain_links(text)


# ---------------------------------------------------------------------------
# 端口分配与配置生成
# ---------------------------------------------------------------------------

def _assign_ports(nodes: List[Dict[str, Any]]) -> Dict[str, int]:
    """为每个节点分配端口，返回 {name: port}。"""
    return {n["name"]: BASE_PORT + i for i, n in enumerate(nodes)}


def _proxy_block(nodes: List[Dict[str, Any]]) -> str:
    lines = ["proxies:"]
    for n in nodes:
        lines.append(f"  - name: {n['name']}")
        for k in ("type", "server", "port", "uuid", "alterId", "cipher", "password",
                  "udp", "tls", "servername", "sni", "network", "skip-cert-verify",
                  "client-fingerprint", "flow", "obfs", "obfs-password", "alpn", "reality-opts"):
            if k in n and n[k] not in (None, "", 0):
                if isinstance(n[k], bool):
                    lines.append(f"    {k}: {str(n[k]).lower()}")
                else:
                    lines.append(f"    {k}: {n[k]}")
    return "\n".join(lines)


def _listener_block_all(port_map: Dict[str, int]) -> str:
    lines = ["listeners:"]
    for name, port in port_map.items():
        lines.append(f"  - name: {name}")
        lines.append("    type: mixed")
        lines.append("    listen: 127.0.0.1")
        lines.append(f"    port: {port}")
        lines.append(f'    proxy: "{name}"')
        lines.append("    udp: true")
    return "\n".join(lines)


def build_config(nodes: List[Dict[str, Any]], port_map: Dict[str, int]) -> str:
    parts = [CONFIG_HEADER, _proxy_block(nodes), "\n", _listener_block_all(port_map), "\n", "rules:\n  - MATCH,DIRECT\n"]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 持久化与热重载
# ---------------------------------------------------------------------------

def _save_state(url: str, port_map: Dict[str, int]) -> None:
    state = {
        "subscription_url": url,
        "port_map": port_map,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_state() -> Optional[Dict[str, Any]]:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _reload_via_controller() -> Dict[str, Any]:
    try:
        resp = requests.put(
            f"{CONTROLLER_URL}/configs?force=true",
            headers={"Authorization": f"Bearer {CONTROLLER_SECRET}"},
            json={"path": str(CONFIG_PATH)},
            timeout=10,
        )
        return {"ok": resp.status_code in (200, 204), "http": resp.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def generate_and_reload(url: str) -> Dict[str, Any]:
    """抓取订阅 → 全量节点分配端口 → 写配置 → 热重载。"""
    text = fetch_subscription(url)
    nodes = parse_subscription(text)
    if not nodes:
        raise ValueError("未能从订阅中解析出任何节点")

    port_map = _assign_ports(nodes)
    NODES_PATH.write_text(_proxy_block(nodes) + "\n", encoding="utf-8")
    CONFIG_PATH.write_text(build_config(nodes, port_map), encoding="utf-8")
    _save_state(url, port_map)

    reload = _reload_via_controller()

    return {
        "url": url,
        "total_nodes": len(nodes),
        "port_map": port_map,
        "reload": reload,
        "config_path": str(CONFIG_PATH),
    }


def current_status() -> Dict[str, Any]:
    state = _load_state()
    port_map = (state or {}).get("port_map", {})
    ports = {}
    for name, port in port_map.items():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        try:
            s.connect(("127.0.0.1", port))
            ports[name] = True
        except Exception:
            ports[name] = False
        finally:
            s.close()
    controller_ok = False
    try:
        r = requests.get(f"{CONTROLLER_URL}/version", headers={"Authorization": f"Bearer {CONTROLLER_SECRET}"}, timeout=3)
        controller_ok = r.status_code == 200
    except Exception:
        controller_ok = False
    return {
        "subscription_url": (state or {}).get("subscription_url", ""),
        "port_map": port_map,
        "ports": ports,
        "updated_at": (state or {}).get("updated_at", ""),
        "controller_ok": controller_ok,
    }


def reload_existing() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise ValueError("config.yaml 不存在，请先配置订阅")
    reload = _reload_via_controller()
    return {"reload": reload, "config_path": str(CONFIG_PATH)}


def clear_subscription() -> Dict[str, Any]:
    """取消导入：写空配置（无节点、无监听）→ 热重载释放端口 → 清空状态。"""
    empty_config = CONFIG_HEADER + "proxies: []\n\nlisteners: []\n\nrules:\n  - MATCH,DIRECT\n"
    CONFIG_PATH.write_text(empty_config, encoding="utf-8")
    reload = _reload_via_controller()
    # 清空状态与节点文件
    STATE_PATH.write_text("{}", encoding="utf-8")
    if NODES_PATH.exists():
        NODES_PATH.write_text("proxies: []\n", encoding="utf-8")
    return {"reload": reload, "cleared": True}
