"""
异步任务池 - 基于asyncio的高并发任务调度

功能:
1. 异步任务提交和执行
2. 并发控制（Semaphore）
3. 任务状态追踪
4. 任务取消支持
"""

import asyncio
import uuid
from typing import Dict, Any, Optional, Coroutine
from datetime import datetime
from enum import Enum
import traceback


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"     # 待执行
    RUNNING = "running"     # 执行中
    COMPLETED = "completed" # 已完成
    FAILED = "failed"       # 失败
    CANCELLED = "cancelled" # 已取消


class AsyncTask:
    """异步任务对象"""
    
    def __init__(self, task_id: str, priority: int = 5):
        self.task_id = task_id
        self.priority = priority
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Any = None
        self.error: Optional[str] = None
        self.task_handle: Optional[asyncio.Task] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "priority": self.priority,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "duration_seconds": (
                (self.completed_at - self.started_at).total_seconds()
                if self.completed_at and self.started_at
                else None
            )
        }


class AsyncTaskPool:
    """
    异步任务池
    
    特性:
    - 并发控制（基于Semaphore）
    - 任务优先级队列
    - 状态追踪
    - 结果缓存
    """
    
    def __init__(self, max_workers: int = 5):
        """
        初始化任务池
        
        Args:
            max_workers: 最大并发任务数
        """
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)
        self.tasks: Dict[str, AsyncTask] = {}
        self.running_tasks: Dict[str, AsyncTask] = {}
        self._lock = asyncio.Lock()
    
    async def submit_task(
        self,
        task_id: Optional[str] = None,
        coro: Optional[Coroutine] = None,
        priority: int = 5
    ) -> str:
        """
        提交异步任务
        
        Args:
            task_id: 任务ID（可选，自动生成）
            coro: 协程对象
            priority: 优先级（1-10，数字越小优先级越高）
        
        Returns:
            task_id: 任务ID
        """
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        if coro is None:
            raise ValueError("协程对象不能为空")
        
        # 创建任务对象
        task = AsyncTask(task_id=task_id, priority=priority)
        
        async with self._lock:
            self.tasks[task_id] = task
        
        # 创建异步任务并执行
        task.task_handle = asyncio.create_task(
            self._execute_with_semaphore(task, coro)
        )
        
        return task_id
    
    async def _execute_with_semaphore(self, task: AsyncTask, coro: Coroutine):
        """
        使用信号量控制并发执行任务
        
        Args:
            task: 任务对象
            coro: 协程对象
        """
        async with self.semaphore:
            try:
                # 更新状态
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now()
                
                async with self._lock:
                    self.running_tasks[task.task_id] = task
                
                print(f"🚀 [AsyncTaskPool] 开始执行任务: {task.task_id}")
                
                # 执行协程
                result = await coro
                
                # 成功完成
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = datetime.now()
                
                duration = (task.completed_at - task.started_at).total_seconds()
                print(f"✅ [AsyncTaskPool] 任务完成: {task.task_id} (耗时: {duration:.2f}s)")
                
            except asyncio.CancelledError:
                # 任务被取消
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                print(f"⚠️ [AsyncTaskPool] 任务已取消: {task.task_id}")
                
            except Exception as e:
                # 执行失败
                task.status = TaskStatus.FAILED
                task.error = f"{str(e)}\n{traceback.format_exc()}"
                task.completed_at = datetime.now()
                print(f"❌ [AsyncTaskPool] 任务失败: {task.task_id}")
                print(f"错误: {task.error}")
                
            finally:
                # 从运行列表中移除
                async with self._lock:
                    if task.task_id in self.running_tasks:
                        del self.running_tasks[task.task_id]
    
    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
        
        Returns:
            任务状态字典，如果任务不存在返回None
        """
        async with self._lock:
            task = self.tasks.get(task_id)
            if task:
                return task.to_dict()
            return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            是否成功取消
        """
        async with self._lock:
            task = self.tasks.get(task_id)
            
            if not task:
                print(f"⚠️ [AsyncTaskPool] 任务不存在: {task_id}")
                return False
            
            if task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                print(f"⚠️ [AsyncTaskPool] 任务无法取消（状态: {task.status}）: {task_id}")
                return False
            
            if task.task_handle and not task.task_handle.done():
                task.task_handle.cancel()
                print(f"✅ [AsyncTaskPool] 任务已取消: {task_id}")
                return True
            
            return False
    
    async def get_pool_stats(self) -> Dict:
        """
        获取任务池统计信息
        
        Returns:
            统计信息字典
        """
        async with self._lock:
            total_tasks = len(self.tasks)
            running_count = len(self.running_tasks)
            
            status_counts = {}
            for task in self.tasks.values():
                status = task.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                "max_workers": self.max_workers,
                "total_tasks": total_tasks,
                "running_tasks": running_count,
                "available_slots": self.max_workers - running_count,
                "status_counts": status_counts
            }
    
    async def wait_all(self, timeout: Optional[float] = None):
        """
        等待所有任务完成
        
        Args:
            timeout: 超时时间（秒），None表示无限等待
        """
        async with self._lock:
            task_handles = [
                task.task_handle
                for task in self.tasks.values()
                if task.task_handle and not task.task_handle.done()
            ]
        
        if task_handles:
            try:
                await asyncio.wait(task_handles, timeout=timeout)
            except asyncio.TimeoutError:
                print(f"⚠️ [AsyncTaskPool] 等待任务超时")
    
    async def clear_completed(self):
        """清理已完成的任务"""
        async with self._lock:
            completed_ids = [
                task_id
                for task_id, task in self.tasks.items()
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
            ]
            
            for task_id in completed_ids:
                del self.tasks[task_id]
            
            print(f"🧹 [AsyncTaskPool] 清理了 {len(completed_ids)} 个已完成任务")
            return len(completed_ids)


# 全局任务池实例
_task_pool_instance: Optional[AsyncTaskPool] = None


def get_task_pool(max_workers: int = 5) -> AsyncTaskPool:
    """
    获取全局任务池实例（单例模式）
    
    Args:
        max_workers: 最大并发数
    
    Returns:
        AsyncTaskPool实例
    """
    global _task_pool_instance
    if _task_pool_instance is None:
        _task_pool_instance = AsyncTaskPool(max_workers=max_workers)
    return _task_pool_instance
