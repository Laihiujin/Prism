"""
发布模块业务逻辑层
集成任务队列、预设管理、文件验证、账号验证
"""
import sys
import json
import uuid
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import asyncio
import warnings

from sqlalchemy import text

# 时区工具
from fastapi_app.core.timezone_utils import now_beijing_naive, to_beijing

# 添加路径以导入现有模块
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from myUtils.preset_manager import PresetManager
from myUtils.cookie_manager import cookie_manager
from myUtils.platform_metadata_adapter import format_metadata_for_platform, PLATFORM_CONFIGS
from fastapi_app.core.logger import logger
from fastapi_app.core.exceptions import NotFoundException, BadRequestException
from fastapi_app.db.runtime import mysql_enabled, sa_connection
from platforms.path_utils import resolve_cookie_file, resolve_video_file


class PublishService:
    """发布服务（已迁移到 Celery）"""

    # 平台代码映射
    PLATFORM_MAP = {
        1: "xiaohongshu",
        2: "channels",
        3: "douyin",
        4: "kuaishou",
        5: "bilibili",
        6: "tiktok",
        7: "youtube",
        8: "baijiahao",
    }

    def __init__(self, task_manager=None):
        """
        初始化发布服务

        Args:
            task_manager: (已弃用) 保留用于向后兼容
        """
        if task_manager is not None:
            logger.warning("[PublishService] task_manager 参数已弃用，任务已迁移到 Celery")
        self.task_manager = task_manager
        self.preset_manager = PresetManager()
        self.executor = ThreadPoolExecutor(max_workers=3)

    def _portable_video_path(self, raw: str) -> str:
        """
        Make the stored `file_path` resilient to repo moves.

        If DB stores an absolute path that no longer exists (e.g. D:\\... from an old location),
        enqueue a portable filename/relative path so `resolve_video_file()` can map it on the worker host.
        """
        if not raw:
            return raw
        try:
            p = Path(str(raw))
            if p.exists():
                return str(p)
            resolved = resolve_video_file(str(raw))
            if resolved and Path(resolved).exists():
                return str(resolved)
            # If absolute but missing, enqueue basename so resolver can find it under prism_backend/videoFile.
            if p.is_absolute():
                return p.name
        except Exception:
            pass
        return str(raw)

    async def validate_file(self, db, file_id: int) -> Dict[str, Any]:
        """验证文件是否存在"""
        if mysql_enabled():
            warnings.warn("SQLite publish/file path is deprecated; using MySQL via DATABASE_URL", DeprecationWarning)
            with sa_connection() as conn:
                row = conn.execute(
                    text("SELECT * FROM file_records WHERE id = :id"),
                    {"id": file_id},
                ).mappings().first()
            if not row:
                raise NotFoundException(f"文件不存在 ID {file_id}")
            return dict(row)

        cursor = db.cursor()
        cursor.execute("SELECT * FROM file_records WHERE id = ?", (file_id,))
        row = cursor.fetchone()

        if not row:
            raise NotFoundException(f"文件不存在: ID {file_id}")

        return dict(row)

    async def validate_accounts(self, account_ids: List[str], platform_code: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        验证账号是否存在且有效
        如果 platform_code 为 None，则不验证平台匹配（用于多平台发布）
        """
        valid_accounts = []

        for account_id in account_ids:
            account = cookie_manager.get_account_by_id(account_id)
            if not account:
                platform_name = self.PLATFORM_MAP.get(platform_code) if platform_code else None
                account = cookie_manager.get_account_by_user_id(account_id, platform=platform_name)
            if not account:
                raise NotFoundException(f"未找到账号: {account_id}")
            normalized_cookie = cookie_manager.ensure_cookie_file(account)
            if normalized_cookie:
                account["cookie_file"] = normalized_cookie

            # 检查 cookie_file 是否存在
            if not account.get('cookie_file'):
                logger.error(f"账号 {account_id} 的 cookie_file 为空")
                raise BadRequestException(
                    f"账号 {account_id} 的 Cookie 文件路径为空，无法发布。"
                    f"请重新导入该账号或联系管理员。"
                )

            cookie_path = resolve_cookie_file(account.get("cookie_file"))
            if not cookie_path or not Path(cookie_path).exists():
                cookie_manager.update_account_status(account.get("platform"), account_id, "file_missing")
                raise BadRequestException(
                    f"账号 {account_id} 的 Cookie 文件不存在: {account.get('cookie_file')}"
                )

            # 如果指定了平台，检查平台是否匹配
            if platform_code is not None and account.get('platform_code') != platform_code:
                raise BadRequestException(
                    f"账号 {account_id} 平台不匹配 (期望: {self.PLATFORM_MAP[platform_code]}, "
                    f"实际: {account.get('platform')})"
                )

            # 检查账号状态
            if account.get('status') != 'valid':
                logger.warning(f"账号 {account_id} 状态为 {account.get('status')}, 可能无法发布")

            logger.info(f"✅ 验证账号: {account_id} - Cookie文件: {account.get('cookie_file')}")
            valid_accounts.append(account)

        return valid_accounts

    async def publish_batch(
        self,
        db,
        file_ids: List[int],
        accounts: List[str],
        platform: Optional[int] = None,
        title: str = "",
        description: Optional[str] = None,
        topics: Optional[List[str]] = None,
        cover_path: Optional[str] = None,
        scheduled_time: Optional[str] = None,
        interval_control_enabled: bool = False,
        interval_mode: Optional[str] = None,
        interval_seconds: Optional[int] = 300,
        random_offset: Optional[int] = 0,
        priority: int = 5,
        items: Optional[List[Dict[str, Any]]] = None,
        # 🆕 NEW: Assignment strategy parameters
        assignment_strategy: str = "all_per_account",
        one_per_account_mode: str = "random",
        per_platform_overrides: Optional[Dict[str, str]] = None,
        # 🆕 NEW: Deduplication parameters
        allow_duplicate_publish: bool = False,
        dedup_window_days: int = 7,
        # 🆕 NEW: Douyin publish options
        declaration: Optional[str] = None,
        location: str = "",
        random_cover: bool = False,
        miniprogram_link: str = "",
        miniprogram_title: str = "",
        # 🆕 NEW: 每平台专属配置（透传到发布任务，供各平台 worker 读取）
        platform_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        logger.info(
            "[PublishService] External publish request via /publish/batch; "
            "will split into publish.single sub-tasks per account/video."
        )
        批量发布
        支持单平台和多平台发布
        - 如果指定了 platform，则只发布到该平台（验证账号必须属于该平台）
        - 如果未指定 platform，则支持多平台发布（自动按账号平台分组）

        Args:
            interval_control_enabled: 是否启用间隔控制
            interval_mode: 间隔模式 ('video_first' 或 'account_first')
            interval_seconds: 基础间隔时间（秒）
            random_offset: 随机偏移范围（±秒），0表示不随机
        """
        batch_id = f"batch_{uuid.uuid4().hex[:12]}"
        results = {
            "batch_id": batch_id,
            "total_tasks": 0,
            "success_count": 0,
            "failed_count": 0,
            "pending_count": 0,
            "tasks": []
        }

        # 定时发布：批量任务会立即执行，但在平台侧设置“定时发布”时间
        timer_config = None
        if scheduled_time:
            timer_config = self._parse_schedule_time(scheduled_time)
            logger.info(f"批量定时发布配置: {timer_config}")

        # 验证账号（如果指定了平台则验证平台匹配，否则不验证）
        try:
            valid_accounts = await self.validate_accounts(accounts, platform)
        except Exception as e:
            logger.error(f"批量发布账号验证失败: {e}")
            raise

        # 如果是多平台发布，按平台分组账号
        if platform is None:
            # 按平台分组
            from collections import defaultdict
            accounts_by_platform = defaultdict(list)
            for account in valid_accounts:
                acc_platform = account.get('platform_code')
                if acc_platform:
                    accounts_by_platform[acc_platform].append(account)

            logger.info(f"多平台发布: 检测到 {len(accounts_by_platform)} 个平台")

            # 为每个平台创建任务
            for plat_code, plat_accounts in accounts_by_platform.items():
                await self._create_batch_tasks(
                    db, batch_id, file_ids, plat_accounts, plat_code,
                    title,
                    description,
                    topics,
                    cover_path,
                    priority,
                    items,
                    results,
                    timer_config,
                    interval_control_enabled=interval_control_enabled,
                    interval_mode=interval_mode,
                    interval_seconds=interval_seconds,
                    random_offset=random_offset,
                    # 🆕 NEW parameters
                    assignment_strategy=assignment_strategy,
                    one_per_account_mode=one_per_account_mode,
                    per_platform_overrides=per_platform_overrides,
                    allow_duplicate_publish=allow_duplicate_publish,
                    dedup_window_days=dedup_window_days,
                    # 🆕 Douyin publish options
                    declaration=declaration,
                    location=location,
                    random_cover=random_cover,
                    miniprogram_link=miniprogram_link,
                    miniprogram_title=miniprogram_title,
                    platform_settings=platform_settings,
                )
        else:
            # 单平台发布
            await self._create_batch_tasks(
                db, batch_id, file_ids, valid_accounts, platform,
                title,
                description,
                topics,
                cover_path,
                priority,
                items,
                results,
                timer_config,
                interval_control_enabled=interval_control_enabled,
                interval_mode=interval_mode,
                interval_seconds=interval_seconds,
                random_offset=random_offset,
                # 🆕 NEW parameters
                assignment_strategy=assignment_strategy,
                one_per_account_mode=one_per_account_mode,
                per_platform_overrides=per_platform_overrides,
                allow_duplicate_publish=allow_duplicate_publish,
                dedup_window_days=dedup_window_days,
                # 🆕 Douyin publish options
                declaration=declaration,
                location=location,
                random_cover=random_cover,
                miniprogram_link=miniprogram_link,
                miniprogram_title=miniprogram_title,
            )

        logger.info(
            f"批量发布任务创建完成: batch_id={batch_id}, "
            f"成功={results['success_count']}, 失败={results['failed_count']}"
        )

        return results

    async def _create_batch_tasks(
        self,
        db,
        batch_id: str,
        file_ids: List[int],
        accounts: List[Dict[str, Any]],
        platform: int,
        title: str,
        description: Optional[str],
        topics: Optional[List[str]],
        cover_path: Optional[str],
        priority: int,
        items: Optional[List[Dict[str, Any]]],
        results: Dict[str, Any],
        timer_config: Optional[Dict[str, Any]] = None,
        *,
        interval_control_enabled: bool = False,
        interval_mode: Optional[str] = None,
        interval_seconds: Optional[int] = 300,
        random_offset: Optional[int] = 0,
        # 🆕 NEW: Assignment strategy parameters
        assignment_strategy: str = "all_per_account",
        one_per_account_mode: str = "random",
        per_platform_overrides: Optional[Dict[str, str]] = None,
        # 🆕 NEW: Deduplication parameters
        allow_duplicate_publish: bool = False,
        dedup_window_days: int = 7,
        # 🆕 NEW: Douyin publish options
        declaration: Optional[str] = None,
        location: str = "",
        random_cover: bool = False,
        miniprogram_link: str = "",
        miniprogram_title: str = "",
        # 🆕 NEW: 每平台专属配置
        platform_settings: Optional[Dict[str, Any]] = None,
    ):
        """创建批量发布任务的内部方法"""
        import random  # 导入 random 模块用于随机偏移
        from fastapi_app.api.v1.publish.assignment_strategies import (
            AssignmentEngine,
            AssignmentConfig
        )

        logger.info(
            f"[PublishService] Splitting batch_id={batch_id} into publish.single tasks: "
            f"files={len(file_ids)}, accounts={len(accounts)}, platform={platform}"
        )

        # 🔧 FIX: 定时发布时，使用定时时间作为间隔控制的基准时间
        if timer_config and timer_config.get("scheduled_time"):
            try:
                base_time = datetime.fromisoformat(timer_config["scheduled_time"])
                logger.info(f"[IntervalControl] 使用定时时间作为基准: {base_time.strftime('%Y-%m-%d %H:%M:%S')}")
            except Exception as e:
                logger.warning(f"[IntervalControl] 解析定时时间失败，使用当前时间: {e}")
                base_time = now_beijing_naive()
        else:
            base_time = now_beijing_naive()
            logger.info(f"[IntervalControl] 使用当前时间作为基准: {base_time.strftime('%Y-%m-%d %H:%M:%S')}")

        interval_s = int(interval_seconds or 0)
        random_offset_s = int(random_offset or 0)
        mode = (interval_mode or "").strip()

        logger.info(
            f"[IntervalControl] 间隔控制配置: "
            f"enabled={interval_control_enabled}, mode={mode}, "
            f"interval={interval_s}s, random_offset=±{random_offset_s}s"
        )

        # 🆕 使用 AssignmentEngine 计算任务分配
        config = AssignmentConfig(
            strategy=assignment_strategy,
            one_per_account_mode=one_per_account_mode,
            per_platform_overrides={
                int(k): v for k, v in (per_platform_overrides or {}).items()
            } if per_platform_overrides else None
        )

        task_assignments = AssignmentEngine.calculate_tasks(
            file_ids=file_ids,
            accounts=accounts,
            config=config
        )

        logger.info(
            f"[AssignmentEngine] Strategy={assignment_strategy}, "
            f"Generated {len(task_assignments)} task assignments "
            f"(videos={len(file_ids)}, accounts={len(accounts)})"
        )

        def _normalize_platform_key(raw_key: Any) -> Optional[str]:
            if raw_key is None:
                return None
            key = str(raw_key).strip()
            return key or None

        def _pick_platform_override(overrides: Optional[Dict[str, Any]], platform_code: int) -> Optional[Any]:
            if not overrides:
                return None
            cfg = PLATFORM_CONFIGS.get(int(platform_code))
            name = cfg.name if cfg else None
            alias_map = {
                1: "xiaohongshu",
                2: "channels",
                3: "douyin",
                4: "kuaishou",
                5: "bilibili",
            }
            candidates = {
                _normalize_platform_key(platform_code),
                _normalize_platform_key(str(platform_code)),
                _normalize_platform_key(name),
                _normalize_platform_key(name.lower() if name else None),
                _normalize_platform_key(alias_map.get(int(platform_code))),
            }
            for key in candidates:
                if not key:
                    continue
                if key in overrides:
                    return overrides.get(key)
            return None

        def _coerce_topics(value: Any) -> List[str]:
            if not value:
                return []
            if isinstance(value, list):
                return [str(t).strip().lstrip("#") for t in value if str(t).strip()]
            if isinstance(value, str):
                parts = [p for p in re.split(r"[\s,，]+", value) if p and p.strip()]
                return [p.lstrip("#").strip() for p in parts if p.lstrip("#").strip()]
            return []

        def _item_value(item: Any, name: str) -> Any:
            """从 item_config（Pydantic 模型或 dict）读取字段；未设置返回 None。"""
            if item is None:
                return None
            if hasattr(item, name):
                return getattr(item, name)
            if isinstance(item, dict):
                return item.get(name)
            return None

        # 为每个分配的任务创建实际发布任务
        for assignment in task_assignments:
            file_id = assignment.file_id
            account = next((a for a in accounts if a['account_id'] == assignment.account_id), None)
            if not account:
                logger.error(f"[AssignmentEngine] Account not found: {assignment.account_id}")
                continue

            # 使用 assignment 中的索引用于间隔计算
            file_idx = assignment.file_index
            account_idx = assignment.account_index

            try:
                # 验证文件
                file_record = await self.validate_file(db, file_id)

                # Material metadata (from素材库), used as defaults when request doesn't override.
                stored_title = file_record.get("ai_title") or file_record.get("title")
                stored_desc = file_record.get("ai_description") or file_record.get("description")
                stored_cover = file_record.get("cover_image") or file_record.get("cover")

                stored_tags: List[str] = []
                raw_tags_field = file_record.get("tags")
                if raw_tags_field:
                    try:
                        if isinstance(raw_tags_field, str):
                            parsed = json.loads(raw_tags_field)
                            if isinstance(parsed, list):
                                stored_tags = [str(t) for t in parsed if str(t).strip()]
                            else:
                                # Accept common separators (comma/space/Chinese comma) and strip leading '#'
                                parts = [p for p in re.split(r"[\s,，]+", raw_tags_field) if p and p.strip()]
                                stored_tags = [p.lstrip("#").strip() for p in parts if p.lstrip("#").strip()]
                        elif isinstance(raw_tags_field, list):
                            stored_tags = [str(t) for t in raw_tags_field if str(t).strip()]
                    except Exception:
                        parts = [p for p in re.split(r"[\s,，]+", str(raw_tags_field)) if p and p.strip()]
                        stored_tags = [p.lstrip("#").strip() for p in parts if p.lstrip("#").strip()]

                parsed_ai_tags: List[str] = []
                if file_record.get('ai_tags'):
                    try:
                        raw_tags = file_record.get('ai_tags')
                        parsed = json.loads(raw_tags) if isinstance(raw_tags, str) else raw_tags
                        if isinstance(parsed, list):
                            parsed_ai_tags = [str(tag) for tag in parsed if str(tag).strip()]
                    except Exception as e:
                        logger.warning(f"Failed to parse ai_tags for file {file_id}: {e}")

                # 查找是否有独立配置
                item_config = next((i for i in (items or []) if (i.file_id if hasattr(i, 'file_id') else i.get('file_id')) == file_id), None)

                # 调试日志
                logger.info(f"📝 [Publish Debug] file_id={file_id}")
                logger.info(f"📝 [Publish Debug] item_config={item_config}")
                logger.info(f"📝 [Publish Debug] global title={title}")
                logger.info(f"📝 [Publish Debug] global description={description}")

                # 确定最终参数（优先使用 item_config，否则使用统一参数）
                # 支持 Pydantic 模型和字典两种格式
                platform_titles = None
                platform_descriptions = None
                platform_topics = None
                if item_config:
                    if hasattr(item_config, 'title'):
                        # Pydantic 模型
                        final_title = item_config.title if item_config.title else (title or stored_title or Path(file_record['file_path']).stem)
                        final_desc = item_config.description if item_config.description is not None else (description or stored_desc or "")
                        final_topics = item_config.topics if item_config.topics is not None else (topics or stored_tags or [])
                        final_cover = item_config.cover_path if item_config.cover_path else (cover_path or stored_cover or "")
                        platform_titles = getattr(item_config, "platform_titles", None)
                        platform_descriptions = getattr(item_config, "platform_descriptions", None)
                        platform_topics = getattr(item_config, "platform_topics", None)
                    else:
                        # 字典格式
                        final_title = item_config.get('title') if item_config.get('title') else (title or stored_title or Path(file_record['file_path']).stem)
                        final_desc = item_config.get('description') if item_config.get('description') is not None else (description or stored_desc or "")
                        final_topics = item_config.get('topics') if item_config.get('topics') is not None else (topics or stored_tags or [])
                        final_cover = item_config.get('cover_path') if item_config.get('cover_path') else (cover_path or stored_cover or "")
                        platform_titles = item_config.get("platform_titles")
                        platform_descriptions = item_config.get("platform_descriptions")
                        platform_topics = item_config.get("platform_topics")
                else:
                    final_title = title or stored_title or Path(file_record['file_path']).stem
                    final_desc = description or stored_desc or ""
                    final_topics = topics or stored_tags or []
                    final_cover = cover_path or stored_cover or ""

                # 按平台覆盖（优先级高于统一参数）
                override_title = _pick_platform_override(platform_titles, platform)
                if override_title:
                    final_title = str(override_title).strip()
                override_desc = _pick_platform_override(platform_descriptions, platform)
                if override_desc is not None and str(override_desc).strip() != "":
                    final_desc = str(override_desc)
                override_topics = _pick_platform_override(platform_topics, platform)
                if override_topics is not None:
                    final_topics = _coerce_topics(override_topics) or final_topics

                if (not final_topics) and parsed_ai_tags:
                    final_topics = parsed_ai_tags

                logger.info(f"✅ [Publish Debug] final_title={final_title}")
                logger.info(f"✅ [Publish Debug] final_desc={final_desc}")
                logger.info(f"✅ [Publish Debug] final_topics={final_topics}")

                # 🆕 使用平台适配器格式化元数据
                formatted_metadata = format_metadata_for_platform(
                    platform_code=platform,
                    metadata={
                        "title": final_title,
                        "description": final_desc,
                        "topics": final_topics
                    }
                )
                logger.info(f"🎯 [Platform Adapter] Formatted metadata for platform {platform}: {formatted_metadata}")

                # 调试：记录文件路径信息
                raw_file_path = file_record.get("file_path") or ""
                portable_path = self._portable_video_path(raw_file_path)
                logger.info(f"[PublishService] file_id={file_id}, raw_path={raw_file_path}, portable_path={portable_path}")
                logger.info(f"[PublishService] Path exists: {Path(portable_path).exists() if portable_path else False}")

                # 🆕 Douyin publish options: per-item override 优先于 top-level 值
                item_declaration = _item_value(item_config, "declaration")
                final_declaration = item_declaration if item_declaration is not None else declaration

                item_location = _item_value(item_config, "location")
                final_location = item_location if item_location is not None else location

                item_random_cover = _item_value(item_config, "random_cover")
                final_random_cover = item_random_cover if item_random_cover is not None else random_cover

                item_miniprogram_link = _item_value(item_config, "miniprogram_link")
                final_miniprogram_link = item_miniprogram_link if item_miniprogram_link is not None else miniprogram_link

                item_miniprogram_title = _item_value(item_config, "miniprogram_title")
                final_miniprogram_title = item_miniprogram_title if item_miniprogram_title is not None else miniprogram_title

                # 创建任务数据，使用格式化后的元数据
                task_data = {
                    "batch_id": batch_id,
                    "file_id": file_id,
                    "video_path": portable_path,
                    "account_id": account['account_id'],
                    "account_name": account.get("original_name") or account.get("name") or account.get("account_id"),
                    "cookie_file": account['cookie_file'],
                    "platform": platform,
                    "title": formatted_metadata.get("title", final_title),
                    "description": formatted_metadata.get("description", final_desc),
                    "tags": formatted_metadata.get("tags", final_topics),
                    "publish_date": (timer_config or {}).get("scheduled_time") or 0,
                    "thumbnail_path": final_cover or "",
                    # 🆕 Douyin publish options
                    "declaration": final_declaration,
                    "location": final_location,
                    "random_cover": bool(final_random_cover),
                    "miniprogram_link": final_miniprogram_link,
                    "miniprogram_title": final_miniprogram_title,
                    "platform_settings": platform_settings or {},
                }

                task_id = f"publish_{batch_id}_{file_id}_{account['account_id']}"

                # 🔒 增强防重复检查：双重检查机制
                # 检查1: pending/running任务（防止重复提交）
                # 检查2: 已成功发布任务（防止重复发布）
                if not allow_duplicate_publish:
                    try:
                        cursor = db.cursor()

                        # 检查1: pending/running任务
                        cursor.execute(
                            """
                            SELECT celery_task_id, status, created_at
                            FROM publish_tasks
                            WHERE platform = ?
                              AND account_id = ?
                              AND material_id = ?
                              AND status IN ('pending', 'running')
                              AND created_at > datetime('now', '-1 day')
                            ORDER BY created_at DESC
                            LIMIT 1
                            """,
                            (str(platform), str(account['account_id']), str(file_id))
                        )
                        pending_task = cursor.fetchone()

                        if pending_task:
                            task_id_existing, status, created_at = pending_task
                            logger.warning(
                                f"[Dedup] Skipping duplicate pending/running task: "
                                f"platform={platform}, account={account['account_id']}, file={file_id}, "
                                f"status={status}, created_at={created_at}"
                            )
                            results["tasks"].append({
                                "task_id": task_id_existing,
                                "file_id": file_id,
                                "platform": platform,
                                "account_id": account['account_id'],
                                "status": "skipped",
                                "reason": "duplicate_pending",
                                "message": f"任务已存在（{status}，提交于 {created_at}）"
                            })
                            continue  # 跳过此任务

                        # 检查2: 已成功发布任务（可配置时间窗口）
                        if dedup_window_days > 0:
                            cursor.execute(
                                f"""
                                SELECT celery_task_id, completed_at, created_at
                                FROM publish_tasks
                                WHERE platform = ?
                                  AND account_id = ?
                                  AND material_id = ?
                                  AND status = 'success'
                                  AND created_at > datetime('now', '-{dedup_window_days} day')
                                ORDER BY completed_at DESC
                                LIMIT 1
                                """,
                                (str(platform), str(account['account_id']), str(file_id))
                            )
                            success_task = cursor.fetchone()

                            if success_task:
                                task_id_existing, completed_at, created_at = success_task
                                published_time = completed_at or created_at
                                logger.warning(
                                    f"[Dedup] Skipping already published content: "
                                    f"platform={platform}, account={account['account_id']}, file={file_id}, "
                                    f"published_at={published_time}"
                                )
                                results["tasks"].append({
                                    "task_id": task_id_existing,
                                    "file_id": file_id,
                                    "platform": platform,
                                    "account_id": account['account_id'],
                                    "status": "skipped",
                                    "reason": "already_published",
                                    "message": f"该账号已在 {published_time} 发布过此视频（{dedup_window_days}天内）"
                                })
                                continue  # 跳过此任务

                    except Exception as e:
                        logger.error(f"[Dedup] Deduplication check failed: {e}")
                        # 检查失败不影响任务提交，继续执行
                else:
                    logger.info(
                        f"[Dedup] allow_duplicate_publish=True, skipping dedup check for "
                        f"file={file_id}, account={account['account_id']}"
                    )

                # Optional interval control: delay task execution by setting `not_before`.
                if interval_control_enabled and interval_s > 0 and mode in ("account_first", "video_first"):
                    # 计算基础偏移量并记录公式
                    if mode == "video_first":
                        base_offset = file_idx * interval_s
                        formula = f"video_first: file_idx({file_idx}) × {interval_s}s"
                    else:
                        # account_first: stagger accounts and keep each account's files sequential.
                        base_offset = (account_idx * interval_s) + (file_idx * interval_s * max(len(accounts), 1))
                        formula = (
                            f"account_first: account_idx({account_idx})×{interval_s}s + "
                            f"file_idx({file_idx})×{interval_s}s×{len(accounts)} accounts"
                        )

                    offset = base_offset

                    # 添加随机偏移（如果配置了）
                    if random_offset_s > 0:
                        import random
                        random_delta = random.randint(-random_offset_s, random_offset_s)
                        offset += random_delta
                        logger.info(
                            f"✅ [IntervalControl] Task {task_id}: "
                            f"{formula} = {base_offset}s + random({random_delta}s) = {offset}s"
                        )
                    else:
                        logger.info(
                            f"✅ [IntervalControl] Task {task_id}: {formula} = {offset}s"
                        )

                    # 确保偏移量不为负数
                    offset = max(0, offset)

                    scheduled_time = base_time + timedelta(seconds=offset)
                    task_data["not_before"] = scheduled_time.isoformat()

                    # 🆕 记录绝对调度时间，便于验证
                    logger.info(
                        f"📅 [IntervalControl] Scheduled: {task_id} → "
                        f"{scheduled_time.strftime('%H:%M:%S')} "
                        f"(file={file_idx+1}/{len(file_ids)}, account={account_idx+1}/{len(accounts)})"
                    )

                # 使用 Celery 提交任务
                from fastapi_app.tasks.publish_tasks import publish_single_task
                from fastapi_app.tasks.task_state_manager import task_state_manager

                result = publish_single_task.apply_async(
                    kwargs={'task_data': task_data},
                    priority=priority,
                    task_id=task_id  # 使用自定义 task_id
                )

                # 保存任务状态到 Redis（实时状态）
                task_state_manager.create_task(
                    task_id=result.id,
                    task_type="publish",
                    data=task_data,
                    priority=priority
                )

                # ✅ 同时写入 SQLite 数据库（持久化历史记录）
                # 避免重启后端时任务状态丢失，导致重复提交
                try:
                    cursor = db.cursor()
                    cursor.execute(
                        """
                        INSERT INTO publish_tasks (
                            celery_task_id, platform, account_id, material_id, title, tags,
                            status, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            result.id,
                            str(platform),
                            str(account['account_id']),
                            str(file_id),
                            final_title,
                            json.dumps(final_topics, ensure_ascii=False) if final_topics else None,
                            "pending",  # 初始状态
                            now_beijing_naive().isoformat(),
                            now_beijing_naive().isoformat()
                        )
                    )
                    db.commit()
                    logger.debug(f"[PublishService] Task {result.id} saved to SQLite publish_tasks")
                except Exception as e:
                    logger.error(f"[PublishService] Failed to save task to SQLite: {e}")
                    # 不影响任务提交，继续执行

                results["total_tasks"] += 1
                results["success_count"] += 1
                results["pending_count"] += 1
                results["tasks"].append({
                    "task_id": result.id,
                    "file_id": file_id,
                    "platform": platform,
                    "account_id": account['account_id'],
                    "status": "pending"
                })

            except Exception as e:
                logger.error(f"批量发布文件 {file_id} 失败: {e}")
                results["failed_count"] += 1
                results["total_tasks"] += 1
                results["tasks"].append({
                    "task_id": f"failed_{file_id}",
                    "file_id": file_id,
                    "platform": platform,
                    "status": "failed",
                    "error_message": str(e)
                })


    def _parse_json_list(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            try:
                parsed = json.loads(raw)
            except Exception:
                parts = [p.strip() for p in re.split(r"[\s,]+", raw) if p.strip()]
                return parts
            if isinstance(parsed, list):
                return parsed
            return [parsed]
        return [value]

    def _normalize_platforms(self, value: Any) -> List[str]:
        items = self._parse_json_list(value)
        result: List[str] = []
        for item in items:
            if item is None:
                continue
            if isinstance(item, int) or (isinstance(item, str) and item.isdigit()):
                code = int(item)
                result.append(self.PLATFORM_MAP.get(code, f"platform_{code}"))
            else:
                result.append(str(item))
        return result

    def _normalize_preset(self, preset: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(preset or {})
        data["name"] = data.get("name") or data.get("label") or ""

        platforms = self._normalize_platforms(data.get("platforms") or data.get("platform"))
        data["platforms"] = platforms
        data["platform"] = platforms

        accounts = self._parse_json_list(data.get("accounts"))
        data["accounts"] = [str(a) for a in accounts if str(a).strip()]

        material_ids = self._parse_json_list(data.get("material_ids") or data.get("materialIds"))
        data["material_ids"] = [str(m) for m in material_ids if str(m).strip()]

        tags = self._parse_json_list(data.get("tags"))
        data["tags"] = [str(t) for t in tags if str(t).strip()]

        if data.get("default_title") is None:
            data["default_title"] = data.get("title")
        if data.get("default_description") is None:
            data["default_description"] = data.get("description")
        if data.get("default_title_template") is None:
            data["default_title_template"] = data.get("default_title")

        default_tags = data.get("default_tags")
        if default_tags is None:
            data["default_tags"] = ",".join(data["tags"]) if data["tags"] else ""
        elif isinstance(default_tags, list):
            data["default_tags"] = ",".join([str(t) for t in default_tags if str(t).strip()])

        if data.get("default_topics") is None:
            data["default_topics"] = data.get("default_tags")

        return data

    async def list_presets(self) -> List[Dict[str, Any]]:
        """Get all publish presets."""
        loop = asyncio.get_event_loop()
        presets = await loop.run_in_executor(
            self.executor,
            self.preset_manager.get_all_presets
        )
        return [self._normalize_preset(p) for p in (presets or [])]

    async def create_preset(self, preset_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建发布预设"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.executor,
            self.preset_manager.create_preset,
            preset_data
        )

        if not result.get('success'):
            raise BadRequestException(f"创建预设失败: {result.get('error')}")

        logger.info(f"预设创建成功: {preset_data.get('name')} (ID: {result.get('id')})")
        return result

    async def update_preset(self, preset_id: int, preset_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新发布预设"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.executor,
            self.preset_manager.update_preset,
            preset_id,
            preset_data
        )

        if not result.get('success'):
            raise BadRequestException(f"更新预设失败: {result.get('error')}")

        logger.info(f"预设更新成功: ID {preset_id}")
        return result

    async def delete_preset(self, preset_id: int) -> Dict[str, Any]:
        """删除发布预设"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.executor,
            self.preset_manager.delete_preset,
            preset_id
        )

        if not result.get('success'):
            raise NotFoundException(f"预设不存在: ID {preset_id}")

        logger.info(f"预设删除成功: ID {preset_id}")
        return result

    async def use_preset(
        self,
        db,
        preset_id: int,
        file_ids: List[int],
        override_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Use preset to publish."""
        loop = asyncio.get_event_loop()
        presets = await loop.run_in_executor(
            self.executor,
            self.preset_manager.get_all_presets
        )

        preset = next((p for p in presets if p['id'] == preset_id), None)
        if not preset:
            raise NotFoundException(f"Preset not found: ID {preset_id}")

        await loop.run_in_executor(
            self.executor,
            self.preset_manager.increment_usage,
            preset_id
        )

        raw_platform = preset.get('platform')
        if raw_platform is None:
            raw_platform = preset.get('platforms')
        platform_list = self._parse_json_list(raw_platform)
        platform_candidate = platform_list[0] if platform_list else None

        platform_code = None
        if platform_candidate is not None:
            if isinstance(platform_candidate, int):
                platform_code = platform_candidate
            else:
                s = str(platform_candidate).strip()
                if s.isdigit():
                    platform_code = int(s)
                else:
                    name_map = {v: k for k, v in self.PLATFORM_MAP.items()}
                    platform_code = name_map.get(s) or name_map.get(s.lower())

        accounts = self._parse_json_list(preset.get('accounts', []))
        accounts = [str(a) for a in accounts if str(a).strip()]

        topics = self._parse_json_list(preset.get('tags', []))
        topics = [str(t) for t in topics if str(t).strip()]

        publish_params = {
            "file_ids": file_ids,
            "accounts": accounts,
            "platform": platform_code,
            "title": preset.get('default_title') or preset.get('title', ''),
            "description": preset.get('description', ''),
            "topics": topics
        }

        if override_data:
            publish_params.update(override_data)

        result = await self.publish_batch(db, **publish_params)

        logger.info(f"?????????: preset_id={preset_id}, batch_id={result.get('batch_id')}")
        return result

    async def get_publish_history(
        self,
        db,
        platform: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取发布历史"""
        if mysql_enabled():
            warnings.warn("SQLite publish_tasks path is deprecated; using MySQL via DATABASE_URL", DeprecationWarning)
            where = ["1=1"]
            params: dict = {"limit": int(limit)}

            if platform:
                where.append("platform = :platform")
                params["platform"] = str(platform)
            if status:
                where.append("status = :status")
                params["status"] = status

            where_sql = " AND ".join(where)
            with sa_connection() as conn:
                rows = conn.execute(
                    text(f"SELECT * FROM publish_tasks WHERE {where_sql} ORDER BY created_at DESC LIMIT :limit"),
                    params,
                ).mappings().all()
            return [dict(r) for r in rows]

        cursor = db.cursor()

        query = "SELECT * FROM publish_tasks WHERE 1=1"
        params = []

        if platform:
            query += " AND platform = ?"
            params.append(str(platform))

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        history = []
        for row in rows:
            history.append(dict(row))

        return history

    def _parse_schedule_time(self, scheduled_time: str) -> Dict[str, Any]:
        """
        解析定时发布时间
        格式: "YYYY-MM-DD HH:MM" 或 "HH:MM"
        """
        try:
            # 尝试解析完整日期时间
            if "T" in scheduled_time:
                iso_value = scheduled_time.strip()
                if iso_value.endswith("Z"):
                    iso_value = f"{iso_value[:-1]}+00:00"
                parsed = datetime.fromisoformat(iso_value)
                if parsed.tzinfo is not None:
                    target_time = to_beijing(parsed).replace(tzinfo=None)
                else:
                    target_time = parsed
            elif " " in scheduled_time:
                time_fmt = "%Y-%m-%d %H:%M:%S" if scheduled_time.count(":") >= 2 else "%Y-%m-%d %H:%M"
                target_time = datetime.strptime(scheduled_time, time_fmt)
            else:
                # 只有时间，使用今天或明天的日期
                time_obj = datetime.strptime(scheduled_time, "%H:%M")
                now = now_beijing_naive()
                target_time = now.replace(
                    hour=time_obj.hour,
                    minute=time_obj.minute,
                    second=0,
                    microsecond=0
                )

                # 如果时间已过，设置为明天
                if target_time < now:
                    target_time += timedelta(days=1)

            # 计算延迟秒数
            delay_seconds = (target_time - now_beijing_naive()).total_seconds()

            if delay_seconds < 0:
                raise ValueError("定时时间不能早于当前时间")

            return {
                "scheduled_time": target_time.isoformat(),
                "delay_seconds": int(delay_seconds),
                "enable_timer": True
            }

        except ValueError as e:
            raise BadRequestException(f"定时时间格式错误: {str(e)}")


# 全局服务实例工厂
def get_publish_service(task_manager=None) -> PublishService:
    """
    获取发布服务实例

    Args:
        task_manager: (已弃用) 保留用于向后兼容
    """
    return PublishService(task_manager)
