"""
平台渠道可见性（CMS「隐藏平台渠道」开关）—— 全局过滤的单一事实来源。

隐藏某平台渠道后，该平台在 账号管理 / 矩阵发布 / 统计 全链路不可见且不可选
（账号数据保留，不会被删除）。发布请求若显式带上已隐藏平台会被拒绝。

存储：
1) 仓库根 .env 的 `PRISM_HIDDEN_PLATFORMS`（逗号分隔的平台别名，如
   `PRISM_HIDDEN_PLATFORMS=baijiahao,kuaishou`）—— 与 CMS 现有
   douyin-login-mode/browser-headless 的 .env 持久化方式一致；
2) 可选 JSON（PRISM_RUNTIME_SETTINGS_PATH 里的 `hiddenPlatforms` 列表）——
   桌面端 runtime settings 一并读取，两者并集生效。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from loguru import logger

from . import registry


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _env_value() -> str:
    env_file = _repo_root() / ".env"
    try:
        from dotenv import dotenv_values

        return str((dotenv_values(env_file) or {}).get("PRISM_HIDDEN_PLATFORMS") or "").strip()
    except Exception:
        return os.getenv("PRISM_HIDDEN_PLATFORMS", "").strip()


def _runtime_json_hidden() -> Set[str]:
    raw_path = os.getenv("PRISM_RUNTIME_SETTINGS_PATH", "").strip()
    if not raw_path:
        return set()
    try:
        payload = json.loads(Path(raw_path).read_text(encoding="utf-8"))
        raw = payload.get("hiddenPlatforms") or []
        if isinstance(raw, str):
            raw = [raw]
        return {str(x).strip().lower() for x in raw if str(x).strip()}
    except (OSError, ValueError, TypeError):
        return set()


def _normalize(entries: Iterable[str]) -> Set[str]:
    """平台别名/代码/名称 → 平台代码 int。未知项跳过。"""
    codes: Set[int] = set()
    for raw in entries:
        key = str(raw).strip().lower()
        if not key:
            continue
        code = registry.normalize_platform_code(key)
        if code is not None:
            codes.add(code)
        # 兼容中文名/平台名
        for meta_code, meta in registry._PLATFORM_META.items():
            if str(meta["name"]) == key or key in (a.lower() for a in meta.get("aliases", [])):
                codes.add(meta_code)
    return codes


def hidden_platform_codes() -> Set[int]:
    """当前被隐藏的平台代码集合（env ∪ runtime json）。"""
    env_raw = _env_value()
    parts = [p for p in env_raw.replace("，", ",").split(",") if p.strip()]
    return _normalize(parts) | _normalize(_runtime_json_hidden())


def is_hidden(platform: Any) -> bool:
    """platform 可以是代码 int / 别名 str / 平台名 str。"""
    if platform is None:
        return False
    code = registry.normalize_platform_code(platform)
    if code is None:
        for meta_code, meta in registry._PLATFORM_META.items():
            if str(meta["name"]) == str(platform):
                code = meta_code
                break
    if code is None:
        return False
    return code in hidden_platform_codes()


def visible_platform_codes() -> List[int]:
    """按注册表顺序返回可见平台代码。"""
    return [code for code in registry._PLATFORM_META if code not in hidden_platform_codes()]


def all_platform_meta() -> List[Dict[str, Any]]:
    """前端 CMS 用：全部平台 + hidden 状态（用于渲染勾选开关）。"""
    hidden = hidden_platform_codes()
    result = []
    for code, meta in registry._PLATFORM_META.items():
        result.append(
            {
                "code": code,
                "name": meta["name"],
                "alias": meta["aliases"][0] if meta.get("aliases") else "",
                "hidden": code in hidden,
            }
        )
    return result


def set_hidden_platforms(aliases_or_codes: Iterable[Any]) -> Dict[str, Any]:
    """写回 .env 的 PRISM_HIDDEN_PLATFORMS（CMS 开关用）。"""
    normalized = _normalize(aliases_or_codes)
    alias_list = []
    for code in sorted(normalized):
        meta = registry._PLATFORM_META.get(code)
        if meta and meta.get("aliases"):
            alias_list.append(meta["aliases"][0])
    env_file = _repo_root() / ".env"
    try:
        from dotenv import set_key

        set_key(str(env_file), "PRISM_HIDDEN_PLATFORMS", ",".join(alias_list), quote_mode="never")
    except Exception as e:
        logger.warning(f"[Channels] write .env failed: {e}")
        raise
    return {"hidden": alias_list}


def apply_hidden_filter(accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """账号列表过滤：隐藏平台的账号不返回（保留数据）。"""
    if not hidden_platform_codes():
        return accounts
    hidden_names = {registry._PLATFORM_META[c]["name"] for c in hidden_platform_codes()}
    aliases = {registry._PLATFORM_META[c]["aliases"][0] for c in hidden_platform_codes()}
    out = []
    for acc in accounts:
        pf = str(acc.get("platform") or "").lower()
        if pf in hidden_names or pf in aliases:
            continue
        out.append(acc)
    return out
