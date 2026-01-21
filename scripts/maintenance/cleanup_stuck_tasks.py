"""
Cleanup stuck running tasks in task queue
- Identifies tasks stuck in 'running' status
- Force terminates old running tasks
- Provides safe cleanup with backup
"""
import sys
from pathlib import Path
import sqlite3
from datetime import datetime, timedelta
import shutil

# Add project path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "syn_backend"))

from loguru import logger


def cleanup_stuck_tasks(dry_run=False, max_age_hours=1):
    """
    Clean up stuck running tasks

    Args:
        dry_run: If True, only show what would be done
        max_age_hours: Tasks running longer than this are considered stuck
    """
    logger.info("=" * 60)
    logger.info("Cleanup Stuck Running Tasks")
    logger.info("=" * 60)
    logger.info("")

    # Database path
    db_path = Path(__file__).parent.parent.parent / "syn_backend" / "db" / "task_queue.db"

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return False

    # Backup database first
    if not dry_run:
        backup_path = db_path.parent / f"task_queue_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy(db_path, backup_path)
        logger.info(f"Database backed up to: {backup_path}")
        logger.info("")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all running tasks
        cursor.execute("""
            SELECT task_id, task_type, started_at, updated_at, retry_count, data
            FROM task_queue
            WHERE status = 'running'
            ORDER BY started_at
        """)

        running_tasks = cursor.fetchall()

        if not running_tasks:
            logger.info("[OK] No running tasks found")
            return True

        logger.info(f"Found {len(running_tasks)} running tasks:")
        logger.info("")

        # Analyze tasks
        stuck_tasks = []
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

        for task in running_tasks:
            task_id = task['task_id']
            task_type = task['task_type']
            started_at = task['started_at']
            updated_at = task['updated_at']
            retry_count = task['retry_count']

            # Parse datetime (handle both ISO and sqlite formats)
            try:
                if 'T' in started_at:
                    start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                else:
                    start_time = datetime.strptime(started_at, '%Y-%m-%d %H:%M:%S')
            except:
                start_time = datetime.min

            is_stuck = start_time < cutoff_time
            age_hours = (datetime.now() - start_time).total_seconds() / 3600

            status_icon = "[STUCK]" if is_stuck else "[OK]"
            logger.info(f"{status_icon} {task_id[:40]}...")
            logger.info(f"    Type: {task_type}")
            logger.info(f"    Started: {started_at}")
            logger.info(f"    Age: {age_hours:.1f} hours")
            logger.info(f"    Retries: {retry_count}")
            logger.info("")

            if is_stuck:
                stuck_tasks.append(task_id)

        if not stuck_tasks:
            logger.info("[OK] No stuck tasks (all running < {} hours)".format(max_age_hours))
            return True

        logger.info("=" * 60)
        logger.info(f"Found {len(stuck_tasks)} stuck tasks (running > {max_age_hours}h)")
        logger.info("=" * 60)
        logger.info("")

        if dry_run:
            logger.info("[DRY RUN] Would cancel these tasks:")
            for task_id in stuck_tasks:
                logger.info(f"  - {task_id[:40]}...")
            logger.info("")
            logger.info("Run with dry_run=False to actually cancel")
            return True

        # Cancel stuck tasks
        logger.info("Cancelling stuck tasks...")
        logger.info("")

        for task_id in stuck_tasks:
            cursor.execute("""
                UPDATE task_queue
                SET status = 'failed',
                    error_message = 'Force terminated - stuck in running status',
                    completed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE task_id = ?
            """, (task_id,))
            logger.info(f"[CANCELLED] {task_id[:40]}...")

        conn.commit()

        logger.info("")
        logger.info("=" * 60)
        logger.info("[SUCCESS] Cleanup completed!")
        logger.info("=" * 60)
        logger.info(f"Cancelled: {len(stuck_tasks)} stuck tasks")
        logger.info(f"Backup: {backup_path if not dry_run else 'N/A (dry run)'}")
        logger.info("")

        # Show final status
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM task_queue
            GROUP BY status
        """)

        logger.info("Final task counts:")
        for row in cursor.fetchall():
            logger.info(f"  {row['status']:12}: {row['count']:4} tasks")
        logger.info("")

    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Cleanup stuck running tasks')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--max-age', type=int, default=1, help='Max age in hours for running tasks (default: 1)')

    args = parser.parse_args()

    success = cleanup_stuck_tasks(dry_run=args.dry_run, max_age_hours=args.max_age)
    exit(0 if success else 1)
