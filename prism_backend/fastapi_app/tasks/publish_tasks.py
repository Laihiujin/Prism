"""
Celery 发布任务定义
替代原有的内存队列系统，使用 Redis 持久化
"""
from __future__ import annotations

import asyncio
import json
import traceback
import sys
import os
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

from celery import Task
from loguru import logger

from fastapi_app.tasks.celery_app import celery_app
from fastapi_app.tasks.task_state_manager import task_state_manager
from fastapi_app.tasks.concurrency_controller import concurrency_controller, ConcurrencyLimitException
from fastapi_app.core.timezone_utils import now_beijing_naive, now_beijing_iso

BASE_DIR = Path(__file__).resolve().parents[2]


def _ensure_backend_on_path() -> None:
    candidates = [
        BASE_DIR,
        BASE_DIR.parent,
        Path.cwd().resolve(),
    ]
    for candidate in candidates:
        if (candidate / "myUtils").exists():
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)
            pythonpath = os.environ.get("PYTHONPATH", "")
            if candidate_str not in pythonpath.split(os.pathsep):
                os.environ["PYTHONPATH"] = os.pathsep.join(
                    [candidate_str, pythonpath] if pythonpath else [candidate_str]
                )
            break


_ensure_backend_on_path()


class CallbackTask(Task):
    """支持任务状态回调的基础任务类"""

    def on_success(self, retval, task_id, args, kwargs):
        """任务成功回调"""
        logger.info(f"[Celery] Task {task_id} succeeded")
        task_state_manager.update_task_state(
            task_id=task_id,
            status="success",
            result=retval,
            completed_at=now_beijing_naive()
        )

        # ✅ 同时写入 SQLite 任务历史（保存7天）
        self._save_to_publish_tasks(task_id, kwargs.get('task_data', {}), status="success", result=retval)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败回调"""
        logger.error(f"[Celery] Task {task_id} failed: {exc}")
        error_msg = f"{str(exc)}\n{traceback.format_exc()}"

        task_state_manager.update_task_state(
            task_id=task_id,
            status="failed",
            error_message=error_msg,
            completed_at=now_beijing_naive()
        )

        # ✅ 同时写入 SQLite 任务历史
        self._save_to_publish_tasks(task_id, kwargs.get('task_data', {}), status="failed", error_message=error_msg)

        # 检查是否需要短信验证（转入人工任务）
        if "SMS_VERIFICATION_REQUIRED" in str(exc):
            self._handle_sms_verification(task_id, kwargs.get('task_data', {}))

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """任务重试回调"""
        logger.warning(f"[Celery] Task {task_id} retrying: {exc}")
        task_state_manager.update_task_state(
            task_id=task_id,
            status="retry"
        )

    def _handle_sms_verification(self, task_id: str, task_data: Dict):
        """处理短信验证异常 - 转入人工任务库"""
        try:
            from fastapi_app.services.manual_task_manager import manual_task_manager

            platform = task_data.get('platform', 'unknown')
            account_id = task_data.get('account_id', 'unknown')
            account_name = task_data.get('account_name', '')
            material_id = task_data.get('file_id', '')
            title = task_data.get('title', '')
            description = task_data.get('description', '')

            manual_task_manager.add_task(
                task_id=task_id,
                task_type="publish",
                platform=platform,
                account_id=account_id,
                account_name=account_name,
                material_id=material_id,
                title=title,
                description=description,
                reason="需要短信验证码",
                metadata=task_data
            )
            logger.info(f"[Celery] Task {task_id} saved to manual tasks")
        except Exception as e:
            logger.error(f"[Celery] Failed to save to manual tasks: {e}")

    def _save_to_publish_tasks(self, task_id: str, task_data: Dict, status: str, result: Any = None, error_message: str = None):
        """保存任务到 SQLite publish_tasks 表（永久保存，用于历史查询和任务恢复）"""
        try:
            from fastapi_app.db.session import main_db_pool

            platform = task_data.get('platform', 'unknown')
            account_id = task_data.get('account_id', 'unknown')
            material_id = task_data.get('file_id', '')
            title = task_data.get('title', '')
            tags = json.dumps(task_data.get('tags', []), ensure_ascii=False) if task_data.get('tags') else None

            # 保存完整的 task_data（JSON 格式），用于任务重试时完整恢复
            task_data_json = json.dumps(task_data, ensure_ascii=False)

            with main_db_pool.get_connection() as db:
                cursor = db.cursor()

                # 检查任务是否已存在（通过 celery_task_id）
                cursor.execute("SELECT task_id FROM publish_tasks WHERE celery_task_id = ?", (task_id,))
                existing = cursor.fetchone()

                if existing:
                    # 更新已有任务
                    cursor.execute(
                        """
                        UPDATE publish_tasks
                        SET status = ?, error_message = ?, updated_at = ?, published_at = ?, task_data = ?
                        WHERE celery_task_id = ?
                        """,
                        (
                            status,
                            error_message,
                            now_beijing_iso(),
                            now_beijing_iso() if status == "success" else None,
                            task_data_json,
                            task_id
                        )
                    )
                else:
                    # 插入新任务（包含完整的 task_data）
                    cursor.execute(
                        """
                        INSERT INTO publish_tasks (
                            celery_task_id, platform, account_id, material_id, title, tags,
                            status, error_message, task_data, priority, created_at, updated_at, published_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            task_id,
                            str(platform),
                            str(account_id),
                            str(material_id) if material_id else None,
                            title,
                            tags,
                            status,
                            error_message,
                            task_data_json,  # 保存完整的 JSON 数据
                            5,  # 默认优先级
                            now_beijing_iso(),
                            now_beijing_iso(),
                            now_beijing_iso() if status == "success" else None
                        )
                    )

                db.commit()
                logger.debug(f"[Celery] Saved task to SQLite publish_tasks with full task_data: {task_id}")

        except Exception as e:
            logger.error(f"[Celery] Failed to save to publish_tasks: {e}")


@celery_app.task(name="publish.single", base=CallbackTask, bind=True, max_retries=0)
def publish_single_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    单个发布任务（支持动态并发控制）

    Args:
        task_data: 发布任务数据
            - platform: 平台ID (1=抖音, 2=小红书, 3=快手, 4=视频号, 5=B站)
            - account_id: 账号ID
            - file_id: 素材ID
            - title: 标题
            - description: 描述
            - tags: 标签列表

    Returns:
        Dict: 执行结果
    """
    task_id = self.request.id
    logger.info(f"[Celery] Starting publish task {task_id}")

    # 更新任务状态为运行中
    task_state_manager.update_task_state(
        task_id=task_id,
        status="running",
        started_at=now_beijing_naive()
    )

    # 提取并发控制参数
    platform_id = task_data.get('platform')
    account_id = task_data.get('account_id')

    # 平台ID映射到平台名称
    PLATFORM_MAP = {
        1: "xiaohongshu",
        2: "channels",
        3: "douyin",
        4: "kuaishou",
        5: "bilibili"
    }
    platform_name = PLATFORM_MAP.get(int(platform_id)) if platform_id else None

    try:
        # 使用并发控制器获取执行令牌
        with concurrency_controller.acquire(
            platform=platform_name,
            account_id=str(account_id) if account_id else None,
            task_type="publish"
        ):
            _ensure_backend_on_path()
            # 动态导入（避免循环依赖）
            from myUtils.batch_publish_service import BatchPublishService

            # 创建临时服务实例执行发布
            service = BatchPublishService(task_manager=None)

            # 执行异步发布逻辑
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(service.handle_single_publish(task_data))
            finally:
                loop.close()

            # 更新素材状态为已发布
            if task_data.get('file_id'):
                _update_material_status(task_data)

            logger.info(f"[Celery] Task {task_id} completed successfully")
            return result

    except ConcurrencyLimitException as e:
        # 并发限制异常 - 重新入队
        logger.warning(f"[Celery] Task {task_id} concurrency limited: {e}, retrying...")
        # 延迟重试（5秒后）
        raise self.retry(exc=e, countdown=5, max_retries=3)

    except Exception as e:
        logger.error(f"[Celery] Task {task_id} failed: {e}")
        # 将失败任务转入人工处理
        _save_to_manual_tasks(task_id, task_data, str(e))
        raise


@celery_app.task(name="publish.batch", base=CallbackTask, bind=True)
def publish_batch_task(self, batch_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    批量发布任务

    Args:
        batch_data: 批量发布数据
            - items: 发布任务列表
            - batch_id: 批次ID

    Returns:
        Dict: 批量执行结果
    """
    task_id = self.request.id
    batch_id = batch_data.get('batch_id', task_id)
    items = batch_data.get('items', [])

    logger.info(f"[Celery] Starting batch task {task_id}, items: {len(items)}")

    # 更新批次任务状态
    task_state_manager.update_task_state(
        task_id=task_id,
        status="running",
        started_at=now_beijing_naive()
    )

    # 提交所有子任务到 Celery
    sub_task_ids = []
    for item in items:
        # 使用 apply_async 提交任务
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

    logger.info(f"[Celery] Batch {batch_id} submitted {len(sub_task_ids)} sub-tasks")

    return {
        "batch_id": batch_id,
        "task_ids": sub_task_ids,
        "total": len(sub_task_ids),
        "status": "submitted"
    }


def _update_material_status(task_data: Dict):
    """更新素材状态为已发布"""
    try:
        file_id = task_data.get('file_id')
        platform = task_data.get('platform')
        account_id = task_data.get('account_id')

        if not file_id:
            return

        from fastapi_app.db.session import main_db_pool

        with main_db_pool.get_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """UPDATE file_records
                   SET status = ?, published_at = ?, last_platform = ?, last_accounts = ?
                   WHERE id = ?""",
                ('published', now_beijing_iso(), platform, account_id, file_id)
            )
            db.commit()
            logger.info(f"[Celery] Updated material status: file_id={file_id}")
    except Exception as e:
        logger.error(f"[Celery] Failed to update material status: {e}")


def _save_to_manual_tasks(task_id: str, task_data: Dict, error_msg: str):
    """保存失败任务到人工处理库"""
    try:
        from fastapi_app.services.manual_task_manager import manual_task_manager

        platform = task_data.get('platform', 'unknown')
        account_id = task_data.get('account_id', 'unknown')
        account_name = task_data.get('account_name', '')
        material_id = task_data.get('file_id', '')
        title = task_data.get('title', '')
        description = task_data.get('description', '')

        manual_task_manager.add_task(
            task_id=task_id,
            task_type="publish_failed",
            platform=platform,
            account_id=account_id,
            account_name=account_name,
            material_id=material_id,
            title=title,
            description=description,
            reason=f"发布失败: {error_msg}",
            metadata=task_data
        )
        logger.info(f"[Celery] Failed task saved to manual tasks: {task_id}")
    except Exception as e:
        logger.error(f"[Celery] Failed to save to manual tasks: {e}")
