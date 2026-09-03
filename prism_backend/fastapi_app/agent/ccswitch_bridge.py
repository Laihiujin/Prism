"""cc-switch 桥接：只读本机 CC Switch 的 SQLite 库，把选中的 provider 应用到项目内。

设计约束（用户明确要求）：
- 不克隆、不集成 cc-switch 源码（它是 Tauri 桌面 GUI，无 CLI），本项目只**读取**它的数据；
- 只**读** `~/.cc-switch/cc-switch.db`，绝不写本机任何配置（~/.claude、~/.hermes 等）；
- 应用的目标只落在**项目内**：tools/hermes-home/config.yaml（Hermes 运行时配置）。

cc-switch providers 表核心字段：
  id, app_type(如 hermes/claude/codex...), name, settings_config(JSON),
  is_current, category, provider_type, meta

settings_config 是自由格式 JSON，**不同 app_type 结构完全不同**（对齐 cc-switch
源码 provider.rs 的 resolve_usage_credentials 分支）：
- hermes:     {"base_url", "api_key", "models": [...]}（扁平 snake_case）
- claude:     {"env": {"ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"/"ANTHROPIC_API_KEY",
                       "ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_*_MODEL"}}
- codex:      {"auth": {"OPENAI_API_KEY"}, "config": "<TOML>"}（base_url 在 TOML 里）
- gemini:     {"env": {"GOOGLE_GEMINI_BASE_URL", "GEMINI_API_KEY"/"GOOGLE_API_KEY"}}
- grokbuild:  {"config": "<TOML>"}（base_url/api_key 在 TOML [models.<default>] 里）
- opencode:   {"options": {"baseURL", "apiKey"}}
- openclaw:   {"baseUrl", "apiKey"}（扁平 camelCase）
- pi:         {"apiKey", ...}
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from loguru import logger

from .hermes_config import write_agent_config
from .hermes_agent import reset_hermes_agent

# 可被环境变量覆盖（测试/容器场景）
CCSWITCH_DB_PATH_ENV = "CCSWITCH_DB_PATH"
DEFAULT_CCSWITCH_DB = Path.home() / ".cc-switch" / "cc-switch.db"

# cc-switch 支持的 agent 类型（对齐 src-tauri/src/app_config.rs AppType::as_str）
APP_TYPES = (
    "claude",
    "claude-desktop",
    "codex",
    "gemini",
    "grokbuild",
    "opencode",
    "openclaw",
    "hermes",
    "pi",
)


def get_ccswitch_db_path() -> Path:
    raw = (os.getenv(CCSWITCH_DB_PATH_ENV) or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return DEFAULT_CCSWITCH_DB


def ccswitch_available() -> bool:
    return get_ccswitch_db_path().is_file()


def _connect_ro() -> sqlite3.Connection:
    """只读连接（URI mode=ro，杜绝任何写入）。"""
    path = get_ccswitch_db_path()
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_settings_config(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _first_non_empty(env: Dict[str, Any], keys: List[str]) -> str:
    """按顺序取第一个非空字符串值（镜像 cc-switch 前端 JS 的 `a || b || c` 语义）。"""
    for key in keys:
        val = env.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return ""


def _parse_toml(text: Optional[str]) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    try:
        import toml

        data = toml.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _codex_base_url(config_text: Optional[str]) -> str:
    """从 Codex config.toml 提取 base_url：优先活跃 [model_providers.<name>].base_url，回退顶层 base_url。"""
    doc = _parse_toml(config_text)
    if not doc:
        return ""
    active = doc.get("model_provider")
    if isinstance(active, str) and active:
        providers = doc.get("model_providers")
        if isinstance(providers, dict):
            section = providers.get(active)
            if isinstance(section, dict):
                base_url = section.get("base_url")
                if isinstance(base_url, str) and base_url.strip():
                    return base_url.strip().rstrip("/")
    top = doc.get("base_url")
    if isinstance(top, str) and top.strip():
        return top.strip().rstrip("/")
    return ""


def _codex_models(config_text: Optional[str]) -> List[Dict[str, str]]:
    """从 Codex config.toml 提取活跃 model_provider 下的模型（model / model_prompt 字段）。"""
    doc = _parse_toml(config_text)
    if not doc:
        return []
    active = doc.get("model_provider")
    if isinstance(active, str) and active:
        providers = doc.get("model_providers")
        if isinstance(providers, dict):
            section = providers.get(active)
            if isinstance(section, dict):
                model = section.get("model")
                if isinstance(model, str) and model.strip():
                    return [{"id": model.strip(), "name": model.strip()}]
    model = doc.get("model")
    if isinstance(model, str) and model.strip():
        return [{"id": model.strip(), "name": model.strip()}]
    return []


def _grok_model_config(config_text: Optional[str]) -> Tuple[str, str, List[Dict[str, str]]]:
    """从 Grok Build config.toml 提取 (base_url, api_key, models)。

    结构：models.default 指向 [model.<name>]，其下 base_url / api_key / model。
    """
    doc = _parse_toml(config_text)
    if not doc:
        return "", "", []
    models = doc.get("models")
    default_model = models.get("default") if isinstance(models, dict) else None
    if not isinstance(default_model, str) or not default_model:
        return "", "", []
    model_map = doc.get("model")
    section = model_map.get(default_model) if isinstance(model_map, dict) else None
    if not isinstance(section, dict):
        return "", "", []
    base_url = section.get("base_url") if isinstance(section.get("base_url"), str) else ""
    api_key = section.get("api_key") if isinstance(section.get("api_key"), str) else ""
    model = section.get("model") if isinstance(section.get("model"), str) else ""
    models_out: List[Dict[str, str]] = []
    if model.strip():
        models_out.append({"id": model.strip(), "name": model.strip()})
    return base_url.strip().rstrip("/"), api_key.strip(), models_out


def _extract_credentials(settings: Dict[str, Any], app_type: str) -> Tuple[str, str]:
    """按 app_type 从 settings_config 提取 (base_url, api_key)。镜像 cc-switch provider.rs 分支。"""
    at = (app_type or "").lower()
    if at == "codex":
        auth = settings.get("auth")
        auth = auth if isinstance(auth, dict) else {}
        api_key = _first_non_empty(auth, ["OPENAI_API_KEY"])
        config_text = settings.get("config")
        config_text = config_text if isinstance(config_text, str) else ""
        return _codex_base_url(config_text), api_key
    if at == "gemini":
        env = settings.get("env")
        env = env if isinstance(env, dict) else {}
        base_url = env.get("GOOGLE_GEMINI_BASE_URL") if isinstance(env.get("GOOGLE_GEMINI_BASE_URL"), str) else ""
        api_key = _first_non_empty(env, ["GEMINI_API_KEY", "GOOGLE_API_KEY"])
        return base_url.strip(), api_key
    if at == "grokbuild":
        config_text = settings.get("config")
        config_text = config_text if isinstance(config_text, str) else ""
        base_url, api_key, _ = _grok_model_config(config_text)
        return base_url, api_key
    if at == "opencode":
        options = settings.get("options")
        options = options if isinstance(options, dict) else {}
        base_url = options.get("baseURL") if isinstance(options.get("baseURL"), str) else ""
        api_key = options.get("apiKey") if isinstance(options.get("apiKey"), str) else ""
        return base_url.strip(), api_key
    if at == "openclaw":
        base_url = settings.get("baseUrl") if isinstance(settings.get("baseUrl"), str) else ""
        api_key = settings.get("apiKey") if isinstance(settings.get("apiKey"), str) else ""
        return base_url.strip(), api_key
    if at == "pi":
        base_url = settings.get("baseUrl") if isinstance(settings.get("baseUrl"), str) else ""
        api_key = settings.get("apiKey") if isinstance(settings.get("apiKey"), str) else ""
        return base_url.strip(), api_key
    if at in ("claude", "claude-desktop"):
        env = settings.get("env")
        env = env if isinstance(env, dict) else {}
        base_url = env.get("ANTHROPIC_BASE_URL") if isinstance(env.get("ANTHROPIC_BASE_URL"), str) else ""
        api_key = _first_non_empty(
            env, ["ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "GOOGLE_API_KEY"]
        )
        return base_url.strip(), api_key
    # hermes 及未知类型：扁平 snake_case（向后兼容）
    base_url = settings.get("base_url") if isinstance(settings.get("base_url"), str) else ""
    api_key = settings.get("api_key") if isinstance(settings.get("api_key"), str) else ""
    return base_url.strip(), api_key


def _extract_models(settings: Dict[str, Any], app_type: str) -> List[Dict[str, str]]:
    """按 app_type 从 settings_config 提取模型列表（不足时为空，靠 /v1/models 在线抓取）。"""
    at = (app_type or "").lower()
    # 通用：顶层 models 数组（hermes / chat_completions 类）
    raw = settings.get("models")
    if isinstance(raw, list) and raw:
        out: List[Dict[str, str]] = []
        for m in raw:
            if isinstance(m, dict):
                mid = m.get("id")
                if mid:
                    out.append({"id": str(mid), "name": str(m.get("name") or mid)})
            elif isinstance(m, str) and m.strip():
                out.append({"id": m.strip(), "name": m.strip()})
        if out:
            return out
    if at == "codex":
        config_text = settings.get("config")
        config_text = config_text if isinstance(config_text, str) else ""
        return _codex_models(config_text)
    if at == "grokbuild":
        config_text = settings.get("config")
        config_text = config_text if isinstance(config_text, str) else ""
        _, _, models = _grok_model_config(config_text)
        return models
    if at in ("claude", "claude-desktop"):
        env = settings.get("env")
        env = env if isinstance(env, dict) else {}
        seen: List[str] = []
        for key in (
            "ANTHROPIC_MODEL",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL",
            "ANTHROPIC_DEFAULT_SONNET_MODEL",
            "ANTHROPIC_DEFAULT_OPUS_MODEL",
            "ANTHROPIC_SMALL_FAST_MODEL",
        ):
            val = env.get(key)
            if isinstance(val, str) and val.strip() and val.strip() not in seen:
                seen.append(val.strip())
        return [{"id": m, "name": m} for m in seen]
    if at == "opencode":
        options = settings.get("options")
        options = options if isinstance(options, dict) else {}
        model = options.get("model")
        if isinstance(model, str) and model.strip():
            return [{"id": model.strip(), "name": model.strip()}]
        return []
    if at == "openclaw":
        # OpenClaw additive 模式下模型挂在 models.providers.<name>.models 下
        providers = settings.get("models")
        providers = providers.get("providers") if isinstance(providers, dict) else None
        if isinstance(providers, dict):
            out = []
            for p in providers.values():
                if not isinstance(p, dict):
                    continue
                pm = p.get("models")
                if isinstance(pm, dict):
                    out.extend({"id": str(k), "name": str(k)} for k in pm.keys())
                elif isinstance(pm, list):
                    out.extend(
                        {"id": str(x.get("id") or x) if isinstance(x, dict) else str(x),
                         "name": str(x.get("name") or x.get("id") or x) if isinstance(x, dict) else str(x)}
                        for x in pm
                    )
            return out
        return []
    return []


def _build_provider(row: sqlite3.Row) -> Dict[str, Any]:
    settings = _parse_settings_config(row["settings_config"])
    app_type = row["app_type"] or ""
    base_url, api_key = _extract_credentials(settings, app_type)
    models = _extract_models(settings, app_type)

    # provider_type 存在 meta JSON 里（如表无此列则回退空串）
    provider_type = ""
    meta_raw = row["meta"] if "meta" in row.keys() else None
    meta = _parse_settings_config(meta_raw) if isinstance(meta_raw, str) else {}
    if isinstance(meta, dict):
        pt = meta.get("provider_type")
        if isinstance(pt, str):
            provider_type = pt
    if not provider_type and "provider_type" in row.keys():
        pt = row["provider_type"]
        if isinstance(pt, str):
            provider_type = pt

    # api_mode：claude 类走 Anthropic Messages；codex 走 Responses；其余默认 OpenAI 兼容
    api_mode = settings.get("api_mode")
    if not isinstance(api_mode, str) or not api_mode:
        at = app_type.lower()
        if at in ("claude", "claude-desktop"):
            api_mode = "anthropic"
        elif at == "codex":
            api_mode = "responses"
        elif at == "gemini":
            api_mode = "gemini"
        else:
            api_mode = "chat_completions"

    return {
        "id": row["id"],
        "app_type": app_type,
        "name": row["name"] or settings.get("name") or row["id"],
        "is_current": bool(row["is_current"]),
        "category": row["category"] or "",
        "provider_type": provider_type,
        "base_url": base_url,
        "api_key": api_key,
        "api_mode": api_mode,
        "models": models,
        # 完整 settings_config 只在显式需要时返回（含 key，前端做掩码）
        "settings_config": settings,
    }


def list_providers(app_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """列出 cc-switch 中的 provider 档案（可选按 app_type 过滤）。"""
    if not ccswitch_available():
        return []
    conn = _connect_ro()
    try:
        if app_type:
            rows = conn.execute(
                "SELECT * FROM providers WHERE app_type = ? ORDER BY sort_index, created_at",
                (app_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM providers ORDER BY app_type, sort_index, created_at"
            ).fetchall()
        return [_build_provider(r) for r in rows]
    finally:
        conn.close()


def get_provider(app_type: str, provider_id: str) -> Optional[Dict[str, Any]]:
    if not ccswitch_available():
        return None
    conn = _connect_ro()
    try:
        row = conn.execute(
            "SELECT * FROM providers WHERE app_type = ? AND id = ?",
            (app_type, provider_id),
        ).fetchone()
        return _build_provider(row) if row else None
    finally:
        conn.close()


def get_current_provider(app_type: str) -> Optional[Dict[str, Any]]:
    """当前在 cc-switch 中选中的 provider（is_current=1）。"""
    if not ccswitch_available():
        return None
    conn = _connect_ro()
    try:
        row = conn.execute(
            "SELECT * FROM providers WHERE app_type = ? AND is_current = 1",
            (app_type,),
        ).fetchone()
        return _build_provider(row) if row else None
    finally:
        conn.close()


def get_status() -> Dict[str, Any]:
    """cc-switch 桥接状态：库是否存在、各 app_type 的 provider 数、当前选中。"""
    if not ccswitch_available():
        return {
            "available": False,
            "db_path": str(get_ccswitch_db_path()),
            "detail": "未检测到 cc-switch 数据库（~/.cc-switch/cc-switch.db）。请先在本机 CC Switch 中添加 provider。",
        }
    conn = _connect_ro()
    try:
        rows = conn.execute(
            "SELECT app_type, COUNT(*) AS cnt, SUM(is_current) AS cur FROM providers GROUP BY app_type"
        ).fetchall()
        by_type = {
            r["app_type"]: {"count": r["cnt"], "current": int(r["cur"] or 0)} for r in rows
        }
        return {
            "available": True,
            "db_path": str(get_ccswitch_db_path()),
            "providers_by_type": by_type,
        }
    finally:
        conn.close()


def _provider_to_llm_config(
    provider: Dict[str, Any], model: Optional[str] = None, app_type: str = "hermes"
) -> Dict[str, Any]:
    """把 cc-switch 的 provider 档案映射成项目 Hermes 的 llm 配置。"""
    api_mode = (provider.get("api_mode") or "chat_completions").lower()
    base_url = (provider.get("base_url") or "").strip()

    # provider 类型映射：chat_completions → custom（OpenAI 兼容）；anthropic → anthropic
    if api_mode in ("anthropic", "anthropic_messages", "anthropic_completion"):
        llm_provider = "anthropic"
    elif api_mode == "lmstudio":
        llm_provider = "lmstudio"
    else:
        llm_provider = "custom"

    chosen_model = (model or "").strip()
    if not chosen_model:
        models = provider.get("models") or []
        if models:
            chosen_model = str(models[0].get("id") or "").strip()

    return {
        "provider": llm_provider,
        "model": chosen_model,
        "api_key": (provider.get("api_key") or "").strip(),
        "base_url": base_url,
    }


def _resolve_provider_for_action(
    app_type: str = "hermes", provider_id: Optional[str] = None
) -> Dict[str, Any]:
    """公共解析：显式 provider_id → 当前选中(is_current=1) → 第一个。

    读库失败/为空时抛 FileNotFoundError / ValueError，供各动作复用。
    """
    if not ccswitch_available():
        raise FileNotFoundError(
            f"未检测到 cc-switch 数据库: {get_ccswitch_db_path()}。请先在本机 CC Switch 中添加 provider。"
        )
    if provider_id:
        provider = get_provider(app_type, provider_id)
        if not provider:
            raise ValueError(f"cc-switch 中不存在 {app_type} provider: {provider_id}")
        return provider
    provider = get_current_provider(app_type)
    if not provider:
        providers = list_providers(app_type)
        if providers:
            provider = providers[0]
    if not provider:
        raise ValueError(f"cc-switch 中没有可用的 {app_type} provider，请先在 CC Switch 中添加。")
    return provider


def _models_url_candidates(base_url: str) -> List[str]:
    """按 cc-switch 官方的候选逻辑生成 models 端点候选列表。

    - base 已是 …/models 结尾 → 直接用
    - base 以 /v1 结尾 → {base}/models
    - 其他 → {base}/v1/models、{base}/models
    """
    base = (base_url or "").strip().rstrip("/")
    if not base:
        raise ValueError("provider 缺少 base_url，无法抓取模型")
    if base.endswith("/models"):
        return [base]
    if base.endswith("/v1"):
        return [f"{base}/models"]
    return [f"{base}/v1/models", f"{base}/models"]


async def fetch_provider_models(
    app_type: str = "hermes", provider_id: Optional[str] = None
) -> Dict[str, Any]:
    """调用 provider 的 models 端点抓取全部可用模型（只读，不写任何配置）。

    依次尝试候选 URL（/v1/models、/models），兼容 OpenAI 兼容 / Anthropic / Codex 端点。
    """
    provider = _resolve_provider_for_action(app_type, provider_id)
    base_url = (provider.get("base_url") or "").strip()
    api_key = (provider.get("api_key") or "").strip()
    candidates = _models_url_candidates(base_url)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    last_error = ""
    async with httpx.AsyncClient(timeout=15.0) as client:
        for url in candidates:
            try:
                resp = await client.get(url, headers=headers)
            except httpx.TimeoutException:
                last_error = f"请求超时：{url}"
                continue
            except httpx.HTTPError as exc:
                last_error = f"请求失败：{exc}"
                continue

            if resp.status_code in (401, 403):
                raise ValueError(f"鉴权失败（HTTP {resp.status_code}），请检查 api_key")
            if resp.status_code >= 400:
                last_error = f"{url} 返回 HTTP {resp.status_code}"
                continue

            data = resp.json()
            items = data.get("data") or data.get("models") or []
            models = [
                {"id": str(m["id"]), "name": str(m.get("name") or m["id"])}
                for m in items
                if isinstance(m, dict) and m.get("id")
            ]
            if not models:
                raise ValueError(f"provider「{provider['name']}」返回了空模型列表")

            logger.info(f"[CCSwitch] 从 {provider['name']} 抓取到 {len(models)} 个模型（{url}）")
            return {
                "provider": {"id": provider["id"], "name": provider["name"], "base_url": base_url},
                "models": models,
            }

    raise ValueError(f"抓取模型失败：{last_error or '未知错误'}")


async def test_provider(
    app_type: str = "hermes",
    provider_id: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """测试 provider 连接与（可选）模型可用性：先探 /v1/models，再发最小对话。"""
    provider = _resolve_provider_for_action(app_type, provider_id)
    base_url = (provider.get("base_url") or "").strip()
    api_key = (provider.get("api_key") or "").strip()
    if not base_url:
        raise ValueError(f"provider「{provider['name']}」没有 base_url，无法测试")

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1) 连接/鉴权探测（依次尝试候选 models 端点）
            probe_error = None
            for url in _models_url_candidates(base_url):
                try:
                    resp = await client.get(url, headers=headers)
                except httpx.HTTPError as exc:
                    probe_error = f"请求失败：{exc}"
                    continue
                if resp.status_code in (401, 403):
                    return {
                        "ok": False, "stage": "连接/鉴权", "status_code": resp.status_code,
                        "error": "api_key 无效或未授权", "provider": provider["name"],
                    }
                if resp.status_code >= 400:
                    probe_error = f"{url} 返回 HTTP {resp.status_code}"
                    continue
                probe_error = None
                break
            if probe_error:
                return {
                    "ok": False, "stage": "连接",
                    "error": probe_error, "provider": provider["name"],
                }

            # 2) 模型级测试（给定 model 时发最小对话）
            if model:
                chat_url = f"{base_url.rstrip('/')}/chat/completions"
                body = {
                    "model": model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 8,
                }
                r2 = await client.post(chat_url, headers=headers, json=body)
                if r2.status_code >= 400:
                    return {
                        "ok": False, "stage": "模型调用", "status_code": r2.status_code,
                        "error": r2.text[:200], "provider": provider["name"], "model": model,
                    }
    except httpx.TimeoutException:
        return {"ok": False, "error": "请求超时", "provider": provider["name"]}
    except httpx.HTTPError as exc:
        return {"ok": False, "error": f"请求失败：{exc}", "provider": provider["name"]}

    latency_ms = int((time.monotonic() - start) * 1000)
    return {
        "ok": True,
        "latency_ms": latency_ms,
        "provider": provider["name"],
        "model": model or None,
    }


async def apply_provider_to_hermes(
    app_type: str = "hermes",
    provider_id: Optional[str] = None,
    model: Optional[str] = None,
    max_turns: int = 12,
) -> Dict[str, Any]:
    """把 cc-switch 中的 provider 应用到项目内的 Hermes Agent。

    provider_id 为空时优先用 cc-switch 当前选中(is_current=1)的 provider；
    仍没有则取第一个。应用只写项目内配置(tools/hermes-home/config.yaml)。
    app_type 支持 cc-switch 全部类型（claude/codex/gemini/…），来源 provider
    的 base_url/api_key 会按各自 settings_config 结构解析后映射成 Hermes llm 配置。
    """
    provider = _resolve_provider_for_action(app_type, provider_id)

    llm = _provider_to_llm_config(provider, model, app_type=app_type)
    if not llm.get("model"):
        raise ValueError(f"provider「{provider['name']}」没有可用模型，请在 cc-switch 中补充。")

    payload = {
        "llm": llm,
        "runtime": {"max_turns": int(max_turns)},
    }
    config_path = write_agent_config(payload)
    await reset_hermes_agent()
    logger.info(f"[CCSwitch] 已应用 provider「{provider['name']}」到 Hermes: {config_path}")

    return {
        "provider": provider,
        "llm": llm,
        "config_path": str(config_path),
        "message": f"已把 cc-switch provider「{provider['name']}」应用到项目 Hermes。",
    }
