"""
Agent服务层 - 脚本管理和执行
"""
import json
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import sqlite3

from .models import SaveScriptRequest, PublishPlan, PublishTask
from ....core.logger import logger
from ....core.config import settings


class AgentService:
    """Agent服务"""

    def __init__(self):
        self.scripts_dir = Path(settings.BASE_DIR) / "storage" / "scripts"
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

        # 初始化脚本数据库
        self.db_path = Path(settings.BASE_DIR) / "db" / "agent_scripts.db"
        self._init_database()

    def _init_database(self):
        """初始化数据库"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scripts (
                    script_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    script_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    plan_name TEXT,
                    description TEXT,
                    generated_by TEXT,
                    created_at TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    status TEXT DEFAULT 'saved'
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS script_executions (
                    execution_id TEXT PRIMARY KEY,
                    script_id TEXT NOT NULL,
                    task_batch_id TEXT,
                    mode TEXT NOT NULL,
                    tasks_created INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    started_at TEXT,
                    completed_at TEXT,
                    result TEXT,
                    FOREIGN KEY (script_id) REFERENCES scripts(script_id)
                )
            """)

            conn.commit()
            logger.info("Agent scripts database initialized")

    async def save_script(self, request: SaveScriptRequest) -> Dict[str, Any]:
        """
        保存AI生成的脚本

        Args:
            request: 保存脚本请求

        Returns:
            {script_id, path}
        """
        try:
            # 生成脚本ID
            script_id = f"scr_{uuid.uuid4().hex[:10]}"

            # 确保文件名有正确的扩展名
            filename = request.filename
            if request.script_type == "json" and not filename.endswith(".json"):
                filename += ".json"
            elif request.script_type == "python" and not filename.endswith(".py"):
                filename += ".py"

            # 保存文件
            file_path = self.scripts_dir / filename
            file_path.write_text(request.content, encoding="utf-8")

            # 保存到数据库
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO scripts
                    (script_id, filename, script_type, content, plan_name, description,
                     generated_by, created_at, file_path, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'saved')
                """, (
                    script_id,
                    filename,
                    request.script_type,
                    request.content,
                    request.meta.plan_name,
                    request.meta.description,
                    request.meta.generated_by,
                    datetime.now().isoformat(),
                    str(file_path.relative_to(settings.BASE_DIR))
                ))
                conn.commit()

            logger.info(f"Script saved: {script_id} -> {filename}")

            return {
                "script_id": script_id,
                "path": f"/scripts/{filename}"
            }

        except Exception as e:
            logger.error(f"Failed to save script: {e}", exc_info=True)
            raise

    async def execute_script(
        self,
        script_id: str,
        mode: str = "execute",
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行脚本

        Args:
            script_id: 脚本ID
            mode: 执行模式(execute/dry-run)
            options: 执行选项

        Returns:
            {task_batch_id, tasks_created, estimated_time}
        """
        try:
            # 从数据库获取脚本
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM scripts WHERE script_id = ?",
                    (script_id,)
                )
                script_row = cursor.fetchone()

                if not script_row:
                    raise ValueError(f"Script not found: {script_id}")

                script = dict(script_row)

            # 解析脚本内容
            if script['script_type'] == 'json':
                plan_data = json.loads(script['content'])
                plan = PublishPlan(**plan_data)
            else:
                # Python脚本需要动态执行(暂不支持)
                raise ValueError("Python scripts execution not yet supported")

            # 生成任务批次ID
            task_batch_id = f"TB{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
            execution_id = f"exec_{uuid.uuid4().hex[:10]}"

            # 记录执行
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO script_executions
                    (execution_id, script_id, task_batch_id, mode, status, started_at)
                    VALUES (?, ?, ?, ?, 'running', ?)
                """, (
                    execution_id,
                    script_id,
                    task_batch_id,
                    mode,
                    datetime.now().isoformat()
                ))
                conn.commit()

            if mode == "dry-run":
                # 仅验证,不实际执行
                tasks_created = await self._validate_plan(plan)
                estimated_time = "0s (dry-run)"
            else:
                # 实际执行
                tasks_created = await self._execute_plan(plan, task_batch_id, options or {})
                estimated_time = self._estimate_time(len(plan.tasks))

            # 更新执行记录
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE script_executions
                    SET tasks_created = ?, status = 'completed', completed_at = ?
                    WHERE execution_id = ?
                """, (
                    tasks_created,
                    datetime.now().isoformat(),
                    execution_id
                ))
                conn.commit()

            logger.info(f"Script executed: {script_id} -> {task_batch_id} ({tasks_created} tasks)")

            return {
                "task_batch_id": task_batch_id,
                "tasks_created": tasks_created,
                "estimated_time": estimated_time
            }

        except Exception as e:
            logger.error(f"Failed to execute script: {e}", exc_info=True)
            # 更新执行记录为失败
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        UPDATE script_executions
                        SET status = 'failed', completed_at = ?, result = ?
                        WHERE execution_id = ?
                    """, (datetime.now().isoformat(), str(e), execution_id))
                    conn.commit()
            except:
                pass
            raise

    async def _validate_plan(self, plan: PublishPlan) -> int:
        """验证发布计划"""
        # TODO: 实现验证逻辑
        # - 检查视频是否存在
        # - 检查账号是否可用
        # - 检查是否有重复发布
        logger.info(f"Validating plan: {plan.plan_name} with {len(plan.tasks)} tasks")
        return len(plan.tasks)

    async def _execute_plan(
        self,
        plan: PublishPlan,
        task_batch_id: str,
        options: Dict[str, Any]
    ) -> int:
        """
        执行发布计划

        将计划中的任务提交到任务队列
        """
        from myUtils.task_queue_manager import TaskQueueManager

        # 获取任务队列管理器
        task_db_path = Path(settings.BASE_DIR) / "db" / "task_queue.db"
        task_manager = TaskQueueManager(db_path=str(task_db_path))

        tasks_created = 0
        priority = options.get('priority', 5)

        for task in plan.tasks:
            try:
                # 构建任务参数
                task_params = {
                    "video_id": task.video_id,
                    "account_id": task.account_id,
                    "platform": task.platform,
                    "title": task.title,
                    "description": task.description,
                    "tags": task.tags,
                    "publish_at": task.publish_at,
                    "delay_range": task.delay_range,
                    "task_batch_id": task_batch_id
                }

                # 提交到任务队列
                task_id = task_manager.add_task(
                    task_type="publish_video",
                    params=task_params,
                    priority=priority
                )

                tasks_created += 1
                logger.debug(f"Created task {task_id} for video {task.video_id}")

            except Exception as e:
                logger.error(f"Failed to create task for video {task.video_id}: {e}")
                continue

        logger.info(f"Created {tasks_created}/{len(plan.tasks)} tasks for batch {task_batch_id}")
        return tasks_created

    def _estimate_time(self, task_count: int) -> str:
        """估算执行时间"""
        # 假设每个任务平均30秒
        total_seconds = task_count * 30

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m{seconds}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h{minutes}m"

    async def get_system_context(self) -> Dict[str, Any]:
        """
        获取系统上下文(供AI使用)

        Returns:
            {accounts: [...], videos: [...]}
        """
        try:
            from myUtils.cookie_manager import cookie_manager

            # 获取账号列表
            accounts_raw = cookie_manager.list_flat_accounts()
            accounts = []

            for acc in accounts_raw:
                if acc.get('status') == 'valid':  # 只返回有效账号
                    accounts.append({
                        "id": acc['account_id'],
                        "platform": acc['platform'],
                        "status": acc['status'],
                        "used_videos": [],  # TODO: 从发布历史获取
                        "tags": []  # TODO: 从账号元数据获取
                    })

            # 获取视频列表
            # TODO: 从文件管理系统获取
            videos = await self._get_videos_context()

            return {
                "accounts": accounts,
                "videos": videos
            }

        except Exception as e:
            logger.error(f"Failed to get system context: {e}", exc_info=True)
            return {"accounts": [], "videos": []}

    async def _get_videos_context(self) -> List[Dict[str, Any]]:
        """获取视频上下文"""
        # TODO: 实现从文件管理API获取视频列表
        # 暂时返回空列表
        return []


# 全局服务实例
agent_service = AgentService()
