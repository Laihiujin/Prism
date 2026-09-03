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
from typing import List, Dict, Optional
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

        # 检查必需字段是否为 None
        if not video_path:
            error_msg = f"视频路径为空: file_id={data.get('file_id')}, account_id={account_id}"
            logger.error(f"[Publish] {error_msg}")
            raise ValueError(error_msg)

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
            cookie_file = resolve_cookie_file(cookie_file)
            video_path = resolve_video_file(video_path)

            # Fail fast with a clear error if file path is still invalid after resolution.
            try:
                if not Path(str(video_path)).exists():
                    raise FileNotFoundError(f"视频文件不存在: {video_path}")
            except Exception as e:
                raise FileNotFoundError(f"视频文件不存在: {video_path}") from e

            # P0：解包 platform_settings 里对应平台的配置，并让顶层扁平字段优先被覆盖
            ps = _platform_settings_for(data, platform) or {}
            poi_name = ""
            if isinstance(ps.get("poi"), dict):
                poi_name = ps.get("poi", {}).get("name", "")
            elif isinstance(ps.get("location"), dict):
                poi_name = ps.get("location", {}).get("name", "")
            mini_program = ps.get("miniProgram") or ps.get("mini_program") or None

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
                category_id=data.get("category_id", 160),
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
