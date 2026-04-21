"""
System prompts for the OpenClaw/Hermes orchestration layer.
"""

from pathlib import Path

import yaml

from fastapi_app.core.config import settings


def _load_unified_prompts():
    """Load prompt definitions from the unified config file."""
    try:
        config_path = settings.BASE_DIR / "config" / "ai_prompts_unified.yaml"
        if not config_path.exists():
            config_path = settings.BASE_DIR / "config" / "ai_prompts.yaml"

        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as handle:
                return yaml.safe_load(handle) or {}
        return {}
    except Exception as exc:
        print(f"[Prompts] Failed to load prompts config: {exc}")
        return {}


_PROMPTS_CONFIG = _load_unified_prompts()


def get_system_prompt(key: str) -> str:
    """Return a system prompt by key from the config tree."""
    if "automation" in _PROMPTS_CONFIG and key in _PROMPTS_CONFIG["automation"]:
        return _PROMPTS_CONFIG["automation"][key].get("system_prompt", "")

    if "content_generation" in _PROMPTS_CONFIG and key in _PROMPTS_CONFIG["content_generation"]:
        return _PROMPTS_CONFIG["content_generation"][key].get("system_prompt", "")

    if key in _PROMPTS_CONFIG:
        config = _PROMPTS_CONFIG[key]
        if isinstance(config, dict):
            return config.get("system_prompt", "")

    return ""


SYSTEM_PROMPT = get_system_prompt("openclaw_agent") or get_system_prompt("agent_orchestrator") or """
你现在是 SynapseAutomation 的矩阵调度系统（OpenClaw + Hermes Agent）。
你的职责是把用户目标转成可执行的自动化步骤，并优先调用系统工具完成任务。

规则：
1. 先判断任务类型：upload、publish、collect、analyze、check、maintain。
2. 用户只是咨询方案时，不调用工具，直接给可执行建议。
3. 数据采集优先使用 API 工具，不滥用浏览器自动化。
4. 发布脚本必须可回滚、可重复、结构化输出。
5. 工具失败时必须返回失败点、原因和下一步建议，不能空转。
"""


USER_PROMPT_TEMPLATE = """
## 当前系统状态

{context}

## 用户需求

{user_request}

## 执行要求

1. 先分析任务类型
2. 读取必要上下文
3. 生成或执行最小可行步骤
4. 需要确认时明确告知
5. 返回结果、失败点和下一步建议
"""


AGENT_TRIGGER_PROMPT = """
当任务涉及以下场景时，应优先走 OpenClaw/Hermes 工具链：

1. 多账号批量发布或分发
2. 多素材批量处理
3. 跨平台排期与差异化文案
4. 平台数据采集与数据回收
5. 脚本生成、保存与执行
6. 系统状态查询、诊断与维护

以下场景直接回答即可，不必调用工具：
1. 功能说明或使用方法咨询
2. 单纯概念解释
3. 简单问答或策略讨论
"""


SYSTEM_PROMPT_WITH_AGENT_RULES = SYSTEM_PROMPT + "\n\n---\n\n" + AGENT_TRIGGER_PROMPT
