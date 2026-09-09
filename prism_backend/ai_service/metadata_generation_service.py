"""Reusable AI title+tags generation for files.

Shared by the HTTP batch endpoint (fastapi_app/api/v1/files/router.py) and the
``generate_ai_metadata`` declaration tool, so the CLI/front-end and the agent all
produce identical platform-aware results. Pure prompt/limit logic lives in
``ai_service.title_topic_generator``; here we wrap DB lookup, model call, JSON
parsing and persistence for one or more file_ids. The model call goes through
``ai_service.llm.call_chat_model`` (the same chat config as /api/v1/ai/chat).
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


def _extract_json_object(content: str) -> Dict[str, Any]:
    """Extract the first balanced top-level JSON object from model output.

    The old ``re.search(r"\{[^}]+\}")`` cannot parse nested objects (e.g. the
    multi-group ``{"groups": [{...}, ...]}`` output), so walk braces instead.
    """
    text = content.strip()
    # Drop markdown fences / prose around the JSON object.
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object found in model output")
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("unbalanced JSON object in model output")


async def _generate_one(
    cursor: Any,
    db: Any,
    prompt_config: Dict[str, Any],
    file_id: int,
    force_regenerate: bool,
    platform: Optional[str],
    language: Optional[str],
    logger: Any,
    group_count: int = 1,
    tags_only_groups: bool = False,
) -> Dict[str, Any]:
    """Generate + persist title/tags for a single file. Returns a result dict.

    ``group_count`` > 1 asks the model for that many differentiated title+tags
    variants; they are stored as JSON in ``file_records.ai_tag_groups`` while
    ``ai_title``/``ai_tags`` keep group #1 (so legacy readers keep working).
    """
    cursor.execute("""
        SELECT id, filename, file_path, title, tags, ai_title, ai_tags
        FROM file_records
        WHERE id = ?
    """, (file_id,))

    row = cursor.fetchone()
    if not row:
        return {"file_id": file_id, "status": "failed", "error": "文件不存在"}

    (
        _file_id_val,
        filename,
        _file_path,
        user_title,
        user_tags,
        existing_ai_title,
        _existing_ai_tags,
    ) = row

    if not force_regenerate and existing_ai_title:
        return {"file_id": file_id, "status": "skipped", "message": "已有AI内容，跳过生成"}

    # 平台网感 prompt（平台风格 + 字数/话题上限 + 可选语言；只出标题+标签）
    from ai_service.title_topic_generator import build_metadata_prompt

    prompt = build_metadata_prompt(
        filename=filename,
        user_title=user_title,
        user_tags=user_tags,
        platform=platform,
        config=prompt_config,
        language=language,
        group_count=group_count,
        tags_only_groups=tags_only_groups,
    )

    # 走与 /api/v1/ai/chat 相同的 chat 模型配置（订阅-deepseek-v4-flash-vision-exp）
    from ai_service.llm import call_chat_model

    content = await call_chat_model(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1500 if group_count and group_count > 1 else 500,
    )

    try:
        metadata = _extract_json_object(content)
    except Exception:
        # 回退：老的正则提取（单组标题+标签场景足够）
        json_match = re.search(r"\{[^}]+\}", content, re.DOTALL)
        metadata = json.loads(json_match.group()) if json_match else json.loads(content)
    # ── 解析：多组（groups[]）或单组（title+tags）两种输出格式 ──
    from ai_service.title_topic_generator import apply_platform_limits

    def _clean_tags(raw_tags: Any) -> List[str]:
        out: List[str] = []
        if isinstance(raw_tags, str):
            raw_tags = [t for t in re.split(r"[\s,，]+", raw_tags) if t and t.strip()]
        if isinstance(raw_tags, list):
            for t in raw_tags:
                s = str(t).strip().lstrip("#").strip()
                if s and s not in out:
                    out.append(s)
        return out

    raw_groups: List[Dict[str, Any]] = metadata.get("groups")
    if isinstance(raw_groups, list) and len(raw_groups) > 0:
        groups: List[Dict[str, Any]] = []
        first_title: str = ""
        first_tags: List[str] = []
        for idx, g in enumerate(raw_groups):
            g = g if isinstance(g, dict) else {}
            title = str(g.get("title", "") or "").strip()
            tags = _clean_tags(g.get("tags"))
            # tags_only_groups：第 2 组起复用第 1 组标题
            if idx > 0 and tags_only_groups and first_title:
                title = first_title
            title, tags = apply_platform_limits(platform=platform, title=title, tags=tags)
            if idx == 0:
                first_title, first_tags = title, tags
            groups.append({"title": title, "tags": tags})

        ai_title, ai_tags = first_title, first_tags
        ai_tag_groups = groups
    else:
        raw_title = str(metadata.get("title", "") or "").strip()
        ai_title, ai_tags = apply_platform_limits(
            platform=platform,
            title=raw_title,
            tags=_clean_tags(metadata.get("tags")),
        )
        ai_tag_groups = [{"title": ai_title, "tags": ai_tags}]

    cursor.execute("""
        UPDATE file_records
        SET ai_title = ?, ai_tags = ?, ai_tag_groups = ?, ai_generated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        ai_title,
        json.dumps(ai_tags, ensure_ascii=False),
        json.dumps(ai_tag_groups, ensure_ascii=False),
        file_id,
    ))
    db.commit()

    if logger:
        logger.info(
            "AI title/tags generated for file %s: %s (%d groups)",
            file_id, ai_title, len(ai_tag_groups),
        )

    return {
        "file_id": file_id,
        "status": "success",
        "ai_title": ai_title,
        "ai_tags": ai_tags,
        "ai_tag_groups": ai_tag_groups,
    }


async def generate_metadata_for_files(
    db: Any,
    file_ids: List[int],
    force_regenerate: bool = False,
    platform: Optional[str] = None,
    language: Optional[str] = None,
    logger: Any = None,
    group_count: int = 1,
    tags_only_groups: bool = False,
) -> Dict[str, Any]:
    """Generate + persist AI title/tags for a list of file_ids.

    ``db`` must expose ``cursor()`` / ``commit()`` (the same connection the
    files router receives). Returns ``{"success_count", "failed_count",
    "results", "platform"}``. When ``group_count`` > 1 each file stores
    ``ai_tag_groups`` (JSON) with that many differentiated title+tags variants.
    """
    from ai_service.title_topic_generator import load_ai_prompts_config, resolve_platform

    prompt_config = load_ai_prompts_config()
    resolved_platform = resolve_platform(platform)
    group_count = max(int(group_count or 1), 1)

    cursor = db.cursor()
    results: List[Dict[str, Any]] = []
    success_count = 0
    failed_count = 0

    for file_id in file_ids:
        try:
            result = await _generate_one(
                cursor=cursor,
                db=db,
                prompt_config=prompt_config,
                file_id=file_id,
                force_regenerate=force_regenerate,
                platform=resolved_platform,
                language=language,
                logger=logger,
                group_count=group_count,
                tags_only_groups=tags_only_groups,
            )
        except Exception as exc:  # noqa: BLE001 - per-file isolation
            if logger:
                logger.error("Failed to generate AI title/tags for file %s: %s", file_id, exc)
            result = {"file_id": file_id, "status": "failed", "error": str(exc)}

        results.append(result)
        if result.get("status") == "success":
            success_count += 1
        elif result.get("status") == "failed":
            failed_count += 1

    return {
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results,
        "platform": resolved_platform,
    }
