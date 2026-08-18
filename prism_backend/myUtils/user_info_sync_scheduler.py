"""
Account status scheduler:
- Randomly checks account status via FastCookieValidator (no info update).
- Periodically cleans duplicated accounts and orphan cookie files.
- Collects Douyin/Bilibili videos every 2 hours (all accounts).
"""
import asyncio
import os
import random
import schedule
import time
import threading
from datetime import datetime
from loguru import logger

from myUtils.cookie_manager import cookie_manager
from myUtils.fast_cookie_validator import FastCookieValidator
from myUtils.profile_manager import cleanup_profiles, cleanup_fingerprints, export_profile_storage_states, ensure_profiles_for_accounts
from myUtils.login_status_checker import login_status_checker


class UserInfoSyncScheduler:
    """Account status scheduler (kept name for compatibility)."""

    def __init__(self):
        self.running = False
        self.scheduler_thread = None
        # 用于动态调度登录状态检查的下次执行时间
        self.next_login_check_minutes = self._random_login_check_interval()

    def _random_login_check_interval(self) -> int:
        """生成随机检查间隔: 3-6小时 (180-360分钟)"""
        return random.randint(180, 360)

    def _sample_size(self, total: int) -> int:
        raw = os.getenv("ACCOUNT_STATUS_SAMPLE_SIZE", "5")
        try:
            size = max(1, int(raw))
        except Exception:
            size = 5
        return min(total, size)

    async def _check_accounts_async(self, accounts):
        validator = FastCookieValidator()
        tasks = []
        for account in accounts:
            tasks.append(
                validator.validate_cookie_fast(
                    account.get("platform"),
                    account_file=account.get("cookie_file"),
                    fallback=False,
                )
            )
        results = await asyncio.gather(*tasks, return_exceptions=True)

        checked = 0
        valid = 0
        expired = 0
        details = []

        for account, result in zip(accounts, results):
            checked += 1
            status = "expired"
            error = None
            elapsed_ms = None
            source = None
            if isinstance(result, Exception):
                error = str(result)
            else:
                status = "valid" if result.get("status") == "valid" else "expired"
                error = result.get("error")
                elapsed_ms = result.get("elapsed_ms")
                source = result.get("source")

            cookie_manager.update_account_status(account.get("platform"), account.get("account_id"), status)
            if status == "valid":
                valid += 1
            else:
                expired += 1

            details.append(
                {
                    "account_id": account.get("account_id"),
                    "platform": account.get("platform"),
                    "status": status,
                    "elapsed_ms": elapsed_ms,
                    "source": source,
                    "error": error,
                }
            )

        return {"checked": checked, "valid": valid, "expired": expired, "details": details}

    async def _collect_platform_videos_async(self, platform: str):
        try:
            import importlib
            analytics_router = importlib.import_module("fastapi_app.api.v1.analytics.router")
        except Exception as exc:
            logger.error(f"[AccountStatus] Failed to import analytics router: {exc}")
            return {"success": 0, "failed": 1, "errors": [{"platform": platform, "error": str(exc)}]}

        if platform == "douyin":
            return await analytics_router._collect_douyin_tiktok_accounts(account_ids=None)
        if platform == "bilibili":
            return await analytics_router._collect_bilibili_accounts(account_ids=None)
        return {"success": 0, "failed": 1, "errors": [{"platform": platform, "error": "unsupported platform"}]}

    def collect_platform_videos(self, platform: str):
        """Collect platform videos for all accounts (douyin/bilibili)."""
        try:
            logger.info(f"[AccountStatus] Start {platform} video collection - {datetime.now().isoformat()}")
            result = asyncio.run(self._collect_platform_videos_async(platform))
            logger.info(f"[AccountStatus] {platform} collection done: {result}")
            return result
        except Exception as e:
            logger.error(f"[AccountStatus] {platform} collection failed: {e}")
            return None

    def check_account_status(self):
        """Randomly check a subset of accounts and update status only."""
        try:
            accounts = cookie_manager.list_flat_accounts()
            if not accounts:
                return {"checked": 0, "valid": 0, "expired": 0, "details": []}
            random.shuffle(accounts)
            sample_size = self._sample_size(len(accounts))
            sample_accounts = accounts[:sample_size]
            logger.info(
                f"[AccountStatus] Start status check ({sample_size}/{len(accounts)}) - {datetime.now().isoformat()}"
            )
            stats = asyncio.run(self._check_accounts_async(sample_accounts))
            logger.info(f"[AccountStatus] Status check done: {stats}")
            return stats
        except Exception as e:
            logger.error(f"[AccountStatus] Status check failed: {e}")
            return None

    def cleanup_accounts(self):
        """Cleanup duplicated accounts and orphan cookie files."""
        try:
            dup_stats = cookie_manager.cleanup_duplicate_accounts()
            orphan_stats = cookie_manager.cleanup_orphan_cookie_files()
            frontend_stats = cookie_manager.prune_accounts_from_snapshot()
            profile_stats = cleanup_profiles()
            ensure_stats = ensure_profiles_for_accounts()
            fp_stats = cleanup_fingerprints()
            stats = {
                "duplicates": dup_stats,
                "orphans": orphan_stats,
                "frontend_prune": frontend_stats,
                "profiles": profile_stats,
                "profiles_ensured": ensure_stats,
                "fingerprints": fp_stats,
            }
            logger.info(f"[AccountStatus] Cleanup done: {stats}")
            return stats
        except Exception as e:
            logger.error(f"[AccountStatus] Cleanup failed: {e}")
            return None

    def export_profile_states(self):
        """Export persistent profiles to storage_state files."""
        try:
            stats = export_profile_storage_states()
            logger.info(f"[AccountStatus] Profile storage_state export done: {stats}")
            return stats
        except Exception as e:
            logger.error(f"[AccountStatus] Profile storage_state export failed: {e}")
            return None

    def check_login_status(self):
        """检查账号登录状态（轮询策略，每次检查5个账号）"""
        try:
            logger.info(f"[LoginStatus] Start login status check - {datetime.now().isoformat()}")
            stats = login_status_checker.check_batch_accounts(batch_size=5)
            logger.info(f"[LoginStatus] Login status check done: {stats}")

            # 执行完毕后，重新安排下次检查时间
            self._reschedule_login_check()

            return stats
        except Exception as e:
            logger.error(f"[LoginStatus] Login status check failed: {e}")
            return None

    def _reschedule_login_check(self):
        """重新安排下次登录状态检查（随机间隔3-6小时）"""
        # 取消当前的登录检查任务
        schedule.clear('login-status-check')

        # 生成新的随机间隔
        interval_minutes = self._random_login_check_interval()
        self.next_login_check_minutes = interval_minutes

        # 安排新的任务
        schedule.every(interval_minutes).minutes.do(self.check_login_status).tag('login-status-check')

        logger.info(f"[LoginStatus] Next check scheduled in {interval_minutes} minutes ({interval_minutes/60:.1f} hours)")

    def setup_schedules(self):
        """Setup scheduled tasks."""
        schedule.every(30).minutes.do(self.check_account_status)
        schedule.every(2).hours.do(lambda: self.collect_platform_videos("douyin"))
        schedule.every(2).hours.do(lambda: self.collect_platform_videos("bilibili"))
        schedule.every(6).hours.do(self.cleanup_accounts)
        schedule.every(6).hours.do(self.export_profile_states)

        # 登录状态检查：首次在随机间隔后执行
        initial_interval = self.next_login_check_minutes
        schedule.every(initial_interval).minutes.do(self.check_login_status).tag('login-status-check')

        logger.info(
            f"[AccountStatus] Scheduled: status check 30m, douyin/bilibili collect 2h, cleanup 6h, export 6h, "
            f"login status check first in {initial_interval}m ({initial_interval/60:.1f}h, then random 3-6h)"
        )

    def start(self):
        """Start scheduler."""
        if self.running:
            logger.warning("[AccountStatus] Scheduler already running")
            return

        self.running = True
        logger.info("[AccountStatus] Starting scheduler...")

        self.setup_schedules()

        def run_scheduler():
            while self.running:
                schedule.run_pending()
                time.sleep(60)

        self.scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()
        logger.info("[AccountStatus] Scheduler started")

    def stop(self):
        """Stop scheduler."""
        logger.info("[AccountStatus] Stopping scheduler...")
        self.running = False

        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)

        schedule.clear()
        logger.info("[AccountStatus] Scheduler stopped")

    def trigger_now(self):
        """Manual trigger status check."""
        logger.info("[AccountStatus] Manual trigger")
        return self.check_account_status()


user_info_sync_scheduler = UserInfoSyncScheduler()


if __name__ == "__main__":
    scheduler = UserInfoSyncScheduler()
    try:
        scheduler.start()
        print("Scheduler started, Ctrl+C to stop...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()
        print("\nStopped.")
