"""
批量发布服务
功能：
1. 支持多账号、多平台批量发布
2. 智能任务分配
3. 失败自动重试
4. 进度实时反馈
5. 验证码自动处理（后移队列）
"""
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
import json

from myUtils.exceptions import CaptchaRequiredException, AccountBlockedException
from myUtils.cookie_manager import cookie_manager
from loguru import logger
from platforms.registry import get_uploader_by_platform_code
from platforms.path_utils import resolve_cookie_file, resolve_video_file
from fastapi_app.core.timezone_utils import now_beijing_iso

# 平台 code → platform_settings 里的 key（与 platforms/registry.py 的 _UPLOADER_SPECS 对应）
PLATFORM_SETTINGS_KEY_BY_CODE = {
    1: "xiaohongshu",
    2: "channels",
    3: "douyin",
    4: "kuaishou",
    5: "bilibili",
    6: "tiktok",
    7: "youtube",
    8: "baijiahao",
    9: "twitter",
}


def _platform_settings_for(data: Dict, platform: int) -> Dict:
    """从 task_data 里取对应平台的 platform_settings（返回 {} 兜底）。"""
    try:
        ps = (data.get("platform_settings") or {}) or {}
        if not isinstance(ps, dict):
            return {}
        return ps.get(PLATFORM_SETTINGS_KEY_BY_CODE.get(platform, ""), {}) or {}
    except Exception:
        return {}

class BatchPublishService:
    """批量发布服务（已迁移到 Celery）"""

    def __init__(self, task_manager=None):
        """
        初始化批量发布服务

        Args:
            task_manager: (已弃用) 保留用于向后兼容，实际不再使用
        """
        # task_manager 参数保留用于向后兼容，但不再使用
        if task_manager is not None:
            logger.warning("[BatchPublish] task_manager 参数已弃用，任务已迁移到 Celery")
        self.task_manager = task_manager

    async def handle_single_publish(self, data: Dict) -> Dict:
        """处理单个发布任务"""
        platform = data.get('platform')
        account_id = data.get('account_id')
        cookie_file = data.get('cookie_file')

        # 回退逻辑：如果 account_id 或 cookie_file 为空，尝试从数组获取
        if not account_id and data.get('accounts'):
            account_id = data['accounts'][0]
            logger.warning(f"[Publish] account_id为空，使用accounts[0]: {account_id}")

        if not cookie_file and data.get('account_files'):
            cookie_file = data['account_files'][0]
            logger.warning(f"[Publish] cookie_file为空，使用account_files[0]: {cookie_file}")

        # 兼容两种字段名：video_path 和 file_path
        video_path = data.get('video_path') or data.get('file_path')
        title = data.get('title', '')
        description = data.get('description', '')  # 提取 description
        tags = data.get('tags') or data.get('topics') or []
        publish_date = data.get('publish_date', 0)
        thumbnail_path = data.get('thumbnail_path', '')

        logger.info(f"[Publish] 开始发布: {account_id} @ platform_{platform}")
        logger.info(f"   标题: {title}")
        logger.info(f"   描述: {description}")
        logger.info(f"   标签: {tags}")
        logger.info(f"   视频: {video_path}")

        if not cookie_file:
            error_msg = f"Cookie文件路径为空: file_id={data.get('file_id')}, account_id={account_id}"
            logger.error(f"[Publish] {error_msg}")
            logger.error(f"[Publish] 任务数据: {json.dumps(data, ensure_ascii=False)}")
            raise ValueError(error_msg)

        if not account_id:
            error_msg = f"账号ID为空: file_id={data.get('file_id')}, cookie_file={cookie_file}"
            logger.error(f"[Publish] {error_msg}")
            logger.error(f"[Publish] 任务数据: {json.dumps(data, ensure_ascii=False)}")
            raise ValueError(error_msg)

        try:
            if not isinstance(platform, int):
                platform = int(platform)

            uploader = get_uploader_by_platform_code(platform)

            # 抖音：避免把 hashtags 混进标题
            upload_title = str(title or "").splitlines()[0].strip()
            if platform == 3 and "#" in upload_title:
                upload_title = upload_title.split("#", 1)[0].strip()

            # 兼容旧数据：cookie_file/video_path 可能只有文件名（相对路径）
            raw_cookie_file = cookie_file
            cookie_file = resolve_cookie_file(cookie_file)

            # 推特(Twitter/X)没有网页 cookie：account_file 是 xurl app 名，
            # 不能被 resolve_cookie_file 拼成 cookiesFile 目录下的文件路径。
            if platform == 9:
                cookie_file = raw_cookie_file

            # P0：解包 platform_settings 里对应平台的配置，并让顶层扁平字段优先被覆盖
            ps = _platform_settings_for(data, platform) or {}

            # 图文/图集（笔记）发布：platform_settings.<platform>.contentKind / contentType = "note"
            # （兼容 "image"/"image_note" 写法）。仅抖音(3)/小红书(1)/快手(4) 支持；其余平台报错。
            # 多张图片 = 一条图文内容（不需要 video_path / file_id）。
            content_kind = str(
                ps.get("contentKind") or ps.get("contentType") or data.get("content_kind") or ""
            ).strip().lower()
            if content_kind in {"note", "image", "image_note"}:
                if platform not in (1, 3, 4):
                    raise ValueError(f"平台 {platform} 暂不支持图文发布（支持：抖音/小红书/快手）")
                images_raw = ps.get("images") or data.get("images") or []
                if isinstance(images_raw, str):
                    images_raw = [images_raw]
                images_raw = [i for i in (images_raw or []) if str(i).strip()]
                if not images_raw:
                    raise ValueError("图文发布需要 images 图片路径列表（platform_settings.<平台>.images）")
                note_result = await self._publish_note(
                    platform=platform,
                    account_id=account_id,
                    cookie_file=cookie_file,
                    title=upload_title,
                    description=description or "",
                    tags=tags or [],
                    publish_date=publish_date,
                    images=images_raw,
                    ps=ps,
                    data=data,
                )
                cookie_manager.update_account(account_id, status='valid')
                return {
                    "success": True,
                    "account_id": account_id,
                    "platform": platform,
                    "video_url": None,
                    "published_at": now_beijing_iso(),
                    "kind": "note",
                    **note_result,
                }

            # 视频发布：必须有 video_path
            if not video_path:
                error_msg = f"视频路径为空: file_id={data.get('file_id')}, account_id={account_id}"
                logger.error(f"[Publish] {error_msg}")
                raise ValueError(error_msg)

            video_path = resolve_video_file(video_path)

            # Fail fast with a clear error if file path is still invalid after resolution.
            try:
                if not Path(str(video_path)).exists():
                    raise FileNotFoundError(f"视频文件不存在: {video_path}")
            except Exception as e:
                raise FileNotFoundError(f"视频文件不存在: {video_path}") from e

            poi_name = ""
            if isinstance(ps.get("poi"), dict):
                poi_name = ps.get("poi", {}).get("name", "")
            elif isinstance(ps.get("location"), dict):
                poi_name = ps.get("location", {}).get("name", "")
            mini_program = ps.get("miniProgram") or ps.get("mini_program") or None

            # B站分P：platform_settings.bilibili.video_parts = [{path,title}...]（可选）
            # 若存在，P1 = 主视频，P2..Pn = video_parts 顺序；part_titles 可缺省。
            bili_parts_raw = []
            bili_part_titles = []
            if platform == 5 and isinstance(ps.get("video_parts"), list):
                for entry in ps.get("video_parts") or []:
                    if isinstance(entry, dict) and entry.get("path"):
                        bili_parts_raw.append(str(entry["path"]))
                        bili_part_titles.append(str(entry.get("title") or ""))
                    elif isinstance(entry, str) and entry:
                        bili_parts_raw.append(entry)
                        bili_part_titles.append("")

            # B站发布配置：面板 tid/copyright/source/dynamic 经 platform_settings 透传
            bili_tid = ps.get("tid") or data.get("category_id")
            bili_category_id = int(bili_tid) if str(bili_tid or "").isdigit() else 160

            result = await uploader.upload(
                account_file=cookie_file,
                title=upload_title,
                file_path=video_path,
                tags=tags or [],
                publish_date=publish_date if publish_date != 0 else None,
                thumbnail_path=thumbnail_path or None,
                product_link=data.get("product_link", "") or data.get("productLink", ""),
                product_title=data.get("product_title", "") or data.get("productTitle", ""),
                category=data.get("category"),
                category_id=bili_category_id if platform == 5 else data.get("category_id", 160),
                description=description or "",
                playlist=data.get("playlist"),
                visibility=data.get("visibility", "public"),
                location=data.get("location", "") or poi_name,
                declaration=data.get("declaration", None) or ps.get("declaration", None),
                random_cover=bool(data.get("random_cover", False) or ps.get("useAIRandomCover", False)),
                miniprogram_link=data.get("miniprogram_link", ""),
                miniprogram_title=data.get("miniprogram_title", ""),
                # 新增字段（来自 platform_settings.douyin，仅上传器显式接收）
                who_can_see=ps.get("whoCanSee", ""),
                save_permission=ps.get("savePermission", ""),
                hotspot=ps.get("hotspot", ""),
                collection=ps.get("collection", ""),
                cover_orientation=ps.get("coverOrientation", "landscape"),
                cover_file=ps.get("coverFile", ""),
                miniprogram_object=mini_program,
                # 🆕 B站分P与稿件级配置（仅 platform 5 上传器消费）
                video_parts=bili_parts_raw or None,
                part_titles=bili_part_titles or None,
                platform_settings=ps,
            )

            # 检查结果中是否包含验证码标识
            # 注意：post_video_* 函数可能没有返回值，如果执行成功（没抛出异常），则认为成功
            if result is None:
                # 没有返回值，但没抛出异常，认为成功
                logger.info(f"[Publish] 发布成功: {account_id} @ platform_{platform}")
                cookie_manager.update_account(account_id, status='valid')
                return {
                    "success": True,
                    "account_id": account_id,
                    "platform": platform,
                    "video_url": None,
                    "published_at": now_beijing_iso()
                }

            if result and result.get('captcha_required'):
                logger.warning(f"[Publish] 检测到验证码: {account_id} @ platform_{platform}")
                # 标记账号状态为需要验证
                cookie_manager.update_account(account_id, status='needs_verification')
                raise CaptchaRequiredException(
                    message=result.get('error', '需要人工处理验证码'),
                    account_id=account_id,
                    platform=platform
                )

            # 检查账号是否被封禁
            if result and result.get('account_blocked'):
                logger.error(f"[Publish] 账号被封禁: {account_id} @ platform_{platform}")
                cookie_manager.update_account(account_id, status='blocked')
                raise AccountBlockedException(
                    account_id=account_id,
                    platform=platform
                )

            if result and result.get('success'):
                logger.info(f"[Publish] 发布成功: {account_id} @ platform_{platform}")
                # 更新账号状态为正常
                cookie_manager.update_account(account_id, status='valid')
                return {
                    "success": True,
                    "account_id": account_id,
                    "platform": platform,
                    "video_url": result.get('video_url'),
                    "published_at": now_beijing_iso()
                }
            else:
                # 上传器通常返回 {success: False, message: <真实原因>}，但这里原实现只读 'error'，
                # 拿不到时会退化成「未知错误」（2026-09-03 抖音发布失败即因此被吞真实原因）。
                error = (
                    result.get('error')
                    or result.get('message')
                    or '未知错误'
                ) if result else '发布函数返回空'
                raise Exception(error)

        except CaptchaRequiredException:
            # 验证码异常，需要特殊处理（任务队列会自动后移）
            raise
        except AccountBlockedException:
            # 账号封禁异常，直接失败不重试
            raise
        except Exception as e:
            logger.error(f"[Publish] 发布失败: {account_id} @ platform_{platform}")
            logger.error(f"   错误: {str(e)}")
            raise

    async def _publish_note(
        self,
        platform: int,
        account_id: str,
        cookie_file: str,
        title: str,
        description: str,
        tags: List[str],
        publish_date: Any,
        images: List[str],
        ps: Dict,
        data: Dict,
    ) -> Dict:
        """图文/图集（笔记）发布：抖音(3)/小红书(1)/快手(4) 复用 refactored note uploader。

        images 支持两种形态：
        - 本地绝对路径列表
        - 素材库文件名（相对 videoFile 目录，如 abc123.jpg）→ resolve_image_file 解析
        """
        from platforms.path_utils import resolve_image_file

        resolved_images = []
        for img in images:
            p = resolve_image_file(str(img))
            if p and Path(p).exists():
                resolved_images.append(p)
            else:
                raise FileNotFoundError(f"图片文件不存在: {img} -> {p}")

        publish_value: Any = 0
        if publish_date:
            if isinstance(publish_date, datetime):
                publish_value = publish_date
            elif isinstance(publish_date, (int, float)):
                publish_value = datetime.fromtimestamp(publish_date)
            elif isinstance(publish_date, str):
                s = publish_date.strip().replace("T", " ").replace("Z", "")
                try:
                    publish_value = datetime.fromisoformat(s)
                except Exception:
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                        try:
                            publish_value = datetime.strptime(s, fmt)
                            break
                        except Exception:
                            continue

        logger.info(
            f"[Publish] 图文发布: account={account_id} @ platform_{platform}, "
            f"images={len(resolved_images)}张, title={title!r}"
        )

        # POI / location 兼容两种面板写法：{name,address} 对象 或 纯字符串
        poi_obj = ps.get("poi")
        location_str = str(ps.get("location") or "")
        if not location_str and isinstance(poi_obj, dict):
            location_str = str(poi_obj.get("name") or "")
        elif not location_str and isinstance(ps.get("location"), dict):
            location_str = str(ps.get("location", {}).get("name") or "")

        if platform == 3:
            from uploader.douyin_uploader.main_refactored import (
                DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
                DOUYIN_PUBLISH_STRATEGY_SCHEDULED,
                DouYinNote,
            )

            strategy = DOUYIN_PUBLISH_STRATEGY_SCHEDULED if publish_value else DOUYIN_PUBLISH_STRATEGY_IMMEDIATE
            mini_program = ps.get("miniProgram") or ps.get("mini_program") or None
            app = DouYinNote(
                resolved_images,
                description or "",
                tags or [],
                publish_value,
                resolve_cookie_file(cookie_file),
                title=title or "",
                publish_strategy=strategy,
                bgm=str(ps.get("bgm") or ""),
                declaration=ps.get("declaration") or None,
                location=location_str,
                collection=(ps.get("collection") or None),
                who_can_see=str(ps.get("whoCanSee") or None) or None,
                save_permission=str(ps.get("savePermission") or None) or None,
                hotspot=str(ps.get("hotspot") or None) or None,
                cover_file=str(ps.get("coverFile") or ""),
                cover_orientation=str(ps.get("coverOrientation") or "landscape"),
                mini_program=mini_program,
            )
        elif platform == 1:
            from uploader.xiaohongshu_uploader.main_refactored import (
                XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE,
                XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED,
                XiaoHongShuNote,
            )

            strategy = XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED if publish_value else XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE
            app = XiaoHongShuNote(
                resolved_images,
                description or "",
                tags or [],
                publish_value,
                resolve_cookie_file(cookie_file),
                title=title or "",
                desc=description or "",
                publish_strategy=strategy,
            )
        elif platform == 4:
            from uploader.ks_uploader.main_refactored import (
                KUAISHOU_PUBLISH_STRATEGY_IMMEDIATE,
                KUAISHOU_PUBLISH_STRATEGY_SCHEDULED,
                KSNote,
            )

            strategy = KUAISHOU_PUBLISH_STRATEGY_SCHEDULED if publish_value else KUAISHOU_PUBLISH_STRATEGY_IMMEDIATE
            app = KSNote(
                resolved_images,
                description or "",
                tags or [],
                publish_value,
                resolve_cookie_file(cookie_file),
                title=title or "",
                publish_strategy=strategy,
            )
        else:
            raise ValueError(f"平台 {platform} 暂不支持图文发布（支持：抖音/小红书/快手）")

        result = app.main()
        if hasattr(result, "__await__"):
            await result

        logger.info(f"[Publish] 图文发布成功: {account_id} @ platform_{platform}")
        return {"message": f"图文发布成功（{len(resolved_images)}张图片）"}

    async def handle_batch_publish(self, data: Dict) -> Dict:
        """
        处理批量发布任务（主任务，会拆分为多个子任务）
        注意：此方法现已由 Celery 任务调用，不再通过内存队列
        """
        batch_id = data.get('batch_id', str(uuid.uuid4()))
        items = data.get('items', [])

        logger.info(f"📦 [BatchPublish] 开始批量发布: {batch_id}, 任务数: {len(items)}")

        # 使用 Celery 提交子任务
        from fastapi_app.tasks.publish_tasks import publish_single_task
        from fastapi_app.tasks.task_state_manager import task_state_manager

        sub_task_ids = []
        for item in items:
            # 使用 Celery 提交任务
            result = publish_single_task.apply_async(
                kwargs={'task_data': item},
                priority=item.get('priority', 5)
            )
            sub_task_ids.append(result.id)

            # 保存子任务到状态管理器
            task_state_manager.create_task(
                task_id=result.id,
                task_type="publish",
                data=item,
                priority=item.get('priority', 5),
                parent_task_id=batch_id
            )

        logger.info(f"✅ [BatchPublish] 批量任务已提交: {batch_id}, 子任务数: {len(sub_task_ids)}")

        return {
            "success": True,
            "batch_id": batch_id,
            "task_ids": sub_task_ids,
            "total_tasks": len(sub_task_ids)
        }

    def create_batch_publish_task(
        self,
        material_id: int,
        accounts: List[Dict],
        title: str,
        tags: List[str],
        publish_date: int = 0,
        description: str = '',
        thumbnail_path: Optional[str] = None,
        priority: int = 5
    ) -> str:
        """创建批量发布任务（使用 Celery）"""

        # 生成批次ID
        batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # 准备发布项
        items = []
        for account in accounts:
            item = {
                'account_id': account['account_id'],
                'platform': account['platform'],
                'cookie_file': account['cookie_file'],
                'video_path': account.get('video_path'),  # 从请求中获取
                'title': title,
                'tags': tags,
                'publish_date': publish_date,
                'description': description,
                'thumbnail_path': thumbnail_path,
                # 平台特定参数
                'productLink': account.get('productLink', ''),
                'productTitle': account.get('productTitle', ''),
                'category': account.get('category'),
                'category_id': account.get('category_id')
            }
            items.append(item)

        # 使用 Celery 提交批量任务
        from fastapi_app.tasks.publish_tasks import publish_batch_task
        from fastapi_app.tasks.task_state_manager import task_state_manager

        batch_data = {
            'batch_id': batch_id,
            'material_id': material_id,
            'items': items,
            'priority': priority
        }

        # 提交到 Celery
        result = publish_batch_task.apply_async(
            kwargs={'batch_data': batch_data},
            priority=priority
        )

        # 保存批次任务状态
        task_state_manager.create_task(
            task_id=result.id,
            task_type="batch_publish",
            data=batch_data,
            priority=priority
        )

        logger.info(f"✅ [BatchPublish] 批量发布任务已创建: {batch_id}, 包含 {len(items)} 个发布任务")

        return batch_id

    def get_batch_status(self, batch_id: str) -> Dict:
        """获取批量任务状态（从 Redis 查询）"""
        from fastapi_app.tasks.task_state_manager import task_state_manager

        # 查询批次主任务
        batch_status = task_state_manager.get_task_state(batch_id)
        if not batch_status:
            return {"error": "批次不存在"}

        # 查询所有子任务
        sub_tasks = []
        task_ids = batch_status.get('result', {}).get('task_ids', [])

        for task_id in task_ids:
            task_status = task_state_manager.get_task_state(task_id)
            if task_status:
                sub_tasks.append(task_status)

        # 统计状态
        stats = {
            "total": len(sub_tasks),
            "success": sum(1 for t in sub_tasks if t['status'] == 'success'),
            "failed": sum(1 for t in sub_tasks if t['status'] == 'failed'),
            "running": sum(1 for t in sub_tasks if t['status'] == 'running'),
            "pending": sum(1 for t in sub_tasks if t['status'] in ['pending', 'retry'])
        }

        return {
            "batch_id": batch_id,
            "batch_status": batch_status['status'],
            "stats": stats,
            "tasks": sub_tasks,
            "created_at": batch_status.get('created_at'),
            "started_at": batch_status.get('started_at'),
            "completed_at": batch_status.get('completed_at')
        }

# 全局实例
_batch_publish_service_instance = None

def get_batch_publish_service(task_manager=None) -> BatchPublishService:
    """
    获取批量发布服务实例

    Args:
        task_manager: (已弃用) 保留用于向后兼容
    """
    global _batch_publish_service_instance
    if _batch_publish_service_instance is None:
        _batch_publish_service_instance = BatchPublishService(task_manager)
    return _batch_publish_service_instance
