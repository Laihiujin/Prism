"""Single source of truth for the AI text-generation model.

All title/topic (and other text) generation funnels through the SAME model
config that ``/api/v1/ai/chat`` uses: the active ``chat`` row in
``ai_model_configs``. The old ``model_manager`` path (a separate ``config.json``
that could sit at 0 providers) has been removed in favor of this single source.

Only non-streaming completions are needed so far. ``get_ai_chat_config`` is a
plain (sync) reader; ``call_chat_model`` awaits the OpenAI-compatible client.
"""

from __future__ import annotations

from typing import Any, Dict, List


def get_ai_chat_config() -> Dict[str, Any]:
    """Return the active chat model config, or raise when unconfigured."""
    from fastapi_app.api.v1.ai.router import get_ai_config

    cfg = get_ai_config("chat")
    if not cfg:
        raise RuntimeError(
            "Chat 服务未配置：请在「标题生成 / 对话模型」设置里配置 chat 模型"
        )
    return cfg


async def call_chat_model(
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 500,
) -> str:
    """Call the configured chat model (same as /api/v1/ai/chat) and return text."""
    from openai import AsyncOpenAI

    cfg = get_ai_chat_config()
    client = AsyncOpenAI(
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url") or "https://api.siliconflow.cn/v1",
    )
    model_name = cfg.get("model_name") or "deepseek-ai/DeepSeek-V3"
    resp = await client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
    )
    return resp.choices[0].message.content
