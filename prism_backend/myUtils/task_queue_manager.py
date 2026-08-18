"""
任务队列管理器
功能：
1. 管理批量发布任务队列
2. 支持任务优先级
3. 并发控制
4. 任务状态追踪
5. 失败重试机制
"""
import asyncio
import sqlite3
import threading
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable
from enum import Enum
from queue import PriorityQueue, Empty
import traceback
from loguru import logger

# 任务状态枚举
class TaskStatus(str, Enum):
    PENDING = "pending"       # 待执行
    RUNNING = "running"       # 执行中
    SUCCESS = "success"       # 成功
    FAILED = "failed"         # 失败
    CANCELLED = "cancelled"   # 已取消
    RETRY = "retry"          # 等待重试

# 任务类型枚举
class TaskType(str, Enum):
    PUBLISH = "publish"              # 发布任务
    DATA_COLLECT = "data_collect"    # 数据采集
    ACCOUNT_CHECK = "account_check"  # 账号检查
    BATCH_PUBLISH = "batch_publish"  # 批量发布

class Task:
    """任务对象"""
    def __init__(
        self,
        task_id: str,
        task_type: TaskType,
        data: Dict,
        priority: int = 5,
        max_retries: int = 3
    ):
        self.task_id = task_id
        self.task_type = task_type
        self.data = data
        self.priority = priority
        self.max_retries = max_retries
        self.retry_count = 0
        self.status = TaskStatus.PENDING
        self.error_message = None
        self.result = None
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None

    def __lt__(self, other):
        """优先级比较（数字越小优先级越高）"""
        return self.priority < other.priority

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "data": self.data,
            "priority": self.priority,
            "status": self.status,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "error_message": self.error_message,
            "result": self.result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }

class TaskQueueManager:
    """任务队列管理器"""

    def __init__(self, db_path: Path, max_workers: int = 3):
        self.db_path = db_path
        self.max_workers = max_workers
        self.task_queue = PriorityQueue()
        self.workers = []
        self.running = False
        self.task_handlers = {}
        self.active_tasks = {}
        self.lock = threading.Lock()

        # 初始化数据库
        self.init_database()

    def init_database(self):
        """初始化任务数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 创建任务表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    task_type TEXT NOT NULL,
                    priority INTEGER DEFAULT 5,
                    status TEXT DEFAULT 'pending',
                    data TEXT,
                    result TEXT,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_status
                ON task_queue(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_type
                ON task_queue(task_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_created
                ON task_queue(created_at)
            """)

            conn.commit()
            logger.info("[TaskQueue] 数据库初始化完成")

    def register_handler(self, task_type: TaskType, handler: Callable):
        """注册任务处理器"""
        self.task_handlers[task_type] = handler
        logger.info(f"[TaskQueue] 注册处理器: {task_type}")

    def add_task(self, task: Task) -> bool:
        """添加任务到队列"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO task_queue (
                        task_id, task_type, priority, status, data,
                        max_retries, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    task.task_id,
                    task.task_type,
                    task.priority,
                    task.status,
                    json.dumps(task.data),
                    task.max_retries,
                    task.created_at.isoformat()
                ))
                conn.commit()

            # 添加到内存队列
            self.task_queue.put((task.priority, task))
            logger.info(f"[TaskQueue] 任务已添加: {task.task_id} ({task.task_type})")
            return True

        except Exception as e:
            logger.error(f"[TaskQueue] 添加任务失败: {e}")
            return False

    def update_task_status(self, task: Task):
        """更新任务状态到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE task_queue SET
                        status = ?,
                        result = ?,
                        error_message = ?,
                        retry_count = ?,
                        started_at = ?,
                        completed_at = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE task_id = ?
                """, (
                    task.status,
                    json.dumps(task.result) if task.result else None,
                    task.error_message,
                    task.retry_count,
                    task.started_at.isoformat() if task.started_at else None,
                    task.completed_at.isoformat() if task.completed_at else None,
                    task.task_id
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"[TaskQueue] 更新任务状态失败: {e}")

    async def execute_task(self, task: Task) -> bool:
        """执行单个任务"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self.update_task_status(task)

        with self.lock:
            self.active_tasks[task.task_id] = task

        try:
            logger.info(f"[TaskQueue] 开始执行任务: {task.task_id} ({task.task_type})")

            # 获取任务处理器
            handler = self.task_handlers.get(task.task_type)
            if not handler:
                raise Exception(f"未找到任务类型 {task.task_type} 的处理器")

            # 执行任务
            result = await handler(task.data)

            # 标记成功
            task.status = TaskStatus.SUCCESS
            task.result = result
            task.completed_at = datetime.now()

            logger.info(f"[TaskQueue] 任务执行成功: {task.task_id}")

            # 如果是发布任务，更新文件状态为已发布
            if task.task_type == TaskType.PUBLISH:
                try:
                    file_id = task.data.get('file_id')
                    platform = task.data.get('platform')
                    account_id = task.data.get('account_id')

                    if file_id:
                        from fastapi_app.db.session import main_db_pool
                        with main_db_pool.get_connection() as db:
                            cursor = db.cursor()
                            cursor.execute(
                                """UPDATE file_records
                                   SET status = ?, published_at = ?, last_platform = ?, last_accounts = ?
                                   WHERE id = ?""",
                                ('published', datetime.now().isoformat(), platform, account_id, file_id)
                            )
                            db.commit()
                            logger.info(f"[TaskQueue] 已更新素材状态为已发布: file_id={file_id}")
                except Exception as update_error:
                    logger.error(f"[TaskQueue] 更新素材状态失败: {update_error}")
                    # 不影响任务成功状态

            return True

        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            task.error_message = error_msg

            # 检查是否需要短信验证（特殊处理）
            if "SMS_VERIFICATION_REQUIRED" in str(e):
                logger.warning(f"[TaskQueue] 检测到需要短信验证，保存到人工任务库: {task.task_id}")
                try:
                    from fastapi_app.services.manual_task_manager import manual_task_manager
                    
                    # 提取任务信息
                    platform = task.data.get('platform', 'unknown')
                    account_id = task.data.get('account_id', 'unknown')
                    account_name = task.data.get('account_name', '')
                    material_id = task.data.get('file_id', '')
                    title = task.data.get('title', '')
                    description = task.data.get('description', '')
                    
                    # 添加到人工任务库
                    manual_task_manager.add_task(
                        task_id=task.task_id,
                        task_type="publish",
                        platform=platform,
                        account_id=account_id,
                        account_name=account_name,
                        material_id=material_id,
                        title=title,
                        description=description,
                        reason="需要短信验证码",
                        metadata=task.data
                    )
                    
                    # 标记任务为失败（不再重试）
                    task.status = TaskStatus.FAILED
                    task.completed_at = datetime.now()
                    logger.info(f"[TaskQueue] 任务已保存到人工任务库，可稍后人工处理")
                    return False
                    
                except Exception as save_error:
                    logger.error(f"[TaskQueue] 保存到人工任务库失败: {save_error}")
                    # 继续执行原有的重试逻辑
            
            # 检查是否是验证码异常（特殊处理）
            if "CaptchaRequiredException" in str(type(e).__name__):
                logger.warning(f"[TaskQueue] 检测到验证码，将任务后移到队列末尾: {task.task_id}")
                # 将任务移到队列末尾（最低优先级）
                retry_task = Task(
                    task_id=task.task_id,
                    task_type=task.task_type,
                    data=task.data,
                    priority=99,  # 最低优先级
                    max_retries=task.max_retries
                )
                retry_task.retry_count = task.retry_count
                task.status = TaskStatus.PENDING  # 重置为pending
                self.task_queue.put((retry_task.priority, retry_task))
                return False

            # 检查是否是账号封禁异常（不重试，直接失败）
            if "AccountBlockedException" in str(type(e).__name__):
                logger.error(f"[TaskQueue] 账号被封禁，任务失败: {task.task_id}")
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                return False

            # 禁用自动重试，将所有失败任务转入人工任务库
            logger.warning(f"[TaskQueue] 任务失败，转入人工处理: {task.task_id}")
            try:
                from fastapi_app.services.manual_task_manager import manual_task_manager
                
                # 提取任务信息
                platform = task.data.get('platform', 'unknown')
                account_id = task.data.get('account_id', 'unknown')
                account_name = task.data.get('account_name', '')
                material_id = task.data.get('file_id', '')
                title = task.data.get('title', '')
                description = task.data.get('description', '')
                
                # 添加到人工任务库
                manual_task_manager.add_task(
                    task_id=task.task_id,
                    task_type="publish_failed", # 标记为发布失败
                    platform=platform,
                    account_id=account_id,
                    account_name=account_name,
                    material_id=material_id,
                    title=title,
                    description=description,
                    reason=f"发布失败: {str(e)}",
                    metadata=task.data
                )
                logger.info(f"[TaskQueue] 失败任务已保存到人工任务库")
            except Exception as save_error:
                logger.error(f"[TaskQueue] 保存到人工任务库失败: {save_error}")

            # 标记为失败
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error_message = error_msg
            return False

        finally:
            self.update_task_status(task)
            with self.lock:
                if task.task_id in self.active_tasks:
                    del self.active_tasks[task.task_id]

    async def worker(self, worker_id: int):
        """工作线程"""
        logger.info(f"[TaskQueue] Worker-{worker_id} 启动")

        while self.running:
            try:
                # 从队列获取任务（超时1秒）
                try:
                    priority, task = self.task_queue.get(timeout=1)
                except Empty:
                    await asyncio.sleep(0.1)
                    continue

                # Optional scheduling: if task specifies `not_before`, delay execution.
                try:
                    not_before = task.data.get("not_before") if isinstance(task.data, dict) else None
                    if not_before:
                        nb_dt: Optional[datetime] = None
                        if isinstance(not_before, (int, float)):
                            nb_dt = datetime.fromtimestamp(float(not_before))
                        elif isinstance(not_before, str):
                            s = not_before.strip().replace("T", " ").replace("Z", "")
                            try:
                                nb_dt = datetime.fromisoformat(s)
                            except Exception:
                                nb_dt = None

                        if nb_dt:
                            now = datetime.now()
                            if now < nb_dt:
                                # Re-queue and sleep a bit to avoid busy looping.
                                self.task_queue.put((priority, task))
                                self.task_queue.task_done()
                                await asyncio.sleep(min((nb_dt - now).total_seconds(), 1.0))
                                continue
                except Exception:
                    # Never block task execution due to scheduling parse errors.
                    pass

                # 执行任务
                await self.execute_task(task)

                # 标记任务完成
                self.task_queue.task_done()

            except Exception as e:
                logger.error(f"[TaskQueue] Worker-{worker_id} 错误: {e}")
                await asyncio.sleep(1)

        logger.info(f"[TaskQueue] Worker-{worker_id} 停止")

    def start(self):
        """启动任务队列"""
        if self.running:
            logger.warning("[TaskQueue] 任务队列已在运行")
            return

        self.running = True
        logger.info(f"[TaskQueue] 启动任务队列 ({self.max_workers} workers)")

        # 加载未完成的任务
        self.load_pending_tasks()

        # 启动工作线程
        loop = asyncio.new_event_loop()

        def run_workers():
            asyncio.set_event_loop(loop)
            tasks = [self.worker(i) for i in range(self.max_workers)]
            loop.run_until_complete(asyncio.gather(*tasks))

        worker_thread = threading.Thread(target=run_workers, daemon=True)
        worker_thread.start()
        self.workers.append(worker_thread)

    def stop(self):
        """停止任务队列"""
        logger.info("[TaskQueue] 停止任务队列...")
        self.running = False

        # 等待所有任务完成
        self.task_queue.join()

        # 等待工作线程结束
        for worker in self.workers:
            worker.join(timeout=5)

        logger.info("[TaskQueue] 任务队列已停止")

    def load_pending_tasks(self):
        """从数据库加载未完成的任务"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT task_id, task_type, priority, data, retry_count, max_retries
                    FROM task_queue
                    WHERE status IN ('pending', 'retry')
                    ORDER BY priority ASC, created_at ASC
                """)

                rows = cursor.fetchall()
                for row in rows:
                    task = Task(
                        task_id=row[0],
                        task_type=TaskType(row[1]),
                        data=json.loads(row[3]) if row[3] else {},
                        priority=row[2],
                        max_retries=row[5]
                    )
                    task.retry_count = row[4]
                    self.task_queue.put((task.priority, task))

                logger.info(f"[TaskQueue] 加载了 {len(rows)} 个待执行任务")

        except Exception as e:
            logger.error(f"[TaskQueue] 加载任务失败: {e}")

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        # 先检查活跃任务
        with self.lock:
            if task_id in self.active_tasks:
                return self.active_tasks[task_id].to_dict()

        # 从数据库查询
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT task_id, task_type, priority, status, data, result,
                           error_message, retry_count, max_retries, created_at,
                           started_at, completed_at
                    FROM task_queue
                    WHERE task_id = ?
                """, (task_id,))

                row = cursor.fetchone()
                if row:
                    return {
                        "task_id": row[0],
                        "task_type": row[1],
                        "priority": row[2],
                        "status": row[3],
                        "data": json.loads(row[4]) if row[4] else {},
                        "result": json.loads(row[5]) if row[5] else None,
                        "error_message": row[6],
                        "retry_count": row[7],
                        "max_retries": row[8],
                        "created_at": row[9],
                        "started_at": row[10],
                        "completed_at": row[11]
                    }

        except Exception as e:
            logger.error(f"[TaskQueue] 查询任务失败: {e}")

        return None

    def list_tasks(self, limit: int = 50, status: Optional[str] = None) -> List[Dict]:
        """获取任务列表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if status:
                    cursor.execute("""
                        SELECT task_id, task_type, priority, status, data, result,
                               retry_count, max_retries, created_at, started_at, completed_at
                        FROM task_queue
                        WHERE status = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (status, limit))
                else:
                    cursor.execute("""
                        SELECT task_id, task_type, priority, status, data, result,
                               retry_count, max_retries, created_at, started_at, completed_at
                        FROM task_queue
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (limit,))

                rows = cursor.fetchall()
                tasks = []
                for row in rows:
                    tasks.append({
                        "task_id": row[0],
                        "task_type": row[1],
                        "priority": row[2],
                        "status": row[3],
                        "data": json.loads(row[4]) if row[4] else {},
                        "result": json.loads(row[5]) if row[5] else None,
                        "retry_count": row[6],
                        "max_retries": row[7],
                        "created_at": row[8],
                        "started_at": row[9],
                        "completed_at": row[10]
                    })

                return tasks

        except Exception as e:
            logger.error(f"[TaskQueue] 获取任务列表失败: {e}")
            return []

    def get_queue_stats(self) -> Dict:
        """获取队列统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 统计各状态任务数
                cursor.execute("""
                    SELECT status, COUNT(*) as count
                    FROM task_queue
                    GROUP BY status
                """)

                status_counts = {row[0]: row[1] for row in cursor.fetchall()}

                # 格式化返回数据
                stats = {
                    'pending': status_counts.get('pending', 0) + status_counts.get('retry', 0),
                    'running': status_counts.get('running', 0),
                    'completed': status_counts.get('success', 0),
                    'failed': status_counts.get('failed', 0),
                    'cancelled': status_counts.get('cancelled', 0),
                    'total': sum(status_counts.values()),
                    'queued': self.task_queue.qsize()
                }

                # 活跃任务数
                with self.lock:
                    stats['active'] = len(self.active_tasks)

                return stats

        except Exception as e:
            logger.error(f"[TaskQueue] 获取统计信息失败: {e}")
            return {}

    def cancel_task(self, task_id: str, force: bool = False) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID
            force: 是否强制取消（包括正在运行的任务）

        Returns:
            bool: 是否成功取消
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if force:
                    # 强制取消：包括running状态的任务
                    cursor.execute("""
                        UPDATE task_queue
                        SET status = ?,
                            error_message = 'Force cancelled by user',
                            completed_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE task_id = ? AND status IN ('pending', 'retry', 'running')
                    """, (TaskStatus.FAILED, task_id))

                    # 从内存活跃任务中移除
                    with self.lock:
                        if task_id in self.active_tasks:
                            del self.active_tasks[task_id]
                            logger.info(f"[TaskQueue] 从活跃任务中移除: {task_id}")
                else:
                    # 正常取消：仅pending和retry
                    cursor.execute("""
                        UPDATE task_queue
                        SET status = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE task_id = ? AND status IN ('pending', 'retry')
                    """, (TaskStatus.CANCELLED, task_id))

                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"[TaskQueue] 任务已取消: {task_id} (force={force})")
                    return True
                else:
                    logger.warning(f"[TaskQueue] 无法取消任务（可能正在执行或已完成）: {task_id}")
                    return False

        except Exception as e:
            logger.error(f"[TaskQueue] 取消任务失败: {e}")
            return False

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM task_queue WHERE task_id = ?", (task_id,))
                conn.commit()
                
                # 同时也从内存队列中尝试移除（如果可能）
                with self.lock:
                    if task_id in self.active_tasks:
                        del self.active_tasks[task_id]

                if cursor.rowcount > 0:
                    logger.info(f"[TaskQueue] 任务已删除: {task_id}")
                    return True
                else:
                    logger.warning(f"[TaskQueue] 无法删除任务（未找到）: {task_id}")
                    return False

        except Exception as e:
            logger.error(f"[TaskQueue] 删除任务失败: {e}")
            return False

# 全局任务队列管理器实例
_task_manager_instance = None

def get_task_manager(db_path: Path = None, max_workers: int = 3) -> TaskQueueManager:
    """获取全局任务队列管理器实例"""
    global _task_manager_instance
    if _task_manager_instance is None:
        if db_path is None:
            raise ValueError("首次调用必须提供 db_path")
        _task_manager_instance = TaskQueueManager(db_path, max_workers)
    return _task_manager_instance
