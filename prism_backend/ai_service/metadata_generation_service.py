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


async def _generate_one(
    cursor: Any,
    db: Any,
    prompt_config: Dict[str, Any],
    file_id: int,
    force_regenerate: bool,
    platform: Optional[str],
    language: Optional[str],
    logger: Any,
) -> Dict[str, Any]:
    """Generate + persist title/tags for a single file. Returns a result dict."""
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
    )

    # 走与 /api/v1/ai/chat 相同的 chat 模型配置（订阅-deepseek-v4-flash-vision-exp）
    from ai_service.llm import call_chat_model

    content = await call_chat_model(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=500,
    )

    json_match = re.search(r"\{[^}]+\}", content, re.DOTALL)
    metadata = json.loads(json_match.group()) if json_match else json.loads(content)

    ai_title = str(metadata.get("title", "") or "").strip()
    raw_tags = metadata.get("tags", [])
    if isinstance(raw_tags, str):
        raw_tags = [t for t in re.split(r"[\s,，]+", raw_tags) if t and t.strip()]
    ai_tags: List[str] = []
    if isinstance(raw_tags, list):
        for t in raw_tags:
            s = str(t).strip()
            if not s:
                continue
            s = s.lstrip("#").strip()
            if s and s not in ai_tags:
                ai_tags.append(s)

    # 按平台限制做后处理：标题截断到平台上限、话题数上限与去重（只处理标题+标签）
    from ai_service.title_topic_generator import apply_platform_limits

    ai_title, ai_tags = apply_platform_limits(
        platform=platform,
        title=ai_title,
        tags=ai_tags,
    )

    cursor.execute("""
        UPDATE file_records
        SET ai_title = ?, ai_tags = ?, ai_generated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (ai_title, json.dumps(ai_tags, ensure_ascii=False), file_id))
    db.commit()

    if logger:
        logger.info("AI title/tags generated for file %s: %s", file_id, ai_title)

    return {
        "file_id": file_id,
        "status": "success",
        "ai_title": ai_title,
        "ai_tags": ai_tags,
    }


async def generate_metadata_for_files(
    db: Any,
    file_ids: List[int],
    force_regenerate: bool = False,
    platform: Optional[str] = None,
    language: Optional[str] = None,
    logger: Any = None,
) -> Dict[str, Any]:
    """Generate + persist AI title/tags for a list of file_ids.

    ``db`` must expose ``cursor()`` / ``commit()`` (the same connection the
    files router receives). Returns ``{"success_count", "failed_count",
    "results", "platform"}``.
    """
    from ai_service.title_topic_generator import load_ai_prompts_config, resolve_platform

    prompt_config = load_ai_prompts_config()
    resolved_platform = resolve_platform(platform)

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
