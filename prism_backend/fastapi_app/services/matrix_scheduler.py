"""
矩阵发布调度器
核心逻辑：平台优先 → 账号轮询 → 素材分配
"""
import sys
import threading
from typing import Dict, List, Optional
from collections import deque
from pathlib import Path
from datetime import datetime
import uuid
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from fastapi_app.models.matrix_task import MatrixTask, TaskStatus
from fastapi_app.core.logger import logger


class MatrixScheduler:
    """矩阵任务调度器"""

    def __init__(self):
        self.pending_queue = deque()  # 待执行队列
        self.retry_queue = deque()    # 重试队列（优先级更高）
        self.running = []             # 正在执行的任务
        self.finished = []            # 已完成任务
        self.failed = []              # 失败任务
        self._lock = threading.Lock()
        
        # 任务索引（快速查找）
        self.task_index: Dict[str, MatrixTask] = {}
        self.tasks_file = Path("data/matrix_tasks.json")
        self._load_tasks()

    def _load_tasks(self):
        """从文件加载任务"""
        if self.tasks_file.exists():
            try:
                with open(self.tasks_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        try:
                            task = MatrixTask(**item)
                            self.task_index[task.task_id] = task
                            
                            # 根据状态恢复队列
                            if task.status == TaskStatus.PENDING:
                                self.pending_queue.append(task)
                            elif task.status == TaskStatus.RETRY or task.status == TaskStatus.NEED_VERIFICATION:
                                self.retry_queue.append(task)
                            elif task.status == TaskStatus.RUNNING:
                                # 重启后，运行中的任务重置为 Pending 或 Retry
                                task.status = TaskStatus.RETRY
                                task.retry_count += 1
                                task.error_message = f"System restarted at {datetime.now()}"
                                self.retry_queue.append(task)
                            elif task.status == TaskStatus.FINISHED:
                                self.finished.append(task)
                            elif task.status == TaskStatus.FAILED:
                                self.failed.append(task)
                        except Exception as e:
                            logger.error(f"Error loading task item: {e}")
                logger.info(f"已加载 {len(self.task_index)} 个矩阵任务")
            except Exception as e:
                logger.error(f"Failed to load matrix tasks: {e}")

    def _save_tasks(self):
        """保存任务到文件"""
        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            # 序列化所有任务
            data = [t.model_dump(mode="json") for t in self.task_index.values()]
            with open(self.tasks_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save matrix tasks: {e}")

    def generate_tasks(
        self,
        platforms: List[str],
        accounts: Dict[str, List[str]],
        materials: List[str],
        title: Optional[str] = None,
        description: Optional[str] = None,
        topics: Optional[List[str]] = None,
        cover_path: Optional[str] = None,
        material_configs: Optional[Dict[str, dict]] = None,
        batch_name: Optional[str] = None,
        interval_enabled: bool = False,
        interval_mode: str = "account_video",
        interval_minutes: int = 30,
        schedule_type: str = "immediate",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> List[MatrixTask]:
        """
        生成矩阵任务
        
        核心规则：
        1. 遍历所有选中素材
        2. 给每个素材分配账号 (轮询)
        3. 确保所有素材都被挂载到任务中
        4. 如果interval_enabled=True，根据interval_mode设置定时发布时间
        5. 如果interval_enabled=False，所有任务同时发布（scheduled_time相同）
        """
        from datetime import datetime, timedelta
        
        batch_id = str(uuid.uuid4())
        all_tasks = []

        logger.info(f"开始生成矩阵任务: batch_id={batch_id}, 平台={len(platforms)}, 素材={len(materials)}, "
                   f"interval_enabled={interval_enabled}, interval_mode={interval_mode}, interval_minutes={interval_minutes}")

        # 计算基础开始时间
        if schedule_type == "immediate":
            base_time = datetime.now()
        elif start_time:
            try:
                base_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            except:
                base_time = datetime.now()
        else:
            base_time = datetime.now()

        # 按平台优先级处理
        for platform_priority, platform in enumerate(platforms):
            account_list = accounts.get(platform, [])
            if not account_list:
                logger.warning(f"平台 {platform} 没有可用账号，跳过")
                continue

            # 根据intervalMode计算每个任务的scheduled_time
            if not interval_enabled:
                # 间隔方式关闭：所有任务同时发布
                logger.info(f"平台 {platform}: 间隔方式关闭，所有任务将同时发布")
                for i, material_id in enumerate(materials):
                    account_index = i % len(account_list)
                    account_id = account_list[account_index]
                    
                    # 所有任务使用相同的base_time
                    self._create_and_add_task(
                        platform=platform,
                        account_id=account_id,
                        material_id=material_id,
                        material_configs=material_configs,
                        title=title,
                        description=description,
                        topics=topics,
                        cover_path=cover_path,
                        batch_id=batch_id,
                        platform_priority=platform_priority,
                        scheduled_time=base_time,  # 所有任务相同时间
                        all_tasks=all_tasks
                    )
                    
            elif interval_mode == "account_video":
                # 按账号&视频间隔：各账号开始时间不同，视频在账号内间隔
                # 例如: 
                # - Account1: 视频1(+0min), 视频2(+30min), 视频3(+60min)
                # - Account2: 视频1(+5min), 视频2(+35min), 视频3(+65min)
                # - Account3: 视频1(+10min), 视频2(+40min), 视频3(+70min)
                for i, material_id in enumerate(materials):
                    account_index = i % len(account_list)
                    account_id = account_list[account_index]
                    
                    # 账号在材料中的排序位置(第几个材料分配给这个账号)
                    material_order_in_account = i // len(account_list)
                    
                    # 计算定时时间：账号偏移 + 视频序号偏移
                    account_offset_minutes = account_index * 5  # 账号间隔5分钟启动
                    video_offset_minutes = material_order_in_account * interval_minutes
                    total_offset_minutes = account_offset_minutes + video_offset_minutes
                    
                    scheduled_time = base_time + timedelta(minutes=total_offset_minutes)
                    
                    self._create_and_add_task(
                        platform=platform,
                        account_id=account_id,
                        material_id=material_id,
                        material_configs=material_configs,
                        title=title,
                        description=description,
                        topics=topics,
                        cover_path=cover_path,
                        batch_id=batch_id,
                        platform_priority=platform_priority,
                        scheduled_time=scheduled_time,
                        all_tasks=all_tasks
                    )
                    
            elif interval_mode == "video":
                # 按视频间隔：各账号同时开始，视频在账号内按间隔
                # 例如:
                # - Account1: 视频1(+0min), 视频2(+30min), 视频3(+60min)
                # - Account2: 视频1(+0min), 视频2(+30min), 视频3(+60min)
                # - Account3: 视频1(+0min), 视频2(+30min), 视频3(+60min)
                for i, material_id in enumerate(materials):
                    account_index = i % len(account_list)
                    account_id = account_list[account_index]
                    
                    # 视频在账号内的序号
                    material_order_in_account = i // len(account_list)
                    
                    # 计算定时时间：只根据视频序号偏移
                    video_offset_minutes = material_order_in_account * interval_minutes
                    scheduled_time = base_time + timedelta(minutes=video_offset_minutes)
                    
                    self._create_and_add_task(
                        platform=platform,
                        account_id=account_id,
                        material_id=material_id,
                        material_configs=material_configs,
                        title=title,
                        description=description,
                        topics=topics,
                        cover_path=cover_path,
                        batch_id=batch_id,
                        platform_priority=platform_priority,
                        scheduled_time=scheduled_time,
                        all_tasks=all_tasks
                    )
            else:
                # 回退到原来的逻辑（immediate模式）
                for i, material_id in enumerate(materials):
                    account_index = i % len(account_list)
                    account_id = account_list[account_index]
                    
                    self._create_and_add_task(
                        platform=platform,
                        account_id=account_id,
                        material_id=material_id,
                        material_configs=material_configs,
                        title=title,
                        description=description,
                        topics=topics,
                        cover_path=cover_path,
                        batch_id=batch_id,
                        platform_priority=platform_priority,
                        scheduled_time=None,
                        all_tasks=all_tasks
                    )

        logger.info(f"矩阵任务生成完成: 总计 {len(all_tasks)} 个任务")
        self._save_tasks()
        return all_tasks
    
    def _create_and_add_task(
        self,
        platform: str,
        account_id: str,
        material_id: str,
        material_configs: Optional[Dict],
        title: Optional[str],
        description: Optional[str],
        topics: Optional[List[str]],
        cover_path: Optional[str],
        batch_id: str,
        platform_priority: int,
        scheduled_time: Optional[datetime],
        all_tasks: List[MatrixTask]
    ):
        """Helper method to create and add a task"""
        # 获取素材差异化配置
        mat_config = (material_configs or {}).get(material_id, {})
        final_title = mat_config.get('title') or title
        final_description = mat_config.get('description') or description
        final_topics = mat_config.get('topics') or topics or []
        final_cover = mat_config.get('cover_path') or cover_path

        # 创建任务
        task = MatrixTask.create(
            platform=platform,
            account_id=account_id,
            material_id=material_id,
            title=final_title,
            description=final_description,
            topics=final_topics,
            cover_path=final_cover,
            batch_id=batch_id,
            priority=platform_priority + 1
        )
        
        # 设置定时时间
        if scheduled_time:
            task.scheduled_time = scheduled_time
        
        all_tasks.append(task)
        self.pending_queue.append(task)
        self.task_index[task.task_id] = task

    def get_next_task(self) -> Optional[MatrixTask]:
        """
        获取下一个待执行任务（不移除）
        优先级：retry_queue > pending_queue
        """
        if self.retry_queue:
            return self.retry_queue[0]
        if self.pending_queue:
            return self.pending_queue[0]
        return None

    def pop_next_task(self) -> Optional[MatrixTask]:
        """
        弹出下一个待执行任务
        优先级：retry_queue > pending_queue
        """
        task = None

        with self._lock:
            if self.retry_queue:
                task = self.retry_queue.popleft()
                logger.info(f"从 retry 队列弹出任务: {task.task_id}")
            elif self.pending_queue:
                task = self.pending_queue.popleft()
                logger.info(f"从 pending 队列弹出任务: {task.task_id}")

            if task:
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now()
                self.running.append(task)
                self._save_tasks()

        return task

    def pop_next_tasks(self, limit: int) -> List[MatrixTask]:
        """批量弹出待执行任务"""
        tasks: List[MatrixTask] = []
        if limit <= 0:
            return tasks

        with self._lock:
            for _ in range(limit):
                task = None
                if self.retry_queue:
                    task = self.retry_queue.popleft()
                    logger.info(f"从 retry 队列弹出任务: {task.task_id}")
                elif self.pending_queue:
                    task = self.pending_queue.popleft()
                    logger.info(f"从 pending 队列弹出任务: {task.task_id}")
                else:
                    break

                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now()
                self.running.append(task)
                tasks.append(task)

            if tasks:
                self._save_tasks()

        return tasks

    def report_result(
        self,
        task_id: str,
        status: str,
        message: str = "",
        verification_url: Optional[str] = None
    ) -> Optional[MatrixTask]:
        """
        上报任务执行结果
        
        状态：
        - success: 成功 → finished
        - fail: 失败 → failed (超过最大重试次数) 或 retry
        - need_verification: 需要验证 → retry 队列末尾
        """
        with self._lock:
            task = self.task_index.get(task_id)
            if not task:
                logger.error(f"任务 {task_id} 不存在")
                return None

            # 从当前队列中移除
            self._remove_from_all_queues(task)

            if status == "success":
                task.status = TaskStatus.FINISHED
                task.completed_at = datetime.now()
                self.finished.append(task)
                logger.info(f"任务 {task_id} 执行成功")

            elif status == "fail":
                task.retry_count += 1
                task.error_message = message

                if task.retry_count >= task.max_retries:
                    task.status = TaskStatus.FAILED
                    task.completed_at = datetime.now()
                    self.failed.append(task)
                    logger.error(f"任务 {task_id} 失败 (已达最大重试次数 {task.max_retries})")
                else:
                    task.status = TaskStatus.RETRY
                    self.retry_queue.append(task)
                    logger.warning(f"任务 {task_id} 失败，进入重试队列 (重试 {task.retry_count}/{task.max_retries})")

            elif status == "need_verification":
                task.status = TaskStatus.NEED_VERIFICATION
                task.verification_url = verification_url
                task.error_message = message
                self.retry_queue.append(task)
                logger.warning(f"任务 {task_id} 需要验证，移至 retry 队列末尾")

            self._save_tasks()
            return task

    def _remove_from_all_queues(self, task: MatrixTask):
        """从所有队列中移除任务"""
        for queue in [self.pending_queue, self.retry_queue, self.running]:
            try:
                queue.remove(task)
            except (ValueError, AttributeError):
                pass

    def get_task_by_id(self, task_id: str) -> Optional[MatrixTask]:
        """根据ID获取任务"""
        return self.task_index.get(task_id)

    def get_all_tasks(self) -> Dict[str, List[MatrixTask]]:
        """获取所有任务列表"""
        return {
            "pending": list(self.pending_queue),
            "retry": list(self.retry_queue),
            "running": self.running.copy(),
            "finished": self.finished.copy(),
            "failed": self.failed.copy(),
        }

    def get_statistics(self) -> Dict[str, int]:
        """获取任务统计"""
        return {
            "pending": len(self.pending_queue),
            "retry": len(self.retry_queue),
            "running": len(self.running),
            "finished": len(self.finished),
            "failed": len(self.failed),
            "total": len(self.task_index),
        }

    def reset(self):
        """重置所有队列"""
        self.pending_queue.clear()
        self.retry_queue.clear()
        self.running.clear()
        self.finished.clear()
        self.failed.clear()
        self.task_index.clear()
        self._save_tasks()
        logger.info("任务调度器已重置")

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self.task_index.get(task_id)
        if not task:
            return False
        
        self._remove_from_all_queues(task)
        task.status = TaskStatus.FAILED
        task.error_message = "用户取消"
        task.completed_at = datetime.now()
        self.failed.append(task)
        self._save_tasks()
        logger.info(f"任务 {task_id} 已取消")
        return True


# 全局单例
_matrix_scheduler: Optional[MatrixScheduler] = None


def get_matrix_scheduler() -> MatrixScheduler:
    """获取矩阵调度器单例"""
    global _matrix_scheduler
    if _matrix_scheduler is None:
        _matrix_scheduler = MatrixScheduler()
        logger.info("矩阵调度器初始化完成")
    return _matrix_scheduler
