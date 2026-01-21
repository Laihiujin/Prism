"""
平台任务管理器
支持高并发的登录和上传任务
使用后台任务 + 任务队列实现
"""
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Optional, Callable, Any
from enum import Enum
import logging
from concurrent.futures import ThreadPoolExecutor
from queue import Queue as ThreadQueue, Empty as QueueEmpty
import threading

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"      # 等待中
    RUNNING = "running"      # 执行中
    SUCCESS = "success"      # 成功
    FAILED = "failed"        # 失败
    TIMEOUT = "timeout"      # 超时


class Task:
    """任务对象"""
    def __init__(self, task_id: str, task_type: str, platform: str, params: dict):
        self.task_id = task_id
        self.task_type = task_type  # login, upload, verify
        self.platform = platform
        self.params = params
        self.status = TaskStatus.PENDING
        self.result = None
        self.error = None
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.progress = 0  # 0-100
        self.message = ""
        
    def to_dict(self):
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "platform": self.platform,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "progress": self.progress,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class PlatformTaskManager:
    """
    平台任务管理器
    支持高并发任务处理
    """
    
    def __init__(self, max_workers: int = 10):
        """
        初始化任务管理器
        
        Args:
            max_workers: 最大并发工作线程数
        """
        self.tasks: Dict[str, Task] = {}
        self.task_queue = ThreadQueue()
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.workers_started = False
        self.lock = threading.Lock()
        
        logger.info(f"任务管理器初始化完成，最大并发数: {max_workers}")
    
    def create_task(self, task_type: str, platform: str, params: dict) -> str:
        """
        创建新任务

        Args:
            task_type: 任务类型 (login, upload, verify)
            platform: 平台名称
            params: 任务参数

        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())
        task = Task(task_id, task_type, platform, params)

        with self.lock:
            self.tasks[task_id] = task

        # 确保工作线程已启动（延迟初始化）
        if not self.workers_started:
            self._start_workers()

        # 将任务加入队列
        self.task_queue.put(task)

        logger.info(f"创建任务: {task_id} ({platform}/{task_type})")
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态字典
        """
        task = self.tasks.get(task_id)
        if task:
            return task.to_dict()
        return None
    
    def update_task_progress(self, task_id: str, progress: int, message: str = ""):
        """
        更新任务进度
        
        Args:
            task_id: 任务ID
            progress: 进度 (0-100)
            message: 进度消息
        """
        task = self.tasks.get(task_id)
        if task:
            task.progress = progress
            task.message = message
            logger.debug(f"任务 {task_id} 进度: {progress}% - {message}")
    
    def _start_workers(self):
        """启动工作线程"""
        if self.workers_started:
            return
        
        for i in range(self.max_workers):
            self.executor.submit(self._worker, i)
        
        self.workers_started = True
        logger.info(f"启动了 {self.max_workers} 个工作线程")
    
    def _worker(self, worker_id: int):
        """
        工作线程

        Args:
            worker_id: 工作线程ID
        """
        logger.info(f"工作线程 {worker_id} 启动")

        while True:
            try:
                # 从队列获取任务（超时1秒）
                task = self.task_queue.get(timeout=1)

                if task is None:  # 停止信号
                    break

                logger.info(f"工作线程 {worker_id} 开始处理任务: {task.task_id}")

                # 更新任务状态
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now()

                try:
                    # 执行任务
                    result = self._execute_task(task)

                    # 任务成功
                    task.status = TaskStatus.SUCCESS
                    task.result = result
                    task.progress = 100
                    task.message = "任务完成"

                except Exception as e:
                    # 任务失败
                    logger.error(f"任务 {task.task_id} 执行失败: {e}")
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    task.message = f"任务失败: {str(e)}"

                finally:
                    task.completed_at = datetime.now()
                    self.task_queue.task_done()

            except QueueEmpty:
                # 队列为空，继续等待（正常情况，不记录日志）
                continue
            except Exception as e:
                # 其他异常才记录
                logger.error(f"工作线程 {worker_id} 异常: {e}", exc_info=True)
    
    def _execute_task(self, task: Task) -> Any:
        """
        执行任务
        
        Args:
            task: 任务对象
            
        Returns:
            任务结果
        """
        # 根据任务类型和平台执行相应的操作
        if task.task_type == "login":
            return self._execute_login(task)
        elif task.task_type == "upload":
            return self._execute_upload(task)
        elif task.task_type == "verify":
            return self._execute_verify(task)
        else:
            raise ValueError(f"未知的任务类型: {task.task_type}")
    
    def _execute_login(self, task: Task) -> dict:
        """
        执行登录任务
        
        Args:
            task: 任务对象
            
        Returns:
            登录结果
        """
        platform = task.platform
        params = task.params
        
        # 更新进度
        self.update_task_progress(task.task_id, 10, "准备登录...")
        
        # 登录统一通过 Playwright Worker，避免在 API 进程中运行浏览器（与 uvicorn --reload 冲突）
        supported = {"kuaishou", "xiaohongshu", "tencent", "douyin", "bilibili"}
        if platform not in supported:
            raise ValueError(f"不支持的平台: {platform}")

        logger.info(f"[TaskManager] 使用 Playwright Worker 进行登录: {platform}")
        self.update_task_progress(task.task_id, 30, "生成二维码...")

        import httpx

        account_id = params.get("account_id") or params.get("id") or "task"
        resp = httpx.post(
            "http://127.0.0.1:7001/qrcode/generate",
            params={"platform": platform, "account_id": account_id, "headless": True},
            timeout=30.0,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("success"):
            raise RuntimeError(payload.get("error") or "Worker generate_qrcode failed")
        qr = payload.get("data") or {}

        self.update_task_progress(task.task_id, 50, "请扫描二维码...")

        return {
            "success": True,
            "message": "二维码已生成，请使用轮询接口完成登录",
            "session_id": qr.get("session_id"),
        }
    
    def _execute_upload(self, task: Task) -> dict:
        """
        执行上传任务
        
        Args:
            task: 任务对象
            
        Returns:
            上传结果
        """
        platform = task.platform
        params = task.params
        
        self.update_task_progress(task.task_id, 10, "准备上传...")
        
        if platform == "kuaishou":
            from platforms.kuaishou.upload import kuaishou_upload

            self.update_task_progress(task.task_id, 30, "打开浏览器...")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    kuaishou_upload.upload(
                        account_file=params["account_file"],
                        title=params["title"],
                        file_path=params["file_path"],
                        tags=params.get("tags", []),
                        publish_date=params.get("publish_date") or None,
                        description=params.get("description", "") or "",
                    )
                )
            finally:
                loop.close()

            return result if isinstance(result, dict) else {"success": True, "message": "上传成功"}
        
        elif platform == "xiaohongshu":
            from platforms.xiaohongshu.upload import xiaohongshu_upload

            file_path = params["file_paths"][0] if params.get("file_paths") else params["file_path"]
            self.update_task_progress(task.task_id, 30, "打开浏览器...")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    xiaohongshu_upload.upload(
                        account_file=params["account_file"],
                        title=params["title"],
                        file_path=file_path,
                        tags=params.get("tags", []),
                        publish_date=params.get("publish_date") or None,
                        thumbnail_path=params.get("thumbnail_path"),
                        description=params.get("description", "") or "",
                    )
                )
            finally:
                loop.close()

            return result if isinstance(result, dict) else {"success": True, "message": "上传成功"}

        elif platform == "douyin":
            # 统一平台层入口（platforms/*）
            from platforms.douyin.upload import douyin_upload

            self.update_task_progress(task.task_id, 30, "打开浏览器...")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    douyin_upload.upload(
                        account_file=params["account_file"],
                        title=params["title"],
                        file_path=params["file_path"],
                        tags=params.get("tags", []),
                        publish_date=params.get("publish_date") or None,
                        thumbnail_path=params.get("thumbnail_path"),
                        product_link=params.get("product_link", "") or params.get("productLink", ""),
                        product_title=params.get("product_title", "") or params.get("productTitle", ""),
                    )
                )
            finally:
                loop.close()

            return result if isinstance(result, dict) else {"success": True, "message": "上传成功"}

        elif platform == "tencent":
            # 统一平台层入口（platforms/*）
            from platforms.tencent.upload import tencent_upload

            self.update_task_progress(task.task_id, 30, "打开浏览器...")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    tencent_upload.upload(
                        account_file=params["account_file"],
                        title=params["title"],
                        file_path=params["file_path"],
                        tags=params.get("tags", []),
                        publish_date=params.get("publish_date") or None,
                        thumbnail_path=params.get("thumbnail_path"),
                        category=params.get("category"),
                        description=params.get("description", "") or "",
                    )
                )
            finally:
                loop.close()

            return result if isinstance(result, dict) else {"success": True, "message": "上传成功"}

        elif platform == "bilibili":
            from platforms.bilibili.upload import bilibili_upload

            self.update_task_progress(task.task_id, 30, "上传中...")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    bilibili_upload.upload(
                        account_file=params["account_file"],
                        title=params["title"],
                        file_path=params["file_path"],
                        tags=params.get("tags", []),
                        publish_date=params.get("publish_date") or None,
                        category_id=params.get("category_id", 160),
                        description=params.get("description", "") or "",
                    )
                )
            finally:
                loop.close()

            return result if isinstance(result, dict) else {"success": True, "message": "上传成功"}
        
        else:
            raise ValueError(f"不支持的平台: {platform}")
    
    def _execute_verify(self, task: Task) -> dict:
        """
        执行Cookie验证任务
        
        Args:
            task: 任务对象
            
        Returns:
            验证结果
        """
        # TODO: 实现Cookie验证
        return {"is_valid": False, "message": "Cookie验证功能待实现"}
    
    def shutdown(self):
        """关闭任务管理器"""
        logger.info("正在关闭任务管理器...")
        
        # 发送停止信号
        for _ in range(self.max_workers):
            self.task_queue.put(None)
        
        # 关闭线程池
        self.executor.shutdown(wait=True)
        logger.info("任务管理器已关闭")


# 全局任务管理器实例 (无限制并发，实际上限100)
task_manager = PlatformTaskManager(max_workers=100)
