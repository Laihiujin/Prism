"""
Unified analytics fetcher for all platforms.
Orchestrates data collection from Douyin, Kuaishou, and Xiaohongshu.
"""
import sys
from pathlib import Path
import sqlite3
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.fetch_douyin_analytics import fetch_and_store_analytics as fetch_douyin
from scripts.fetch_kuaishou_analytics import fetch_kuaishou_analytics
from scripts.fetch_xiaohongshu_analytics import fetch_xiaohongshu_analytics


def get_account_info(db_path: Path, account_id: int) -> Dict:
    """Get account information from database"""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, platform, cookie, user_id, nickname
            FROM accounts
            WHERE id = ?
        """, (account_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_task_videos(db_path: Path, task_id: int = None) -> List[Dict]:
    """Get task videos from database"""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if task_id:
            query = """
                SELECT id as task_id, title, publish_date, platform
                FROM tasks
                WHERE id = ?
            """
            cursor.execute(query, (task_id,))
        else:
            query = """
                SELECT id as task_id, title, publish_date, platform
                FROM tasks
                WHERE status = 'published'
                ORDER BY publish_date DESC
                LIMIT 100
            """
            cursor.execute(query)
        
        return [dict(row) for row in cursor.fetchall()]


def fetch_analytics_for_account(db_path: Path, account_id: int, task_id: int = None, headless: bool = True):
    """
    Fetch analytics for a specific account
    
    Args:
        db_path: Path to database
        account_id: Account ID to fetch data for
        task_id: Optional specific task ID, otherwise fetch all published tasks
        headless: Run browsers in headless mode
    """
    # Get account info
    account = get_account_info(db_path, account_id)
    if not account:
        print(f"Account {account_id} not found")
        return
    
    platform = account['platform']
    cookie = account['cookie']
    
    print(f"\n{'='*60}")
    print(f"Fetching analytics for account: {account['nickname']} ({platform})")
    print(f"{'='*60}\n")
    
    # Get task videos
    task_videos = get_task_videos(db_path, task_id)
    if not task_videos:
        print("No task videos found")
        return
    
    print(f"Found {len(task_videos)} task videos to match\n")
    
    # Fetch based on platform
    try:
        if platform == 'douyin':
            fetch_douyin(db_path, account_id, cookie, task_videos)
        elif platform == 'kuaishou':
            fetch_kuaishou_analytics(cookie, task_videos, db_path, account_id, headless)
        elif platform == 'xiaohongshu':
            fetch_xiaohongshu_analytics(cookie, task_videos, db_path, account_id, headless)
        else:
            print(f"Unsupported platform: {platform}")
    except Exception as e:
        print(f"Error fetching analytics: {e}")
        import traceback
        traceback.print_exc()


def fetch_analytics_for_all_accounts(db_path: Path, headless: bool = True):
    """Fetch analytics for all active accounts"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nickname, platform
            FROM accounts
            WHERE status = 'active'
        """)
        accounts = cursor.fetchall()
    
    if not accounts:
        print("No active accounts found")
        return
    
    print(f"\nFound {len(accounts)} active accounts")
    
    for account_id, nickname, platform in accounts:
        print(f"\n{'='*60}")
        print(f"Processing: {nickname} ({platform})")
        print(f"{'='*60}")
        
        try:
            fetch_analytics_for_account(db_path, account_id, headless=headless)
        except Exception as e:
            print(f"Error processing account {account_id}: {e}")
            continue


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Fetch video analytics from all platforms")
    parser.add_argument('--db', type=str, default='syn_backend/db/database.db', help='Database path')
    parser.add_argument('--account', type=int, help='Specific account ID to fetch')
    parser.add_argument('--task', type=int, help='Specific task ID to fetch')
    parser.add_argument('--all', action='store_true', help='Fetch for all active accounts')
    parser.add_argument('--headless', action='store_true', default=True, help='Run browsers in headless mode')
    parser.add_argument('--show-browser', action='store_true', help='Show browser window (disable headless)')
    
    args = parser.parse_args()
    
    # Get database path
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)
    
    headless = args.headless and not args.show_browser
    
    if args.all:
        fetch_analytics_for_all_accounts(db_path, headless)
    elif args.account:
        fetch_analytics_for_account(db_path, args.account, args.task, headless)
    else:
        print("Please specify --account <id> or --all")
        print("\nExamples:")
        print("  python fetch_all_analytics.py --account 1")
        print("  python fetch_all_analytics.py --account 1 --task 5")
        print("  python fetch_all_analytics.py --all")
        print("  python fetch_all_analytics.py --account 1 --show-browser")
