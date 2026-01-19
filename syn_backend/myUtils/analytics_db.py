"""
Analytics database schema and helper functions
"""
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

try:
    from fastapi_app.core.timezone_utils import now_beijing_naive
except ImportError:
    # Fallback for standalone usage
    def now_beijing_naive():
        return datetime.now()

def ensure_analytics_schema(db_path: Path):
    """Create analytics tables if they don't exist"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Video analytics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS video_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                account_id INTEGER,
                platform VARCHAR(20) NOT NULL,
                video_id VARCHAR(100),
                video_url TEXT,
                title VARCHAR(500),
                thumbnail TEXT,
                publish_date DATE,
                play_count INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                collect_count INTEGER DEFAULT 0,
                share_count INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                match_confidence FLOAT,
                raw_data TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(id),
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)
        
        # Analytics history for trend tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analytics_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_analytics_id INTEGER NOT NULL,
                play_count INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                collect_count INTEGER DEFAULT 0,
                share_count INTEGER DEFAULT 0,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_analytics_id) REFERENCES video_analytics(id)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_analytics_platform ON video_analytics(platform)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_analytics_publish_date ON video_analytics(publish_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_history_video_id ON analytics_history(video_analytics_id)")
        
        conn.commit()


def _build_filter_clause(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    platform: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    account_ids: Optional[List[str]] = None,
) -> tuple[str, list]:
    conditions = ["1=1"]
    params = []

    # Platform filter
    search_platforms = []
    if platforms:
        search_platforms.extend(platforms)
    if platform and platform.lower() != "all":
        search_platforms.append(platform)
    
    # Remove duplicates and empty strings
    search_platforms = list(set([p for p in search_platforms if p]))
    
    if search_platforms:
        placeholders = ','.join(['?'] * len(search_platforms))
        conditions.append(f"platform IN ({placeholders})")
        params.extend(search_platforms)

    # Account filter
    if account_ids:
        # Filter out empty strings
        valid_ids = [aid for aid in account_ids if aid]
        if valid_ids:
            placeholders = ','.join(['?'] * len(valid_ids))
            conditions.append(f"account_id IN ({placeholders})")
            params.extend(valid_ids)

    # Date filter
    if start_date:
        conditions.append("publish_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("publish_date <= ?")
        params.append(end_date)

    return "WHERE " + " AND ".join(conditions), params


def get_analytics_summary(
    db_path: Path,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    platform: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    account_ids: Optional[List[str]] = None,
) -> Dict:
    """Get analytics summary statistics"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        where_clause, params = _build_filter_clause(
            start_date, end_date, platform, platforms, account_ids
        )
        
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_videos,
                COALESCE(SUM(play_count), 0) as total_plays,
                COALESCE(SUM(like_count), 0) as total_likes,
                COALESCE(SUM(comment_count), 0) as total_comments,
                COALESCE(SUM(collect_count), 0) as total_collects,
                COALESCE(AVG(play_count), 0) as avg_play_count
            FROM video_analytics
            {where_clause}
        """, params)
        
        row = cursor.fetchone()
        
        return {
            "totalVideos": row[0],
            "totalPlays": row[1],
            "totalLikes": row[2],
            "totalComments": row[3],
            "totalCollects": row[4],
            "avgPlayCount": round(row[5], 2)
        }


def get_analytics_videos(
    db_path: Path,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    platform: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    account_ids: Optional[List[str]] = None,
) -> List[Dict]:
    """Get video analytics data"""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        where_clause, params = _build_filter_clause(
            start_date, end_date, platform, platforms, account_ids
        )
        
        cursor.execute(f"""
            SELECT
                id,
                account_id as accountId,
                video_id as videoId,
                title,
                platform,
                thumbnail,
                video_url as videoUrl,
                publish_date as publishDate,
                play_count as playCount,
                like_count as likeCount,
                comment_count as commentCount,
                collect_count as collectCount,
                share_count as shareCount,
                raw_data as rawData,
                last_updated as lastUpdated
            FROM video_analytics
            {where_clause}
            ORDER BY publish_date DESC
            LIMIT ?
        """, params + [limit])
        
        return [dict(row) for row in cursor.fetchall()]


def get_chart_data(
    db_path: Path,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: int = 7,
    platforms: Optional[List[str]] = None,
    account_ids: Optional[List[str]] = None,
) -> List[Dict]:
    """Get chart data for trend visualization"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Build filter clause
        # Note: we pass None for platform single arg, but pass the lists
        where_clause, params = _build_filter_clause(
            start_date, end_date, None, platforms, account_ids
        )
        
        cursor.execute(f"""
            SELECT 
                publish_date as date,
                SUM(play_count) as playCount,
                SUM(like_count) as likeCount,
                SUM(comment_count) as commentCount,
                SUM(collect_count) as collectCount
            FROM video_analytics
            {where_clause}
            GROUP BY publish_date
            ORDER BY publish_date ASC
        """, params)
        
        rows = cursor.fetchall()
        return [{
            "date": row[0], 
            "playCount": row[1],
            "likeCount": row[2],
            "commentCount": row[3],
            "collectCount": row[4]
        } for row in rows]


def insert_video_analytics(db_path: Path, data: Dict) -> int:
    """Insert new video analytics record"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO video_analytics (
                task_id, account_id, platform, video_id, video_url,
                title, thumbnail, publish_date, play_count, like_count,
                comment_count, collect_count, share_count, match_confidence, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('task_id'),
            data.get('account_id'),
            data['platform'],
            data.get('video_id'),
            data.get('video_url'),
            data.get('title'),
            data.get('thumbnail'),
            data.get('publish_date'),
            data.get('play_count', 0),
            data.get('like_count', 0),
            data.get('comment_count', 0),
            data.get('collect_count', 0),
            data.get('share_count', 0),
            data.get('match_confidence'),
            json.dumps(data.get('raw_data', {}))
        ))
        
        conn.commit()
        return cursor.lastrowid


def update_video_analytics(db_path: Path, video_id: int, data: Dict):
    """Update existing video analytics record"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE video_analytics
            SET play_count = ?,
                like_count = ?,
                comment_count = ?,
                collect_count = ?,
                share_count = ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            data.get('play_count', 0),
            data.get('like_count', 0),
            data.get('comment_count', 0),
            data.get('collect_count', 0),
            data.get('share_count', 0),
            video_id
        ))


def upsert_video_analytics_by_key(db_path: Path, *, platform: str, video_id: str, data: Dict) -> int:
    """
    Insert or update a video_analytics row by (platform, video_id).
    Returns row id.
    """
    platform = (platform or "").lower()
    video_id = str(video_id or "").strip()
    if not platform or not video_id:
        raise ValueError("platform and video_id are required for upsert")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id
            FROM video_analytics
            WHERE platform = ?
              AND video_id = ?
            ORDER BY last_updated DESC
            LIMIT 1
            """,
            (platform, video_id),
        )
        row = cursor.fetchone()

        raw_json = json.dumps(data.get("raw_data", {}))

        if row:
            row_id = int(row["id"])
            cursor.execute(
                """
                UPDATE video_analytics
                SET
                    task_id = COALESCE(?, task_id),
                    account_id = COALESCE(?, account_id),
                    video_url = COALESCE(?, video_url),
                    title = COALESCE(?, title),
                    thumbnail = COALESCE(?, thumbnail),
                    publish_date = COALESCE(?, publish_date),
                    play_count = ?,
                    like_count = ?,
                    comment_count = ?,
                    collect_count = ?,
                    share_count = ?,
                    match_confidence = COALESCE(?, match_confidence),
                    raw_data = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    data.get("task_id"),
                    data.get("account_id"),
                    data.get("video_url"),
                    data.get("title"),
                    data.get("thumbnail"),
                    data.get("publish_date"),
                    data.get("play_count", 0),
                    data.get("like_count", 0),
                    data.get("comment_count", 0),
                    data.get("collect_count", 0),
                    data.get("share_count", 0),
                    data.get("match_confidence"),
                    raw_json,
                    row_id,
                ),
            )
            conn.commit()
            return row_id

        cursor.execute(
            """
            INSERT INTO video_analytics (
                task_id, account_id, platform, video_id, video_url,
                title, thumbnail, publish_date, play_count, like_count,
                comment_count, collect_count, share_count, match_confidence, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.get("task_id"),
                data.get("account_id"),
                platform,
                video_id,
                data.get("video_url"),
                data.get("title"),
                data.get("thumbnail"),
                data.get("publish_date"),
                data.get("play_count", 0),
                data.get("like_count", 0),
                data.get("comment_count", 0),
                data.get("collect_count", 0),
                data.get("share_count", 0),
                data.get("match_confidence"),
                raw_json,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def record_analytics_history(db_path: Path, video_analytics_id: int):
    """Record current analytics state to history for trend tracking"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Get current stats
        cursor.execute("""
            SELECT play_count, like_count, comment_count, collect_count, share_count
            FROM video_analytics
            WHERE id = ?
        """, (video_analytics_id,))
        
        row = cursor.fetchone()
        if row:
            cursor.execute("""
                INSERT INTO analytics_history (
                    video_analytics_id, play_count, like_count, 
                    comment_count, collect_count, share_count
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (video_analytics_id,) + row)
            
            conn.commit()
