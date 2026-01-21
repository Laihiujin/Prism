"""
定时任务调度器
功能：
1. 定时数据采集
2. 定时账号检查
3. 定时任务清理
4. 支持 Cron 表达式配置
"""
import asyncio
import threading
import schedule
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Callable
import sqlite3

from myUtils.video_collector import collector
from myUtils.cookie_manager import cookie_manager
from myUtils.task_queue_manager import Task, TaskType, TaskQueueManager

class ScheduledTaskService:
    """定时任务服务"""

    def __init__(self, task_manager: TaskQueueManager, db_path: Path):
        self.task_manager = task_manager
        self.db_path = db_path
        self.running = False
        self.scheduler_thread = None

        # 注册任务处理器
        self.task_manager.register_handler(TaskType.DATA_COLLECT, self.handle_data_collect)
        self.task_manager.register_handler(TaskType.ACCOUNT_CHECK, self.handle_account_check)

        # 初始化调度配置数据库
        self.init_schedule_db()

    def init_schedule_db(self):
        """初始化调度配置数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 创建调度配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    task_type TEXT NOT NULL,
                    schedule_type TEXT NOT NULL,  -- daily, hourly, interval, cron
                    schedule_config TEXT,         -- JSON配置
                    enabled INTEGER DEFAULT 1,
                    last_run TIMESTAMP,
                    next_run TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 插入默认调度任务
            default_tasks = [
                ('daily_data_collect', 'data_collect', 'daily', '{"time": "02:00"}'),
                ('hourly_account_check', 'account_check', 'interval', '{"hours": 6}'),
            ]

            for name, task_type, schedule_type, config in default_tasks:
                cursor.execute("""
                    INSERT OR IGNORE INTO scheduled_tasks (name, task_type, schedule_type, schedule_config)
                    VALUES (?, ?, ?, ?)
                """, (name, task_type, schedule_type, config))

            conn.commit()
            print("✅ [Scheduler] 调度配置数据库初始化完成")

    async def handle_data_collect(self, data: Dict) -> Dict:
        """处理数据采集任务"""
        print("📊 [Scheduler] 开始定时数据采集...")

        try:
            # 获取所有有效账号
            accounts = cookie_manager.list_flat_accounts()
            valid_accounts = [acc for acc in accounts if acc.get('status') == 'valid']

            print(f"   发现 {len(valid_accounts)} 个有效账号")

            # 执行采集
            results = await collector.collect_all_accounts()

            print(f"✅ [Scheduler] 数据采集完成")
            print(f"   成功: {results['success']}/{results['total']}")

            return {
                "success": True,
                "total": results['total'],
                "success_count": results['success'],
                "failed_count": results['failed'],
                "details": results['details']
            }

        except Exception as e:
            print(f"❌ [Scheduler] 数据采集失败: {e}")
            raise

    async def handle_account_check(self, data: Dict) -> Dict:
        """处理账号检查任务"""
        print("🔍 [Scheduler] 开始定时账号检查...")

        try:
            accounts = cookie_manager.list_flat_accounts()
            checked = 0
            valid = 0
            invalid = 0

            for account in accounts:
                if account.get('cookie_file'):
                    # 检查Cookie有效性
                    is_valid = await cookie_manager.check_account_validity(
                        account['platform'],
                        account['cookie_file']
                    )

                    checked += 1
                    if is_valid:
                        valid += 1
                    else:
                        invalid += 1
                        # 更新账号状态
                        cookie_manager.update_account_status(
                            account['account_id'],
                            'expired'
                        )

            print(f"✅ [Scheduler] 账号检查完成")
            print(f"   检查: {checked}, 有效: {valid}, 失效: {invalid}")

            return {
                "success": True,
                "checked": checked,
                "valid": valid,
                "invalid": invalid
            }

        except Exception as e:
            print(f"❌ [Scheduler] 账号检查失败: {e}")
            raise

    def add_scheduled_task(self, task_type: TaskType, schedule_func: Callable):
        """添加定时任务到调度器"""
        def job():
            """创建并提交任务到队列"""
            task_id = f"{task_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            task = Task(
                task_id=task_id,
                task_type=task_type,
                data={},
                priority=3,  # 定时任务优先级较高
                max_retries=2
            )
            self.task_manager.add_task(task)

        schedule_func(job)

    def setup_default_schedules(self):
        """设置默认调度"""
        # 每天凌晨2点采集数据
        self.add_scheduled_task(
            TaskType.DATA_COLLECT,
            lambda job: schedule.every().day.at("02:00").do(job)
        )

        # 每6小时检查账号状态
        self.add_scheduled_task(
            TaskType.ACCOUNT_CHECK,
            lambda job: schedule.every(6).hours.do(job)
        )

        print("✅ [Scheduler] 默认调度任务已设置")
        print("   - 每天 02:00 采集数据")
        print("   - 每 6 小时检查账号")

    def start(self):
        """启动调度器"""
        if self.running:
            print("⚠️ [Scheduler] 调度器已在运行")
            return

        self.running = True
        print("🚀 [Scheduler] 启动定时任务调度器...")

        # 设置调度
        self.setup_default_schedules()

        # 启动调度线程
        def run_scheduler():
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次

        self.scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()

        print("✅ [Scheduler] 调度器已启动")

    def stop(self):
        """停止调度器"""
        print("🛑 [Scheduler] 停止调度器...")
        self.running = False

        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)

        schedule.clear()
        print("✅ [Scheduler] 调度器已停止")

    def trigger_task_now(self, task_type: TaskType) -> str:
        """立即触发任务"""
        task_id = f"{task_type.value}_manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        task = Task(
            task_id=task_id,
            task_type=task_type,
            data={},
            priority=1,  # 手动触发的优先级最高
            max_retries=2
        )
        self.task_manager.add_task(task)

        print(f"✅ [Scheduler] 手动触发任务: {task_id}")
        return task_id

    def get_next_schedules(self) -> List[Dict]:
        """获取下次执行时间"""
        jobs = schedule.get_jobs()
        schedules = []

        for job in jobs:
            schedules.append({
                "job": str(job.job_func),
                "next_run": job.next_run.isoformat() if job.next_run else None,
                "interval": str(job.interval) if hasattr(job, 'interval') else None,
                "unit": job.unit if hasattr(job, 'unit') else None
            })

        return schedules

# 全局实例
_scheduled_task_service_instance = None

def get_scheduled_task_service(task_manager: TaskQueueManager = None, db_path: Path = None):
    """获取定时任务服务实例"""
    global _scheduled_task_service_instance
    if _scheduled_task_service_instance is None:
        if task_manager is None or db_path is None:
            raise ValueError("首次调用必须提供 task_manager 和 db_path")
        _scheduled_task_service_instance = ScheduledTaskService(task_manager, db_path)
    return _scheduled_task_service_instance
