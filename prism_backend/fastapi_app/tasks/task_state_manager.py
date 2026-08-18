"""
任务状态管理器 - 使用 Redis 持久化任务状态
替代原有的 SQLite 任务队列，支持分布式部署
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from loguru import logger

from fastapi_app.cache.redis_client import get_redis
from fastapi_app.core.timezone_utils import now_beijing_naive, now_beijing_iso


class TaskStateManager:
    """基于 Redis 的任务状态管理器"""

    def __init__(self):
        self.redis = get_redis()
        self.key_prefix = "celery:task:"
        self.index_prefix = "celery:index:"

    def _task_key(self, task_id: str) -> str:
        """获取任务的 Redis key"""
        return f"{self.key_prefix}{task_id}"

    def _index_key(self, index_type: str) -> str:
        """获取索引的 Redis key"""
        return f"{self.index_prefix}{index_type}"

    def create_task(
        self,
        task_id: str,
        task_type: str,
        data: Dict[str, Any],
        priority: int = 5,
        parent_task_id: Optional[str] = None
    ) -> bool:
        """
        创建任务记录

        Args:
            task_id: 任务ID（通常是 Celery task_id）
            task_type: 任务类型（publish/batch_publish）
            data: 任务数据
            priority: 优先级
            parent_task_id: 父任务ID（用于批量任务）

        Returns:
            bool: 是否创建成功
        """
        if not self.redis:
            logger.warning("[TaskState] Redis not available, skipping state persistence")
            return False

        try:
            task_state = {
                "task_id": task_id,
                "task_type": task_type,
                "data": data,
                "priority": priority,
                "parent_task_id": parent_task_id,
                "status": "pending",
                "created_at": now_beijing_iso(),
                "started_at": None,
                "completed_at": None,
                "error_message": None,
                "result": None,
                "retry_count": 0
            }

            # 保存任务状态
            self.redis.set(
                self._task_key(task_id),
                json.dumps(task_state, ensure_ascii=False),
                ex=86400 * 7  # 保存7天
            )

            # 添加到状态索引（用于列表查询）
            self.redis.zadd(
                self._index_key(f"status:{task_state['status']}"),
                {task_id: now_beijing_naive().timestamp()}
            )

            # 添加到类型索引
            self.redis.zadd(
                self._index_key(f"type:{task_type}"),
                {task_id: now_beijing_naive().timestamp()}
            )

            logger.debug(f"[TaskState] Created task {task_id}")
            return True

        except Exception as e:
            logger.error(f"[TaskState] Failed to create task: {e}")
            return False

    def update_task_state(
        self,
        task_id: str,
        status: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
        result: Optional[Any] = None,
        retry_count: Optional[int] = None
    ) -> bool:
        """
        更新任务状态

        Args:
            task_id: 任务ID
            status: 状态（pending/running/success/failed/retry）
            started_at: 开始时间
            completed_at: 完成时间
            error_message: 错误信息
            result: 执行结果
            retry_count: 重试次数

        Returns:
            bool: 是否更新成功
        """
        if not self.redis:
            return False

        try:
            # 获取当前任务状态
            task_key = self._task_key(task_id)
            task_json = self.redis.get(task_key)

            if not task_json:
                logger.warning(f"[TaskState] Task {task_id} not found, creating new state")
                # 如果任务不存在，创建一个基础状态
                task_state = {
                    "task_id": task_id,
                    "task_type": "unknown",
                    "data": {},
                    "priority": 5,
                    "parent_task_id": None,
                    "status": status or "running",
                    "created_at": now_beijing_iso(),
                    "started_at": None,
                    "completed_at": None,
                    "error_message": None,
                    "result": None,
                    "retry_count": 0
                }
            else:
                task_state = json.loads(task_json)

            # 更新状态索引
            old_status = task_state.get('status')
            if status and status != old_status:
                # 从旧状态索引中移除
                if old_status:
                    self.redis.zrem(self._index_key(f"status:{old_status}"), task_id)
                # 添加到新状态索引
                self.redis.zadd(
                    self._index_key(f"status:{status}"),
                    {task_id: now_beijing_naive().timestamp()}
                )

            # 更新字段
            if status:
                task_state['status'] = status
            if started_at:
                task_state['started_at'] = started_at.isoformat()
            if completed_at:
                task_state['completed_at'] = completed_at.isoformat()
            if error_message is not None:
                task_state['error_message'] = error_message
            if result is not None:
                task_state['result'] = result
            if retry_count is not None:
                task_state['retry_count'] = retry_count

            task_state['updated_at'] = now_beijing_iso()

            # 保存更新后的状态
            self.redis.set(
                task_key,
                json.dumps(task_state, ensure_ascii=False),
                ex=86400 * 7
            )

            logger.debug(f"[TaskState] Updated task {task_id}, status={status}")
            return True

        except Exception as e:
            logger.error(f"[TaskState] Failed to update task: {e}")
            return False

    def get_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            Dict: 任务状态数据，不存在则返回 None
        """
        if not self.redis:
            return None

        try:
            task_json = self.redis.get(self._task_key(task_id))
            if not task_json:
                return None

            return json.loads(task_json)

        except Exception as e:
            logger.error(f"[TaskState] Failed to get task state: {e}")
            return None

    def list_tasks(
        self,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        列出任务

        Args:
            status: 按状态筛选
            task_type: 按类型筛选
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[Dict]: 任务列表
        """
        if not self.redis:
            return []

        try:
            # 确定查询的索引
            if status:
                # 按指定状态筛选
                index_key = self._index_key(f"status:{status}")
                task_ids = self.redis.zrevrange(index_key, offset, offset + limit - 1)
            elif task_type:
                # 按类型筛选
                index_key = self._index_key(f"type:{task_type}")
                task_ids = self.redis.zrevrange(index_key, offset, offset + limit - 1)
            else:
                # 获取所有任务：合并所有状态索引
                all_task_ids = set()
                for s in ["pending", "running", "success", "failed", "retry", "cancelled"]:
                    status_key = self._index_key(f"status:{s}")
                    ids = self.redis.zrevrange(status_key, 0, -1)
                    all_task_ids.update(ids)

                # 获取所有任务的详情并按创建时间排序
                all_tasks_with_time = []
                for task_id in all_task_ids:
                    task_state = self.get_task_state(task_id)
                    if task_state:
                        # 使用创建时间作为排序依据
                        created_at = task_state.get('created_at', '')
                        all_tasks_with_time.append((created_at, task_state))

                # 按创建时间倒序排序
                all_tasks_with_time.sort(key=lambda x: x[0], reverse=True)

                # 应用分页
                tasks = [task for _, task in all_tasks_with_time[offset:offset + limit]]
                return tasks

            # 批量获取任务详情（当按状态或类型筛选时）
            tasks = []
            for task_id in task_ids:
                task_state = self.get_task_state(task_id)
                if task_state:
                    tasks.append(task_state)

            return tasks

        except Exception as e:
            logger.error(f"[TaskState] Failed to list tasks: {e}")
            return []

    def get_queue_stats(self) -> Dict[str, int]:
        """
        获取队列统计信息

        Returns:
            Dict: 统计数据
        """
        if not self.redis:
            return {
                "pending": 0,
                "running": 0,
                "success": 0,
                "failed": 0,
                "retry": 0,
                "total": 0
            }

        try:
            stats = {
                "pending": self.redis.zcard(self._index_key("status:pending")) or 0,
                "running": self.redis.zcard(self._index_key("status:running")) or 0,
                "success": self.redis.zcard(self._index_key("status:success")) or 0,
                "failed": self.redis.zcard(self._index_key("status:failed")) or 0,
                "retry": self.redis.zcard(self._index_key("status:retry")) or 0,
            }
            stats["total"] = sum(stats.values())

            return stats

        except Exception as e:
            logger.error(f"[TaskState] Failed to get stats: {e}")
            return {}

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务（仅更新状态，实际停止需要 Celery revoke）

        Args:
            task_id: 任务ID

        Returns:
            bool: 是否成功
        """
        try:
            # 撤销 Celery 任务
            from fastapi_app.tasks.celery_app import celery_app
            celery_app.control.revoke(task_id, terminate=True)

            # 更新状态为 cancelled
            return self.update_task_state(
                task_id=task_id,
                status="cancelled",
                completed_at=now_beijing_naive()
            )

        except Exception as e:
            logger.error(f"[TaskState] Failed to cancel task: {e}")
            return False

    def delete_task(self, task_id: str) -> bool:
        """
        删除任务记录

        Args:
            task_id: 任务ID

        Returns:
            bool: 是否成功
        """
        if not self.redis:
            return False

        try:
            # 获取任务状态以便从索引中删除
            task_state = self.get_task_state(task_id)
            if task_state:
                # 从状态索引中移除
                status = task_state.get('status')
                if status:
                    self.redis.zrem(self._index_key(f"status:{status}"), task_id)

                # 从类型索引中移除
                task_type = task_state.get('task_type')
                if task_type:
                    self.redis.zrem(self._index_key(f"type:{task_type}"), task_id)

            # 删除任务数据
            self.redis.delete(self._task_key(task_id))

            logger.info(f"[TaskState] Deleted task {task_id}")
            return True

        except Exception as e:
            logger.error(f"[TaskState] Failed to delete task: {e}")
            return False


# 全局单例
task_state_manager = TaskStateManager()
