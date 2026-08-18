"""
Fetch video analytics data from Douyin (抖音) platform
Uses the API endpoint to get video statistics
"""
import requests
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
from difflib import SequenceMatcher

# API endpoint for fetching Douyin video data
DOUYIN_API_URL = "http://42.194.193.186:8000/api/douyin/web/fetch_one_video"


def calculate_similarity(str1: str, str2: str) -> float:
    """Calculate similarity between two strings"""
    return SequenceMatcher(None, str1, str2).ratio()


def fetch_douyin_video_data(aweme_id: str) -> Optional[Dict]:
    """
    Fetch video data from Douyin API
    
    Args:
        aweme_id: Douyin video ID
        
    Returns:
        Dictionary with video statistics or None if failed
    """
    try:
        response = requests.get(DOUYIN_API_URL, params={"aweme_id": aweme_id}, timeout=10)
        data = response.json()
        
        if data.get("code") == 200 and "data" in data:
            aweme_detail = data["data"].get("aweme_detail", {})
            stats = aweme_detail.get("statistics", {})
            author = aweme_detail.get("author", {})
            
            return {
                "video_id": aweme_detail.get("aweme_id"),
                "title": aweme_detail.get("desc", ""),
                "platform": "douyin",
                "author_name": author.get("nickname", ""),
                "author_id": author.get("uid", ""),
                "play_count": stats.get("play_count", 0),
                "like_count": stats.get("digg_count", 0),
                "comment_count": stats.get("comment_count", 0),
                "collect_count": stats.get("collect_count", 0),
                "share_count": stats.get("share_count", 0),
                "create_time": aweme_detail.get("create_time"),
                "video_url": aweme_detail.get("share_url", ""),
                "cover_url": aweme_detail.get("video", {}).get("cover", {}).get("url_list", [None])[0],
                "raw_data": aweme_detail
            }
        return None
    except Exception as e:
        print(f"Error fetching Douyin video {aweme_id}: {e}")
        return None


def get_account_videos_list(account_id: str, cookie: str) -> List[Dict]:
    """
    Get list of videos from a Douyin account
    This is a placeholder - actual implementation would use Douyin API
    
    Args:
        account_id: Douyin account ID
        cookie: Account cookie for authentication
        
    Returns:
        List of video dictionaries with basic info
    """
    # TODO: Implement actual Douyin account video list fetching
    # This would require using the account's cookie to access their creator center
    # and fetch the list of published videos
    
    print(f"TODO: Fetch video list for account {account_id}")
    return []


def match_video_with_task(task_video: Dict, account_videos: List[Dict], threshold: float = 0.95) -> Optional[Dict]:
    """
    Match a task video with account videos based on publish date and title similarity
    
    Args:
        task_video: Video from task pool with expected publish_date and title
        account_videos: List of videos from account
        threshold: Minimum similarity score (0-1)
        
    Returns:
        Matched video dict or None
    """
    task_date = task_video.get("publish_date")
    task_title = task_video.get("title", "")
    
    for video in account_videos:
        # Check publish date match
        video_date = video.get("publish_date")
        if video_date != task_date:
            continue
        
        # Calculate title similarity
        video_title = video.get("title", "")
        similarity = calculate_similarity(task_title, video_title)
        
        if similarity >= threshold:
            video["match_confidence"] = similarity
            return video
    
    return None


def fetch_and_store_analytics(db_path: Path, account_id: int, cookie: str, task_videos: List[Dict]):
    """
    Fetch analytics for all task videos and store in database
    
    Args:
        db_path: Path to SQLite database
        account_id: Account ID in database
        cookie: Account cookie for authentication
        task_videos: List of task videos to match and fetch data for
    """
    from myUtils.analytics_db import insert_video_analytics, update_video_analytics
    
    # Get account's video list
    account_videos = get_account_videos_list(str(account_id), cookie)
    
    matched_count = 0
    fetched_count = 0
    
    for task_video in task_videos:
        # Try to match with account videos
        matched_video = match_video_with_task(task_video, account_videos)
        
        if matched_video:
            matched_count += 1
            aweme_id = matched_video.get("video_id")
            
            if aweme_id:
                # Fetch detailed data from API
                video_data = fetch_douyin_video_data(aweme_id)
                
                if video_data:
                    # Prepare data for database
                    analytics_data = {
                        "task_id": task_video.get("task_id"),
                        "account_id": account_id,
                        "platform": "douyin",
                        "video_id": video_data["video_id"],
                        "video_url": video_data["video_url"],
                        "title": video_data["title"],
                        "thumbnail": video_data["cover_url"],
                        "publish_date": datetime.fromtimestamp(video_data["create_time"]).strftime('%Y-%m-%d'),
                        "play_count": video_data["play_count"],
                        "like_count": video_data["like_count"],
                        "comment_count": video_data["comment_count"],
                        "collect_count": video_data["collect_count"],
                        "share_count": video_data["share_count"],
                        "match_confidence": matched_video.get("match_confidence"),
                        "raw_data": video_data["raw_data"]
                    }
                    
                    # Check if record exists
                    with sqlite3.connect(db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id FROM video_analytics WHERE video_id = ? AND platform = ?",
                            (video_data["video_id"], "douyin")
                        )
                        existing = cursor.fetchone()
                        
                        if existing:
                            # Update existing record
                            update_video_analytics(db_path, existing[0], analytics_data)
                        else:
                            # Insert new record
                            insert_video_analytics(db_path, analytics_data)
                        
                        fetched_count += 1
                        print(f"✓ Fetched data for: {video_data['title'][:50]}...")
    
    print(f"\nSummary:")
    print(f"  Matched: {matched_count}/{len(task_videos)}")
    print(f"  Fetched: {fetched_count}/{len(task_videos)}")
    
    return {"matched": matched_count, "fetched": fetched_count}


if __name__ == "__main__":
    # Example usage
    test_aweme_id = "7372484719365098803"
    
    print(f"Testing Douyin API with video ID: {test_aweme_id}")
    data = fetch_douyin_video_data(test_aweme_id)
    
    if data:
        print("\n✓ Successfully fetched video data:")
        print(f"  Title: {data['title']}")
        print(f"  Author: {data['author_name']}")
        print(f"  Play Count: {data['play_count']:,}")
        print(f"  Like Count: {data['like_count']:,}")
        print(f"  Comment Count: {data['comment_count']:,}")
        print(f"  Collect Count: {data['collect_count']:,}")
    else:
        print("\n✗ Failed to fetch video data")
