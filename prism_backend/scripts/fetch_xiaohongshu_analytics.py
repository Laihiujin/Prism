"""
Fetch video analytics data from Xiaohongshu (小红书) platform
Uses Selenium to scrape creator center data
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from difflib import SequenceMatcher

# Xiaohongshu creator center URL
XHS_CREATOR_URL = "https://creator.xiaohongshu.com/creator/notes"


def setup_driver(headless: bool = False) -> webdriver.Chrome:
    """Setup Chrome WebDriver with options"""
    options = Options()
    if headless:
        options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Set user agent
    options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        '''
    })
    return driver


def login_with_cookie(driver: webdriver.Chrome, cookie_str: str):
    """Login to Xiaohongshu using cookie string"""
    driver.get(XHS_CREATOR_URL)
    time.sleep(2)
    
    try:
        cookies = json.loads(cookie_str) if isinstance(cookie_str, str) else cookie_str
        if isinstance(cookies, list):
            for cookie in cookies:
                driver.add_cookie(cookie)
        elif isinstance(cookies, dict):
            for name, value in cookies.items():
                driver.add_cookie({'name': name, 'value': value, 'domain': '.xiaohongshu.com'})
        
        driver.refresh()
        time.sleep(3)
        return True
    except Exception as e:
        print(f"Error setting cookies: {e}")
        return False


def fetch_xiaohongshu_video_list(driver: webdriver.Chrome, max_videos: int = 100) -> List[Dict]:
    """
    Fetch video list from Xiaohongshu creator center
    
    Returns:
        List of video dictionaries with basic info
    """
    videos = []
    
    try:
        wait = WebDriverWait(driver, 10)
        
        # Wait for note list to load
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "note-item")))
        
        # Scroll to load more
        last_height = driver.execute_script("return document.body.scrollHeight")
        while len(videos) < max_videos:
            note_elements = driver.find_elements(By.CLASS_NAME, "note-item")
            
            for element in note_elements[len(videos):]:
                try:
                    # Check if it's a video note
                    note_type = element.find_element(By.CLASS_NAME, "note-type").text
                    if "视频" not in note_type:
                        continue
                    
                    # Extract data
                    title = element.find_element(By.CLASS_NAME, "note-title").text
                    note_id = element.get_attribute("data-note-id")
                    
                    # Get publish date
                    date_text = element.find_element(By.CLASS_NAME, "publish-time").text
                    
                    # Get stats
                    stats_element = element.find_element(By.CLASS_NAME, "note-stats")
                    views = stats_element.find_element(By.CLASS_NAME, "view-count").text
                    likes = stats_element.find_element(By.CLASS_NAME, "like-count").text
                    comments = stats_element.find_element(By.CLASS_NAME, "comment-count").text
                    collects = stats_element.find_element(By.CLASS_NAME, "collect-count").text
                    
                    videos.append({
                        "video_id": note_id,
                        "title": title,
                        "publish_date": date_text,
                        "play_count": int(views.replace(',', '').replace('w', '0000')),
                        "like_count": int(likes.replace(',', '').replace('w', '0000')),
                        "comment_count": int(comments.replace(',', '').replace('w', '0000')),
                        "collect_count": int(collects.replace(',', '').replace('w', '0000')),
                        "platform": "xiaohongshu"
                    })
                except (NoSuchElementException, ValueError) as e:
                    continue
            
            # Scroll down
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
    except TimeoutException:
        print("Timeout waiting for note list")
    except Exception as e:
        print(f"Error fetching video list: {e}")
    
    return videos[:max_videos]


def fetch_xiaohongshu_video_detail(driver: webdriver.Chrome, note_id: str) -> Optional[Dict]:
    """
    Fetch detailed analytics for a specific video note
    
    Args:
        driver: Selenium WebDriver
        note_id: Xiaohongshu note ID
        
    Returns:
        Dictionary with detailed video analytics
    """
    try:
        # Navigate to note detail/analytics page
        detail_url = f"https://creator.xiaohongshu.com/creator/notes/{note_id}/data"
        driver.get(detail_url)
        
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "data-panel")))
        
        data = {
            "video_id": note_id,
            "platform": "xiaohongshu",
        }
        
        # Extract detailed stats
        stat_cards = driver.find_elements(By.CLASS_NAME, "stat-card")
        for card in stat_cards:
            label = card.find_element(By.CLASS_NAME, "stat-label").text
            value = card.find_element(By.CLASS_NAME, "stat-value").text
            
            value_int = int(value.replace(',', '').replace('w', '0000'))
            
            if "曝光" in label or "浏览" in label:
                data["play_count"] = value_int
            elif "点赞" in label:
                data["like_count"] = value_int
            elif "评论" in label:
                data["comment_count"] = value_int
            elif "收藏" in label:
                data["collect_count"] = value_int
            elif "分享" in label:
                data["share_count"] = value_int
        
        return data
    except Exception as e:
        print(f"Error fetching video detail: {e}")
        return None


def fetch_xiaohongshu_analytics(cookie_str: str, task_videos: List[Dict], db_path: Path, account_id: int, headless: bool = False):
    """
    Main function to fetch Xiaohongshu analytics
    
    Args:
        cookie_str: Cookie string for authentication
        task_videos: List of task videos to match
        db_path: Database path
        account_id: Account ID
        headless: Run browser in headless mode
    """
    from myUtils.analytics_db import insert_video_analytics, update_video_analytics
    import sqlite3
    
    driver = setup_driver(headless)
    
    try:
        if not login_with_cookie(driver, cookie_str):
            print("Failed to login with cookie")
            return
        
        print("Fetching video list...")
        account_videos = fetch_xiaohongshu_video_list(driver)
        print(f"Found {len(account_videos)} videos")
        
        matched_count = 0
        fetched_count = 0
        
        for task_video in task_videos:
            matched = None
            task_date = task_video.get("publish_date")
            task_title = task_video.get("title", "")
            
            for video in account_videos:
                if video["publish_date"] == task_date:
                    similarity = SequenceMatcher(None, task_title, video["title"]).ratio()
                    if similarity >= 0.95:
                        matched = video
                        matched["match_confidence"] = similarity
                        break
            
            if matched:
                matched_count += 1
                
                detail_data = fetch_xiaohongshu_video_detail(driver, matched["video_id"])
                
                if detail_data:
                    analytics_data = {
                        "task_id": task_video.get("task_id"),
                        "account_id": account_id,
                        "platform": "xiaohongshu",
                        "video_id": detail_data["video_id"],
                        "title": matched["title"],
                        "publish_date": matched["publish_date"],
                        "play_count": detail_data.get("play_count", 0),
                        "like_count": detail_data.get("like_count", 0),
                        "comment_count": detail_data.get("comment_count", 0),
                        "collect_count": detail_data.get("collect_count", 0),
                        "share_count": detail_data.get("share_count", 0),
                        "match_confidence": matched["match_confidence"],
                        "raw_data": detail_data
                    }
                    
                    with sqlite3.connect(db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id FROM video_analytics WHERE video_id = ? AND platform = ?",
                            (detail_data["video_id"], "xiaohongshu")
                        )
                        existing = cursor.fetchone()
                        
                        if existing:
                            update_video_analytics(db_path, existing[0], analytics_data)
                        else:
                            insert_video_analytics(db_path, analytics_data)
                        
                        fetched_count += 1
                        print(f"✓ Fetched: {matched['title'][:50]}...")
        
        print(f"\nSummary:")
        print(f"  Matched: {matched_count}/{len(task_videos)}")
        print(f"  Fetched: {fetched_count}/{len(task_videos)}")
        
    finally:
        driver.quit()


if __name__ == "__main__":
    print("Xiaohongshu Analytics Scraper")
    print("This script requires valid cookie for authentication")
    print("\nNote: CSS selectors need to be updated based on Xiaohongshu's current HTML structure")
