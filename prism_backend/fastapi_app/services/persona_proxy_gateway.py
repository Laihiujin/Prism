"""
Persona per-country 代理网关服务。

职责：
1. 从订阅 URL 抓取节点（支持 base64 明文 / Clash YAML 两种格式）。
2. 按地区（sg/jp/us/de/tw/hk）从节点中挑选一个，写入 listener 配置。
3. 生成 tools/persona-studio/proxies/config.yaml + nodes.yaml。
4. 通过 mihomo external-controller 热重载（PUT /configs?force=true），无需重启进程。

数据文件位置：
- PROXIES_DIR = tools/persona-studio/proxies/
- config.yaml / nodes.yaml / gateway.json（保存订阅 URL 与最近一次生成信息）
"""
from __future__ import annotations

import base64
import json
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml

from fastapi_app.core.config import settings

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
PROXIES_DIR = Path(settings.BASE_DIR).parent / "tools" / "persona-studio" / "proxies"
CONFIG_PATH = PROXIES_DIR / "config.yaml"
NODES_PATH = PROXIES_DIR / "nodes.yaml"
STATE_PATH = PROXIES_DIR / "gateway.json"

CONTROLLER_URL = "http://127.0.0.1:9093"
CONTROLLER_SECRET = "persona_gateway"

# 每个地区的 mixed 代理端口（与 persona_proxies.PERSONA_PROXIES 保持一致）
REGIONS: Dict[str, Dict[str, Any]] = {
    "sg": {"port": 7771, "name": "新加坡", "prefixes": ["🇸🇬 新加坡"]},
    "jp": {"port": 7772, "name": "日本", "prefixes": ["🇯🇵 日本"]},
    "us": {"port": 7773, "name": "美国", "prefixes": ["🇺🇸 直连美国", "🇺🇸 美国"]},
    "de": {"port": 7774, "name": "德国", "prefixes": ["🇩🇪 直连德国", "🇩🇪 德国"]},
    "tw": {"port": 7775, "name": "台湾", "prefixes": ["🇹🇼 台湾"]},
    "hk": {"port": 7776, "name": "香港", "prefixes": ["🇭🇰 香港"]},
}

# 过滤掉不可靠节点：UDP 直连、纯 IPv6、0.5x 限速
_BAD_MARKERS = ("- UDP", "[ IPv6", "[ 0.5x")

CONFIG_HEADER = """# Persona per-country 代理网关 (独立官方 mihomo) —— 由后端自动生成
# 提供 7771-7776 六个 HTTP/SOCKS mixed 端口，各绑定一个地区节点。
# 更新此文件请用 Prism 的「代理网关」页面，勿手改（会被覆盖）。

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
def fetch_subscription(url: str, timeout: int = 20) -> str:
    """抓取订阅文本。"""
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "clash-verge/2.0"})
    resp.raise_for_status()
    text = resp.text.strip()
    if not text:
        raise ValueError("订阅内容为空")
    return text


def _is_yaml(text: str) -> bool:
    head = text[:512]
    return head.lstrip().startswith(("proxies:", "proxies:\n", "mixed-port:", "port:")) or "proxies:" in head[:2048]


def _parse_yaml_proxies(text: str) -> List[Dict[str, Any]]:
    data = yaml.safe_load(text) or {}
    proxies = data.get("proxies") or []
    result = []
    for p in proxies:
        if not isinstance(p, dict) or not p.get("name") or not p.get("server"):
            continue
        result.append(p)
    return result


def _b64decode_safe(s: str) -> Optional[str]:
    s = s.strip()
    try:
        # 补充 padding，兼容无填充的 base64
        s2 = s + "=" * (-len(s) % 4)
        return base64.b64decode(s2).decode("utf-8", "ignore")
    except Exception:
        return None


def _parse_ss(uri: str) -> Optional[Dict[str, Any]]:
    rest = uri[len("ss://"):]
    # 支持 ss://base64(user:pass@host:port) 和 ss://method:pass@host:port
    if "@" not in rest:
        dec = _b64decode_safe(rest)
        if dec and "@" in dec:
            rest = dec
        else:
            return None
    userinfo, hostport = rest.split("@", 1)
    frag = ""
    if "#" in hostport:
        hostport, frag = hostport.split("#", 1)
    method_pass = userinfo
    if ":" not in userinfo and "%3A" not in userinfo:
        dec = _b64decode_safe(userinfo)
        if dec and ":" in dec:
            method_pass = dec
    if ":" not in method_pass:
        return None
    method, password = method_pass.split(":", 1)
    hp = hostport.split("#", 1)[0]
    return {
        "name": frag or f"ss:{hp}",
        "type": "ss",
        "server": hp.rsplit(":", 1)[0] if ":" in hp else hp,
        "port": int(hp.rsplit(":", 1)[1]) if ":" in hp else 443,
        "cipher": method,
        "password": password,
    }


def _parse_vmess(uri: str) -> Optional[Dict[str, Any]]:
    payload = uri[len("vmess://"):]
    dec = _b64decode_safe(payload)
    if not dec:
        return None
    try:
        d = json.loads(dec)
    except Exception:
        return None
    return {
        "name": d.get("ps") or d.get("add") or "",
        "type": "vmess",
        "server": d.get("add", ""),
        "port": int(d.get("port", 443)),
        "uuid": d.get("id", ""),
        "alterId": d.get("aid", 0),
        "cipher": d.get("scy", "auto"),
        "tls": d.get("tls") == "tls",
        "servername": d.get("sni", ""),
        "network": d.get("net", "tcp"),
    }


def _parse_trojan_vless(uri: str, scheme: str) -> Optional[Dict[str, Any]]:
    rest = uri[len(scheme) + 3:]
    password_id, hostport = rest.split("@", 1)
    frag = ""
    if "#" in hostport:
        hostport, frag = hostport.split("#", 1)
    query = {}
    if "?" in hostport:
        hostport, qs = hostport.split("?", 1)
        query = dict(urllib.parse.parse_qsl(qs))
    hp = hostport.split("#", 1)[0]
    host = hp.rsplit(":", 1)[0]
    port = int(hp.rsplit(":", 1)[1]) if ":" in hp else 443
    node = {
        "name": frag or f"{scheme}:{hp}",
        "type": scheme,
        "server": host,
        "port": port,
        "password": password_id if scheme == "trojan" else None,
        "uuid": password_id if scheme == "vless" else None,
        "udp": True,
    }
    if query.get("sni"):
        node["sni"] = query["sni"]
    if query.get("type"):
        node["network"] = query["type"]
    if query.get("security") and query["security"] != "none":
        node["tls"] = True
    if query.get("skip-cert-verify") == "1":
        node["skip-cert-verify"] = True
    if scheme == "vless":
        if query.get("fp"):
            node["client-fingerprint"] = query["fp"]
        if query.get("flow"):
            node["flow"] = query["flow"]
    return node


def _parse_hysteria2(uri: str) -> Optional[Dict[str, Any]]:
    rest = uri[len("hysteria2://"):]
    if "@" in rest:
        _, hostport = rest.split("@", 1)
    else:
        hostport = rest
    frag = ""
    if "#" in hostport:
        hostport, frag = hostport.split("#", 1)
    query = {}
    if "?" in hostport:
        hostport, qs = hostport.split("?", 1)
        query = dict(urllib.parse.parse_qsl(qs))
    hp = hostport.split("#", 1)[0]
    host = hp.rsplit(":", 1)[0]
    port = int(hp.rsplit(":", 1)[1]) if ":" in hp else 443
    node = {
        "name": frag or f"hy2:{hp}",
        "type": "hysteria2",
        "server": host,
        "port": port,
        "password": query.get("password", ""),
        "skip-cert-verify": query.get("insecure", "1") == "1",
    }
    if query.get("sni"):
        node["sni"] = query["sni"]
    if query.get("obfs"):
        node["obfs"] = query["obfs"]
        node["obfs-password"] = query.get("obfs-password", "")
    return node


def _parse_plain_links(text: str) -> List[Dict[str, Any]]:
    nodes = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        uri = line
        try:
            if uri.startswith("vmess://"):
                node = _parse_vmess(uri)
            elif uri.startswith("trojan://"):
                node = _parse_trojan_vless(uri, "trojan")
            elif uri.startswith("vless://"):
                node = _parse_trojan_vless(uri, "vless")
            elif uri.startswith("ss://"):
                node = _parse_ss(uri)
            elif uri.startswith("hysteria2://") or uri.startswith("hy2://"):
                node = _parse_hysteria2(uri)
            else:
                node = None
            if node and node.get("server"):
                nodes.append(node)
        except Exception:
            continue
    return nodes


def parse_subscription(text: str) -> List[Dict[str, Any]]:
    """解析订阅文本，返回节点列表。兼容 base64 明文链接与 Clash YAML。"""
    text = text.strip()
    # 1) 尝试 base64 解码明文链接
    decoded = _b64decode_safe(text)
    if decoded and decoded.lstrip().startswith(("vmess://", "trojan://", "ss://", "vless://", "hysteria2://", "hy2://")):
        return _parse_plain_links(decoded)

    # 2) 尝试 Clash YAML（直接 yaml 解析，兼容任意 header/comment）
    try:
        obj = yaml.safe_load(text)
        proxies = (obj or {}).get("proxies") if isinstance(obj, dict) else None
        if isinstance(proxies, list) and proxies:
            return _parse_yaml_proxies(text)
    except Exception:
        pass

    # 3) 否则按明文链接处理
    return _parse_plain_links(text)


# ---------------------------------------------------------------------------
# 节点挑选
# ---------------------------------------------------------------------------
def _is_good(name: str) -> bool:
    return not any(m in name for m in _BAD_MARKERS)


_SCHEME_TAGS = ("vmess:", "trojan:", "vless:", "ss:", "hy2:", "hysteria2:")


def _display_name(name: str) -> str:
    """去掉节点名里的协议前缀（如 'vmess:🇯🇵 日本 1' -> '🇯🇵 日本 1'）。"""
    n = (name or "").strip()
    for tag in _SCHEME_TAGS:
        if n.startswith(tag):
            return n[len(tag):]
    return n


def pick_node(nodes: List[Dict[str, Any]], prefixes: List[str]) -> Optional[Dict[str, Any]]:
    """按前缀挑选节点，优先含 [ h12 ] 的可靠节点，排除 UDP/IPv6/0.5x。"""
    # 优先: 前缀匹配 + [h12] + 非坏标记
    for n in nodes:
        name = _display_name(n.get("name", ""))
        if not _is_good(name):
            continue
        if any(name.startswith(p) for p in prefixes) and "[ h12 ]" in name:
            return n
    # 次选: 前缀匹配 + 非坏标记
    for n in nodes:
        name = _display_name(n.get("name", ""))
        if not _is_good(name):
            continue
        if any(name.startswith(p) for p in prefixes):
            return n
    return None


# ---------------------------------------------------------------------------
# 配置生成
# ---------------------------------------------------------------------------
def _proxy_block(nodes: List[Dict[str, Any]]) -> str:
    """把节点 dict 列表渲染为 mihomo proxies 段。"""
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


def _listener_block(mapping: Dict[str, str]) -> str:
    lines = ["listeners:"]
    for region, cfg in REGIONS.items():
        node_name = mapping.get(region)
        if not node_name:
            continue
        lines.append(f"  - name: {region}")
        lines.append("    type: mixed")
        lines.append("    listen: 127.0.0.1")
        lines.append(f"    port: {cfg['port']}")
        lines.append(f'    proxy: "{node_name}"')
        lines.append("    udp: true")
    return "\n".join(lines)


def build_config(nodes: List[Dict[str, Any]], mapping: Dict[str, str]) -> str:
    """生成完整 config.yaml 文本。"""
    parts = [CONFIG_HEADER, _proxy_block(nodes), "\n", _listener_block(mapping), "\n", "rules:\n  - MATCH,DIRECT\n"]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 持久化与热重载
# ---------------------------------------------------------------------------
def _save_state(url: str, mapping: Dict[str, str]) -> None:
    state = {
        "subscription_url": url,
        "mapping": mapping,
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
    """通过 mihomo external-controller 热重载 config.yaml。"""
    url = f"{CONTROLLER_URL}/configs?force=true"
    try:
        resp = requests.put(
            url,
            headers={"Authorization": f"Bearer {CONTROLLER_SECRET}"},
            json={"path": str(CONFIG_PATH)},
            timeout=10,
        )
        return {"ok": resp.status_code in (200, 204), "http": resp.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def generate_and_reload(url: str) -> Dict[str, Any]:
    """抓取订阅 -> 挑选地区节点 -> 写配置 -> 热重载。返回结果。"""
    text = fetch_subscription(url)
    nodes = parse_subscription(text)
    if not nodes:
        raise ValueError("未能从订阅中解析出任何节点")

    mapping: Dict[str, str] = {}
    picked = {}
    for region, cfg in REGIONS.items():
        node = pick_node(nodes, cfg["prefixes"])
        if node:
            mapping[region] = node["name"]
            picked[region] = node

    if not mapping:
        raise ValueError("没有匹配到任何地区的节点（检查订阅里是否有对应国家的节点）")

    # 写 nodes.yaml（全量）+ config.yaml（含 listeners）
    nodes_block = _proxy_block(nodes)
    NODES_PATH.write_text(nodes_block + "\n", encoding="utf-8")
    CONFIG_PATH.write_text(build_config(nodes, mapping), encoding="utf-8")
    _save_state(url, mapping)

    reload = _reload_via_controller()

    return {
        "url": url,
        "total_nodes": len(nodes),
        "mapping": mapping,
        "picked": {k: v for k, v in picked.items()},
        "reload": reload,
        "config_path": str(CONFIG_PATH),
    }


def current_status() -> Dict[str, Any]:
    """返回网关当前状态。"""
    state = _load_state()
    ports = {}
    import socket
    for region, cfg in REGIONS.items():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        try:
            s.connect(("127.0.0.1", cfg["port"]))
            ports[region] = True
        except Exception:
            ports[region] = False
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
        "mapping": (state or {}).get("mapping", {}),
        "updated_at": (state or {}).get("updated_at", ""),
        "ports": ports,
        "controller_ok": controller_ok,
        "regions": {
            region: {"port": cfg["port"], "name": cfg["name"]}
            for region, cfg in REGIONS.items()
        },
    }


def reload_existing() -> Dict[str, Any]:
    """不重新抓取，仅用现有 config.yaml 热重载。"""
    if not CONFIG_PATH.exists():
        raise ValueError("config.yaml 不存在，请先配置订阅")
    reload = _reload_via_controller()
    return {"reload": reload, "config_path": str(CONFIG_PATH)}
