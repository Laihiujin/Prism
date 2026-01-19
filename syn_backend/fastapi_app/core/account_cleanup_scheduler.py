"""
账号数据定时清理调度器
每6小时自动清理一次，确保账号数据一致性
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.cleanup_account_data import cleanup_all_account_data

logger = logging.getLogger(__name__)


class AccountCleanupScheduler:
    """账号数据清理调度器"""

    def __init__(self, interval_hours: int = 6):
        """
        初始化调度器

        Args:
            interval_hours: 清理间隔（小时），默认6小时
        """
        self.interval_hours = interval_hours
        self.interval_seconds = interval_hours * 3600
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_cleanup_time: Optional[datetime] = None

    async def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("账号清理调度器已在运行中")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_scheduler())
        logger.info(f"账号清理调度器已启动，清理间隔: {self.interval_hours}小时")

    async def stop(self):
        """停止调度器"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("账号清理调度器已停止")

    async def _run_scheduler(self):
        """运行调度器主循环"""
        # 启动时立即执行一次清理
        await self._execute_cleanup()

        while self._running:
            try:
                # 等待指定间隔
                await asyncio.sleep(self.interval_seconds)

                # 执行清理
                if self._running:
                    await self._execute_cleanup()

            except asyncio.CancelledError:
                logger.info("调度器任务被取消")
                break
            except Exception as e:
                logger.error(f"调度器运行出错: {e}", exc_info=True)
                # 出错后等待1分钟再继续
                await asyncio.sleep(60)

    async def _execute_cleanup(self):
        """执行清理任务"""
        try:
            logger.info("开始执行定时账号数据清理...")
            start_time = datetime.now()

            # 在线程池中执行清理（避免阻塞事件循环）
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                cleanup_all_account_data,
                False  # dry_run=False
            )

            self._last_cleanup_time = datetime.now()
            duration = (self._last_cleanup_time - start_time).total_seconds()

            # 统计清理结果
            total_deleted = sum(s.get('deleted', 0) for s in results.values())
            total_kept = sum(s.get('kept', 0) for s in results.values())

            logger.info(
                f"定时清理完成 - 耗时: {duration:.2f}秒, "
                f"保留: {total_kept}项, 删除: {total_deleted}项"
            )

            # 计算下次清理时间
            next_cleanup = self._last_cleanup_time + timedelta(hours=self.interval_hours)
            logger.info(f"下次清理时间: {next_cleanup.strftime('%Y-%m-%d %H:%M:%S')}")

        except Exception as e:
            logger.error(f"执行清理任务失败: {e}", exc_info=True)

    async def trigger_manual_cleanup(self) -> dict:
        """
        手动触发清理

        Returns:
            dict: 清理结果
        """
        logger.info("手动触发账号数据清理...")
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                cleanup_all_account_data,
                False
            )

            self._last_cleanup_time = datetime.now()

            return {
                'success': True,
                'timestamp': self._last_cleanup_time.isoformat(),
                'results': results
            }

        except Exception as e:
            logger.error(f"手动清理失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def get_status(self) -> dict:
        """
        获取调度器状态

        Returns:
            dict: 状态信息
        """
        next_cleanup = None
        if self._last_cleanup_time:
            next_cleanup = self._last_cleanup_time + timedelta(hours=self.interval_hours)

        return {
            'running': self._running,
            'interval_hours': self.interval_hours,
            'last_cleanup': self._last_cleanup_time.isoformat() if self._last_cleanup_time else None,
            'next_cleanup': next_cleanup.isoformat() if next_cleanup else None
        }


# 全局调度器实例
_scheduler: Optional[AccountCleanupScheduler] = None


def get_scheduler() -> AccountCleanupScheduler:
    """获取全局调度器实例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = AccountCleanupScheduler(interval_hours=6)
    return _scheduler


async def start_cleanup_scheduler():
    """启动清理调度器"""
    scheduler = get_scheduler()
    await scheduler.start()


async def stop_cleanup_scheduler():
    """停止清理调度器"""
    scheduler = get_scheduler()
    await scheduler.stop()


if __name__ == "__main__":
    # 测试调度器
    async def test():
        scheduler = AccountCleanupScheduler(interval_hours=6)
        await scheduler.start()

        # 运行一段时间
        await asyncio.sleep(10)

        # 查看状态
        status = scheduler.get_status()
        print(f"调度器状态: {status}")

        # 停止
        await scheduler.stop()

    asyncio.run(test())
