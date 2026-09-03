"""Platform-aware title & topic generation helpers.

These glue Prism's per-platform 网感 rules in config/ai_prompts_unified.yaml
(``content_generation.title_generation.platform_tuning`` / ``tags_generation
.platform_rules``) and myUtils/platform_metadata_adapter.py limits onto the
batch AI metadata generation path, so generating "title + topics" for a given
platform actually produces a platform-appropriate, publishable result instead
of one generic blob.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is a project dependency
    yaml = None


# Per-platform limits. Title caps come from myUtils/platform_metadata_adapter.py;
# max_tags comes from config/ai_prompts_unified.yaml tags_generation.platform_rules.
# Per-platform RED-LINE limits (must never be exceeded). These mirror the hard
# caps enforced by the production uploaders (the ones that would otherwise break
# publishing), taking precedence over the generic rules in ai_prompts_unified.yaml:
#   - douyin title: >20 chars raises  (uploader/douyin_uploader/main_refactored.py)
#   - xiaohongshu title: filled to [20]; tags capped at 10 (fill_tags max_tags)
#   - kuaishou: combined field; tags[:3]
#   - bilibili / youtube / others: platform_metadata_adapter caps
PLATFORM_META: Dict[str, Dict[str, Any]] = {
    "douyin": {"code": 3, "label": "抖音", "title_max": 20, "max_tags": 4, "desc_max": 2000},
    "xiaohongshu": {"code": 1, "label": "小红书", "title_max": 20, "max_tags": 10, "desc_max": 1000},
    "kuaishou": {"code": 4, "label": "快手", "title_max": None, "max_tags": 3, "desc_max": None},
    "bilibili": {"code": 5, "label": "B站", "title_max": 80, "max_tags": 12, "desc_max": 2000},
    "video_account": {"code": 2, "label": "视频号", "title_max": None, "max_tags": None, "desc_max": None},
    "tiktok": {"code": 6, "label": "TikTok", "title_max": None, "max_tags": 5, "desc_max": 2200},
    "youtube": {"code": 7, "label": "YouTube", "title_max": 100, "max_tags": 15, "desc_max": 5000},
}

# Default output language per platform. TikTok targets an international audience, so
# title/topic generation defaults to bilingual (中文 + English) unless overridden.
PLATFORM_LANGUAGE_DEFAULT: Dict[str, str] = {
    "tiktok": "bilingual",
}

# Allowed language values and their prompt guidance.
LANGUAGE_GUIDANCE: Dict[str, str] = {
    "bilingual": (
        "输出语言：标题与话题采用中英双语 —— 标题形如「中文标题 | English Title」；"
        "话题同时给出中文 + 英文标签（如 #中文标签 和 #english_tag），便于跨语言搜索。"
    ),
    "en": "输出语言：标题与话题以英文为主，适合面向海外观众。",
    "zh": "输出语言：标题与话题以中文为主。",
}

# Platform-specific 网感 guidance injected into the generation prompt. The short
# "style" comes from the editable YAML; this gives the structural hook guidance.
PLATFORM_GUIDANCE: Dict[str, str] = {
    "douyin": (
        "标题：短促强钩子、口语化，开头给出冲突/结果/悬念/情绪；不要堆形容词，"
        "必须包含一个可验证信息点（人物/行为/结果/场景/情绪）。"
        "话题：1 个品类/IP 标签 + 1 个内容形态标签 + 1–2 个细分标签，避免全是大词。"
    ),
    "xiaohongshu": (
        "标题：像笔记标题，关键词清晰、审美克制、有温度但不浮夸；"
        "结构可用「主体 + 场景/方法 + 结果/承诺」，如「新手也能学会的 X」。"
        "话题：泛流量（人群/场景）+ 垂直品类 + 细分话题组合。"
    ),
    "tiktok": (
        "标题：面向海外观众，开头即钩子/结果/好奇心，语言简洁明了（默认中英双语见 LANGUAGE_GUIDANCE）；"
        "话题：1 个品类 + 1 个内容形态 + 1–2 个细分，含英文标签以利于海外搜索。"
    ),
}


def _config_path() -> Path:
    return Path(__file__).parent.parent / "config" / "ai_prompts_unified.yaml"


def load_ai_prompts_config() -> Dict[str, Any]:
    """Load config/ai_prompts_unified.yaml; return {} when missing/unreadable."""
    path = _config_path()
    if yaml is None or not path.is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _platform_style(config: Dict[str, Any], platform: str) -> str:
    content_gen = config.get("content_generation") or {}
    tune = (content_gen.get("title_generation") or {}).get("platform_tuning") or {}
    style = (tune.get(platform) or {}).get("style") or ""
    return str(style).strip()


def _platform_max_tags(config: Dict[str, Any], platform: str) -> Optional[int]:
    content_gen = config.get("content_generation") or {}
    rules = (content_gen.get("tags_generation") or {}).get("platform_rules") or {}
    return (rules.get(platform) or {}).get("max_tags")


def resolve_language(language: Optional[str], platform: Optional[str] = None) -> Optional[str]:
    """Normalize an explicit language, or fall back to the platform default.

    Returns None (use the generic 中文-first rule) when nothing is specified and
    the platform has no language default.
    """
    if language:
        key = str(language).strip().lower()
        if key in LANGUAGE_GUIDANCE:
            return key
        # tolerate a few aliases
        alias = {
            "zh-cn": "zh", "cn": "zh", "中文": "zh",
            "en-us": "en", "english": "en", "英文": "en",
            "bi": "bilingual", "both": "bilingual", "中英": "bilingual",
        }.get(key)
        if alias:
            return alias
    if platform:
        return PLATFORM_LANGUAGE_DEFAULT.get(platform)
    return None


def build_metadata_prompt(
    filename: str,
    user_title: Optional[str],
    user_tags: Optional[str],
    platform: Optional[str],
    config: Optional[Dict[str, Any]] = None,
    language: Optional[str] = None,
) -> str:
    """Build a platform-aware AI metadata prompt.

    When ``platform`` is None/unknown this behaves like the legacy generic
    prompt (title <= 30, tags 1-4). Otherwise it injects the platform 网感
    style, title cap and topic cap so the returned title/topics actually fit
    that platform. ``language`` (zh/en/bilingual) overrides the output language;
    TikTok defaults to bilingual when not provided.
    """
    config = config if config is not None else load_ai_prompts_config()
    meta = (PLATFORM_META or {}).get(platform) if platform else None
    lang = resolve_language(language, platform)

    if meta is None:
        title_max = 30
        max_tags = 4
        desc_max = 2000
        platform_block = ""
        tags_block = "3) tags 输出 1-4 个，去重，不要带 # 符号（系统会自动加 #）"
    else:
        label = meta["label"]
        title_max = meta.get("title_max")
        max_tags = meta.get("max_tags", 4)
        desc_max = meta.get("desc_max")
        style = _platform_style(config, platform) or meta["label"]
        guidance = PLATFORM_GUIDANCE.get(platform, "")
        caps = "；".join(
            c for c in [
                f"标题 {title_max} 字以内" if title_max else "",
                f"话题不超过 {max_tags} 个" if max_tags else "",
                f"描述 {desc_max} 字以内" if desc_max else "",
            ] if c
        )
        platform_block = (
            f"\n目标平台：{label}（{platform}）。\n"
            f"平台风格：{style}；{guidance}\n"
            f"执行：{caps}。"
        )
        tags_block = (
            f"3) tags 输出最多 {max_tags} 个，去重，不要带 # 符号（系统会自动加 #）"
        )

    title_hint = f"{title_max}字以内" if title_max else "合理长度"
    desc_hint = f"{desc_max}字以内" if desc_max else "50-120字"
    language_block = ""
    final_lang_note = "4) title/description/tags 全部用中文表达为主，不要表情符号"
    if lang:
        language_block = f"\n{LANGUAGE_GUIDANCE[lang]}"
        # Bilingual/en relax the strict 中文-first rule for language tags only.
        final_lang_note = "4) 不要表情符号；避免英文引号包裹标题"

    return f"""请基于「文件名」以及「用户已有标题/标签」，生成适合短视频平台的 AI 标题、描述和标签，并尽量做"改编优化"而不是完全重写。{platform_block}{language_block}

输入：
- 文件名：{filename}
- 用户标题（可为空）：{user_title or ""}
- 用户标签（可为空，可能为 JSON 数组/空格分隔/逗号分隔）：{user_tags or ""}

输出要求（严格 JSON，禁止 markdown/解释/多余文本）：
{{
  "title": "标题（{title_hint}，中文优先）",
  "description": "描述（{desc_hint}，中文优先）",
  "tags": ["标签1", "标签2", "标签3"]
}}

约束：
1) 如果用户标题/标签存在：保持主题一致、保留核心意思，在其基础上润色优化即可
2) 如出现英文词：翻译为中文（专有名词可保留原文并加中文释义；中英双语场景下保留英文原文）
{tags_block}
{final_lang_note}
"""


def resolve_platform(platform: Optional[str]) -> Optional[str]:
    """Normalize a platform name to a known key, or None when unrecognized."""
    if not platform:
        return None
    key = str(platform).strip().lower()
    aliases = {
        "dy": "douyin", "抖音": "douyin", "douyin": "douyin",
        "xhs": "xiaohongshu", "小红书": "xiaohongshu", "xiaohongshu": "xiaohongshu",
        "ks": "kuaishou", "快手": "kuaishou", "kuaishou": "kuaishou",
        "bili": "bilibili", "bilibili": "bilibili", "b站": "bilibili",
        "视频号": "video_account", "video_account": "video_account", "channels": "video_account", "tencent": "video_account",
        "tiktok": "tiktok", "tk": "tiktok", "youtube": "youtube", "yt": "youtube",
    }
    return aliases.get(key, key if key in PLATFORM_META else None)


def apply_platform_limits(
    platform: Optional[str],
    title: str,
    tags: List[str],
    description: Optional[str] = None,
) -> Tuple[str, List[str], Optional[str]]:
    """Enforce platform RED-LINE limits on generated metadata.

    Truncates the title to the platform cap, caps/dedupes tags, truncates the
    description, and strips any leading ``#`` from tags (stored cleansed; the
    publisher re-adds ``#``). These ceilings come from the production uploaders
    and must never be exceeded.
    """
    meta = (PLATFORM_META or {}).get(platform) if platform else None
    title = str(title or "").strip()
    desc = str(description or "").strip()
    clean_tags: List[str] = []
    for t in tags:
        tag = str(t).strip().lstrip("#").strip()
        if tag and tag not in clean_tags:
            clean_tags.append(tag)

    if meta:
        if meta.get("title_max"):
            title = title[: meta["title_max"]]
        max_tags = meta.get("max_tags")
        if max_tags is not None:
            clean_tags = clean_tags[:max_tags]
        if meta.get("desc_max"):
            desc = desc[: meta["desc_max"]]
    else:
        clean_tags = clean_tags[:4]

    return title, clean_tags, desc


def build_platform_constraint_notes(
    platform: Optional[str],
    language: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """Return a compact platform red-line + style instruction block.

    Used by the /api/v1/ai/chat path so the "标题生成 / 对话模型" also honors the
    per-platform title/topic/description ceilings and style, not just the
    batch endpoint. Empty string when platform is unknown/unspecified.
    """
    resolved = resolve_platform(platform)
    if not resolved:
        return ""
    meta = (PLATFORM_META or {}).get(resolved)
    if not meta:
        return ""

    config = config if config is not None else load_ai_prompts_config()
    label = meta["label"]
    style = _platform_style(config, resolved) or label
    guidance = PLATFORM_GUIDANCE.get(resolved, "")

    caps = []
    if meta.get("title_max"):
        caps.append(f"标题最多 {meta['title_max']} 字（不可超）")
    if meta.get("max_tags"):
        caps.append(f"话题最多 {meta['max_tags']} 个（不可超）")
    if meta.get("desc_max"):
        caps.append(f"描述最多 {meta['desc_max']} 字（不可超）")

    lines = [
        f"目标平台：{label}。",
        f"平台风格：{style}；{guidance}",
    ]
    if caps:
        lines.append("【红线】" + "；".join(caps) + "。")
    lang = resolve_language(language, resolved)
    if lang:
        lines.append(LANGUAGE_GUIDANCE[lang])
    return "\n".join(lines)
