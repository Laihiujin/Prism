"""
Video data auto-collection system.
Collects full video lists for supported platforms using saved cookies.
"""
import sys
import asyncio

# 修复 Windows 下 Playwright 的 NotImplementedError
# Playwright 需要 ProactorEventLoop 来创建子进程
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
import sqlite3
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from playwright.async_api import Page, async_playwright, TimeoutError as PlaywrightTimeoutError
from loguru import logger
from contextlib import asynccontextmanager

# Always define BASE_DIR first
BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from fastapi_app.core.config import settings
    DB_PATH = Path(settings.DATABASE_PATH)
    from config.conf import PLAYWRIGHT_HEADLESS
    from fastapi_app.core.timezone_utils import now_beijing_naive
except ImportError:
    DB_PATH = BASE_DIR / os.getenv("DB_PATH_REL", "db/database.db")
    PLAYWRIGHT_HEADLESS = True  # Default to headless if config missing
    # Fallback timezone helper
    from datetime import datetime as dt
    def now_beijing_naive():
        return dt.now()

from myUtils.analytics_db import ensure_analytics_schema, upsert_video_analytics_by_key
from myUtils.functional_route_manager import functional_route_manager
from myUtils.cookie_manager import cookie_manager
from myUtils.tikhub_client import get_tikhub_client, TikHubClient

WAIT_TIMEOUT = int(os.getenv("COLLECT_WAIT_MS", "45000"))
HEADLESS = PLAYWRIGHT_HEADLESS
TIKHUB_MAX_PAGES = int(os.getenv("TIKHUB_MAX_PAGES", "5"))
DEFAULT_UA = os.getenv(
    "PLAYWRIGHT_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36",
)


class VideoDataCollector:
    def __init__(self):
        self.init_database()

    def _build_launch_args(self) -> Dict[str, Any]:
        """Build Playwright launch args with optional local Chrome path."""
        args: Dict[str, Any] = {
            "headless": HEADLESS,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        try:
            from config.conf import LOCAL_CHROME_PATH
            if LOCAL_CHROME_PATH:
                args["executable_path"] = str(LOCAL_CHROME_PATH)
        except Exception:
            pass
        return args

    def _resolve_cookie_path(self, cookie_file: str) -> Path:
        """Resolve cookie path from filename, relative path, or absolute path."""
        if not cookie_file:
            return cookie_manager._resolve_cookie_path("")
        return cookie_manager._resolve_cookie_path(cookie_file)

    def init_database(self):
        """Ensure the analytics table exists and has current schema."""
        db_str = str(DB_PATH)
        try:
            with sqlite3.connect(db_str) as conn:
                cursor = conn.cursor()
                
                # 1. Create table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS video_analytics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        account_id TEXT NOT NULL,
                        platform TEXT NOT NULL,
                        video_id TEXT NOT NULL,
                        title TEXT,
                        cover_url TEXT,
                        publish_time TEXT,
                        duration INTEGER,
                        play_count INTEGER DEFAULT 0,
                        like_count INTEGER DEFAULT 0,
                        comment_count INTEGER DEFAULT 0,
                        share_count INTEGER DEFAULT 0,
                        collect_count INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'published',
                        collected_at TEXT NOT NULL,
                        UNIQUE(account_id, video_id)
                    )
                    """
                )

                # 2. Add missing columns (migration)
                cursor.execute("PRAGMA table_info(video_analytics)")
                existing_cols = {row[1] for row in cursor.fetchall()}

                def add_col(name, ddl):
                    if name not in existing_cols:
                        cursor.execute(f"ALTER TABLE video_analytics ADD COLUMN {name} {ddl}")

                add_col("cover_url", "TEXT")
                add_col("publish_time", "TEXT")
                add_col("duration", "INTEGER")
                add_col("play_count", "INTEGER DEFAULT 0")
                add_col("like_count", "INTEGER DEFAULT 0")
                add_col("comment_count", "INTEGER DEFAULT 0")
                add_col("share_count", "INTEGER DEFAULT 0")
                add_col("collect_count", "INTEGER DEFAULT 0")
                add_col("completion_rate", "REAL")
                add_col("avg_watch_time", "INTEGER")
                add_col("status", "TEXT DEFAULT 'published'")
                add_col("collected_at", "TEXT")

                # 3. Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_v_a_account ON video_analytics(account_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_v_a_platform ON video_analytics(platform)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_v_a_collected ON video_analytics(collected_at)")
                
                conn.commit()
                print("[Collector] Database initialized (consolidated)")
        except Exception as e:
            logger.error(f"[Collector] Database init failed at {db_str}: {e}")

    async def _recover_id_by_clicking(self, page: Page, item_selector: str, index: int, platform: str) -> Optional[str]:
        """通过点击元素并在详情页提取 ID"""
        try:
            items = await page.query_selector_all(item_selector)
            if index < len(items):
                item = items[index]
                async with page.expect_popup() as popup_info:
                    await item.click()
                detail_page = await popup_info.value
                await detail_page.wait_for_load_state("networkidle")
                url = detail_page.url
                video_id = None
                if platform == "kuaishou":
                    m = re.search(r"photoId=([\w-]+)", url) or re.search(r"short-video/([\w-]+)", url)
                    if m: video_id = m.group(1)
                elif platform == "douyin":
                    m = re.search(r"work-detail/(\d+)", url) or re.search(r"video/(\d+)", url)
                    if m: video_id = m.group(1)
                
                await detail_page.close()
                return video_id
        except Exception as e:
            logger.warning(f"Failed to recover ID by clicking: {e}")
        return None

    def _proximity_match_and_recover(self, account_id: str, platform: str, scraped_video: Dict[str, Any]):
        """
        近似对比与 ID 回收逻辑。
        对比维度：标题、预览图、发布时间、标签。
        """
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                title = scraped_video.get("title", "").strip()
                publish_time_str = scraped_video.get("publish_time", "")
                video_id = scraped_video.get("video_id")
                scraped_tags = scraped_video.get("tags", [])
                
                if not video_id:
                    return

                # 查找匹配的任务 (24小时内或待处理的)
                query = """
                SELECT * FROM publish_tasks 
                WHERE platform = ? AND account_id = ? AND (video_id IS NULL OR video_id = '')
                AND status IN ('pending', 'success', 'publishing')
                ORDER BY created_at DESC LIMIT 50
                """
                cursor.execute(query, (platform, account_id))
                tasks = cursor.fetchall()

                best_match = None
                for task in tasks:
                    task_title = (task["title"] or "").strip()
                    task_tags = json.loads(task["tags"]) if task["tags"] else []
                    
                    # 1. 标题完全匹配或高度相似
                    if title and task_title:
                        if title == task_title or title in task_title or task_title in title:
                            best_match = task
                            break
                    
                    # 2. 标签匹配 (如果有)
                    if scraped_tags and task_tags:
                        overlap = set(scraped_tags) & set(task_tags)
                        if len(overlap) >= 1: # 至少有一个标签相同
                            # 这里可以进一步结合标题或时间
                            if not title or not task_title or (title[:5] == task_title[:5]):
                                best_match = task
                                break

                if best_match:
                    task_id = best_match["task_id"]
                    cursor.execute(
                        "UPDATE publish_tasks SET video_id = ?, status = 'success', published_at = ? WHERE task_id = ?",
                        (video_id, publish_time_str, task_id)
                    )
                    logger.info(f"Recovered video_id {video_id} for platform {platform} matching task {task_id}")
                    conn.commit()
                    
                    # 同时尝试同步到 manual_tasks (如果 task_id 对应)
                    # ...
        except Exception as e:
            logger.error(f"Error in proximity matching: {e}")

    def save_video_data(self, account_id: str, platform: str, video: Dict[str, Any]):
        """Save video data using analytics_db helper and trigger recovery."""
        # ✅ CRITICAL: Validate video_id before saving
        video_id = video.get("video_id")
        if not video_id or not str(video_id).strip():
            logger.warning(f"[Collector] Skipping video without valid ID: {video.get('title', 'NO_TITLE')[:40]}")
            return

        data_to_save = {
            "account_id": account_id,
            "platform": platform,
            "video_id": str(video_id).strip(),
            "title": video.get("title") or "",
            "thumbnail": video.get("cover_url") or "",
            "publish_date": video.get("publish_time") or "",
            "play_count": video.get("play_count") or 0,
            "like_count": video.get("like_count") or 0,
            "comment_count": video.get("comment_count") or 0,
            "share_count": video.get("share_count") or 0,
            "collect_count": video.get("collect_count") or 0,
            "collected_at": now_beijing_naive().isoformat(),
            "raw_data": video
        }

        try:
            upsert_video_analytics_by_key(
                DB_PATH,
                platform=platform,
                video_id=data_to_save["video_id"],
                data=data_to_save
            )
            logger.debug(f"[Collector] Saved {platform} video {data_to_save['video_id']}: {data_to_save['title'][:30] if data_to_save['title'] else 'NO_TITLE'}")
        except Exception as e:
            logger.error(f"[Collector] Error saving to DB: {e}")
            return

        # 触发 ID 回写到后端任务表
        self._proximity_match_and_recover(account_id, platform, video)

    async def collect_douyin_data_api(self, cookie_file: str, account_id: str) -> Dict[str, Any]:
        cookies = self._load_cookie_list(cookie_file)
        if not cookies:
            return {"success": False, "error": "Cookie file not found or invalid"}

        cookie_header = self._cookie_header(cookies, domain_filter="douyin.com") or self._cookie_header(cookies)
        if not cookie_header:
            return {"success": False, "error": "No cookie header available"}

        headers = {
            "User-Agent": DEFAULT_UA,
            "Referer": "https://creator.douyin.com/",
            "Cookie": cookie_header,
        }

        url = "https://creator.douyin.com/web/api/media/aweme/list"
        cursor = 0
        has_more = True
        videos: List[Dict[str, Any]] = []
        rounds = 0

        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            while has_more and rounds < 200:
                rounds += 1
                try:
                    resp = await client.get(url, params={"cursor": cursor, "count": 20, "status": 1})
                except httpx.HTTPError as exc:  # noqa: BLE001
                    return {"success": False, "error": f"Request failed: {exc}"}

                if resp.status_code >= 400:
                    detail = ""
                    try:
                        detail = resp.text
                    except Exception:
                        pass
                    return {"success": False, "error": f"HTTP {resp.status_code}: {detail}"}

                data = resp.json()
                payload = data.get("data") or data
                aweme_list = payload.get("aweme_list") or []
                for item in aweme_list:
                    stats = item.get("statistics", {}) if isinstance(item, dict) else {}
                    title = item.get("desc") or item.get("title") or ""
                    cover = None
                    try:
                        cover = item.get("video", {}).get("cover", {}).get("url_list", [None])[0]
                    except Exception:
                        cover = None
                    videos.append(
                        {
                            "video_id": item.get("aweme_id") or "",
                            "title": title,
                            "cover_url": cover,
                            "play_count": stats.get("play_count") or stats.get("play_count_v2") or 0,  # ✅ Standardized
                            "like_count": stats.get("digg_count") or 0,  # ✅ Standardized
                            "comment_count": stats.get("comment_count") or 0,  # ✅ Standardized
                            "share_count": stats.get("share_count") or 0,  # ✅ Standardized
                            "publish_time": item.get("create_time"),
                        }
                    )

                has_more_raw = payload.get("has_more")
                has_more = has_more_raw in (1, "1", True)
                cursor = payload.get("cursor", cursor + 20)

        saved_count = 0
        for video in videos:
            if video.get("video_id"):
                self.save_video_data(account_id, "douyin", video)
                saved_count += 1

        return {"success": True, "count": saved_count, "videos": videos}

    def _load_cookie_list(self, cookie_file: str) -> List[Dict[str, Any]]:
        """Load cookies from playwright storage or raw list."""
        path = self._resolve_cookie_path(cookie_file)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

        cookies: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            if isinstance(data.get("cookies"), list):
                cookies = data.get("cookies", [])
            elif isinstance(data.get("origins"), list):
                for origin in data.get("origins", []):
                    cookies.extend(origin.get("cookies", []))
        elif isinstance(data, list):
            cookies = data
        return cookies

    def _cookie_header(self, cookies: List[Dict[str, Any]], domain_filter: Optional[str] = None) -> str:
        """Build Cookie header string from cookie list."""
        pairs = []
        for c in cookies:
            if not c or "name" not in c or "value" not in c:
                continue
            if domain_filter and domain_filter not in (c.get("domain") or ""):
                continue
            pairs.append(f"{c['name']}={c['value']}")
        return "; ".join(pairs)

    async def collect_kuaishou_data_tikhub(
        self,
        account: Dict[str, Any],
        client: TikHubClient,
        max_pages: int,
    ) -> Dict[str, Any]:
        user_id = (account.get("user_id") or "").strip()
        if not user_id:
            return {"success": False, "error": "TikHub requires Kuaishou user_id (eid) in account.user_id"}
        if user_id.isdigit():
            return {"success": False, "error": "TikHub requires Kuaishou eid (non-numeric). Update account.user_id"}

        videos, pages = await client.collect_kuaishou_posts(user_id=user_id, max_pages=max_pages)
        saved_count = 0
        for video in videos:
            if video.get("video_id"):
                self.save_video_data(account["account_id"], "kuaishou", video)
                saved_count += 1

        return {
            "success": saved_count > 0,
            "count": saved_count,
            "videos": videos,
            "pages": pages,
            "source": "tikhub",
        }

    async def collect_xiaohongshu_data_tikhub(
        self,
        account: Dict[str, Any],
        client: TikHubClient,
        max_pages: int,
    ) -> Dict[str, Any]:
        user_id = (account.get("user_id") or "").strip()
        if not user_id:
            return {"success": False, "error": "TikHub requires Xiaohongshu user_id in account.user_id"}

        videos, pages = await client.collect_xiaohongshu_notes(user_id=user_id, max_pages=max_pages)
        saved_count = 0
        for video in videos:
            if video.get("video_id"):
                self.save_video_data(account["account_id"], "xiaohongshu", video)
                saved_count += 1

        return {
            "success": saved_count > 0,
            "count": saved_count,
            "videos": videos,
            "pages": pages,
            "source": "tikhub",
        }

    async def collect_channels_data_tikhub(
        self,
        account: Dict[str, Any],
        client: TikHubClient,
        max_pages: int,
    ) -> Dict[str, Any]:
        username = (account.get("user_id") or account.get("name") or "").strip()
        if not username:
            return {"success": False, "error": "TikHub requires WeChat Channels username in account.user_id"}

        videos, pages = await client.collect_channels_home(username=username, max_pages=max_pages)
        saved_count = 0
        for video in videos:
            if video.get("video_id"):
                self.save_video_data(account["account_id"], "channels", video)
                saved_count += 1

        return {
            "success": saved_count > 0,
            "count": saved_count,
            "videos": videos,
            "pages": pages,
            "source": "tikhub",
        }

    async def _collect_with_scroll(
        self,
        page: Page,
        extract_script: str,
        *,
        scroll_script: Optional[str] = None,
        max_rounds: int = 30,
        wait_ms: int = 800,
    ) -> List[Dict[str, Any]]:
        """
        Repeatedly extract items while scrolling to load more results.
        Stops after two rounds with no new items or hitting max_rounds.
        """
        collected: Dict[str, Dict[str, Any]] = {}
        idle_rounds = 0

        for _ in range(max_rounds):
            try:
                items = await page.evaluate(extract_script)
            except Exception as exc:  # noqa: BLE001
                print(f"[Collector] Extract failed: {exc}")
                break

            if not items:
                items = []

            new_items = 0
            for item in items:
                video_id = item.get("video_id") or item.get("id")
                if video_id and video_id not in collected:
                    collected[video_id] = item
                    new_items += 1

            if new_items == 0:
                idle_rounds += 1
            else:
                idle_rounds = 0

            scroll_js = scroll_script or "window.scrollTo(0, document.body.scrollHeight);"
            try:
                await page.evaluate(scroll_js)
            except Exception:
                pass
            await page.wait_for_timeout(wait_ms)

            if idle_rounds >= 2:
                break

        return list(collected.values())

    async def collect_kuaishou_data(self, cookie_file: str, account_id: str) -> Dict[str, Any]:
        """Collect Kuaishou videos for the given account."""
        print("[Kuaishou] Start collecting data...")

        cookie_path = self._resolve_cookie_path(cookie_file)
        if not cookie_path.exists():
            return {"success": False, "error": "Cookie file not found"}

        async with async_playwright() as p:
            browser = await p.chromium.launch(**self._build_launch_args())
            context = await browser.new_context(
                storage_state=cookie_path,
                user_agent=DEFAULT_UA,
                viewport={"width": 1366, "height": 768},
            )
            page = await context.new_page()

            try:
                await page.goto("https://cp.kuaishou.com/article/manage/video", timeout=30000)
                await page.wait_for_load_state("networkidle")

                if "login" in page.url:
                    return {"success": False, "error": "Login expired"}

                # 执行关闭引导路由
                await functional_route_manager.execute_close_guides(page, "kuaishou")

                await page.wait_for_selector(".video-item", timeout=WAIT_TIMEOUT)

                # 获取视频列表
                videos = await self._collect_with_scroll(
                    page,
                    """
                    () => {
                        const items = document.querySelectorAll('.video-item');
                        return Array.from(items).map((item, index) => {
                            const title = item.querySelector('.video-item__detail__row__title')?.innerText || '';
                            const stats = Array.from(item.querySelectorAll('.video-item__detail__row__label')).map(l => l.innerText);
                            const time = item.querySelector('.video-item__detail__row__time')?.innerText || '';
                            return {
                                index,
                                title,
                                play_count: parseInt(stats[0] || '0'),
                                like_count: parseInt(stats[1] || '0'),
                                comment_count: parseInt(stats[2] || '0'),
                                publish_time: time
                            };
                        });
                    }
                    """,
                )

                # 增强型采集：如果缺少 ID，尝试通过点击回收
                for video in videos:
                    try:
                        # 点击视频卡片以跳转详情页获取 ID
                        selectors = [".video-item", ".video-item__detail__row__title"]
                        # 这里我们简单的通过位置点击
                        items = await page.query_selector_all(".video-item")
                        if video["index"] < len(items):
                            item = items[video["index"]]
                            # 开启新页面监听以防止主页面跳转
                            async with page.expect_popup() as popup_info:
                                await item.click()
                            detail_page = await popup_info.value
                            await detail_page.wait_for_load_state("networkidle")
                            # 从 URL 中提取 ID (e.g., .../detail?photoId=X or .../short-video/X)
                            url = detail_page.url
                            m = re.search(r"photoId=([\w-]+)", url) or re.search(r"short-video/([\w-]+)", url)
                            if m:
                                video["video_id"] = m.group(1)
                                logger.info(f"Successfully recovered photoId: {video['video_id']}")
                            await detail_page.close()
                    except Exception as e:
                        logger.warning(f"Failed to recover ID for video {video.get('title')}: {e}")

                saved_count = 0
                for video in videos:
                    if video.get("video_id"):
                        self.save_video_data(account_id, "kuaishou", video)
                        saved_count += 1

                if saved_count > 0:
                    print(f"[Kuaishou] Collected {saved_count} videos")
                    return {"success": True, "count": saved_count, "videos": videos}
                
                # Fallback to click-to-detail if no IDs found
                print("[Kuaishou] No ids from DOM, trying click-to-detail fallback...")
                click_videos = await self._collect_kuaishou_ids_by_click(page, max_items=30)
                click_saved = 0
                for video in click_videos:
                    if video.get("video_id"):
                        self.save_video_data(account_id, "kuaishou", video)
                        click_saved += 1
                
                if click_saved > 0:
                    return {"success": True, "count": click_saved, "videos": click_videos}

                return {"success": False, "error": "No videos found"}

            except PlaywrightTimeoutError:
                return {"success": False, "error": "Timeout waiting for video list"}
            except Exception as e:  # noqa: BLE001
                print(f"[Kuaishou] Collect failed: {e}")
                return {"success": False, "error": str(e)}
            finally:
                await browser.close()

    async def collect_xiaohongshu_data(self, cookie_file: str, account_id: str) -> Dict[str, Any]:
        """Collect Xiaohongshu videos for the given account."""
        print("[XHS] Start collecting data...")

        cookie_path = self._resolve_cookie_path(cookie_file)
        if not cookie_path.exists():
            return {"success": False, "error": "Cookie file not found"}

        async with async_playwright() as p:
            browser = await p.chromium.launch(**self._build_launch_args())
            context = await browser.new_context(
                storage_state=cookie_path,
                user_agent=DEFAULT_UA,
                viewport={"width": 1366, "height": 768},
            )
            page = await context.new_page()

            try:
                await page.goto("https://creator.xiaohongshu.com/new/note-manager", timeout=WAIT_TIMEOUT)
                await page.wait_for_load_state("networkidle")

                if "login" in page.url:
                    return {"success": False, "error": "Login expired"}

                await page.wait_for_selector(
                    ".note-item, .content-card, .note-card, [data-note-id], [data-id]",
                    timeout=WAIT_TIMEOUT,
                )

                videos = await self._collect_with_scroll(
                    page,
                    """
                    () => {
                        const items = document.querySelectorAll('.note-item, .content-card, .note-card, [data-note-id], [data-id]');
                        return Array.from(items).map(item => {
                            const num = (selector) => {
                                const el = item.querySelector(selector);
                                return el ? parseInt(el.textContent.replace(/[^0-9]/g, '') || '0') : 0;
                            };
                            return {
                                video_id: item.getAttribute('data-note-id') || item.getAttribute('data-id') || '',
                                title: item.querySelector('.title, .note-title, .name')?.textContent.trim() || '',
                                cover_url: item.querySelector('img')?.src || '',
                                play_count: num('.view-count, [class*="view"]'),
                                like_count: num('.like-count, [class*="like"]'),
                                comment_count: num('.comment-count, [class*="comment"]'),
                                collect_count: num('.collect-count, [class*="collect"]'),
                                publish_time: item.querySelector('.publish-time, .time, .date, .time-text')?.textContent.trim() || ''
                            };
                        });
                    }
                    """,
                    max_rounds=40,
                    wait_ms=1200,
                )

                saved_count = 0
                for video in videos:
                    if video.get("video_id"):
                        self.save_video_data(account_id, "xiaohongshu", video)
                        saved_count += 1

                print(f"[XHS] Collected {saved_count} videos")
                return {"success": True, "count": saved_count, "videos": videos}

            except PlaywrightTimeoutError:
                return {"success": False, "error": "Timeout waiting for content list (login expired or layout changed)"}
            except Exception as e:  # noqa: BLE001
                print(f"[XHS] Collect failed: {e}")
                return {"success": False, "error": str(e)}
            finally:
                await browser.close()

    async def collect_douyin_data(self, cookie_file: str, account_id: str) -> Dict[str, Any]:
        """
        Collect Douyin videos for the given account.

        Collection Strategy:
        1. Try API method first (faster, but requires specific headers/cookies)
        2. Fall back to page DOM extraction
        3. Final fallback: click each item to get video_id from detail page URL

        Known Issues:
        - API method fails with "Url doesn't match" (requires additional auth headers)
        - Detail page is SPA-based, title/stats selectors may not match dynamic content
        - Click method only gets video_id reliably, title/stats often empty
        """
        print("[Douyin] Start collecting data...")

        cookie_path = self._resolve_cookie_path(cookie_file)
        if not cookie_path.exists():
            return {"success": False, "error": "Cookie file not found"}

        # Prefer API crawling for speed and stability
        api_result = await self.collect_douyin_data_api(cookie_file, account_id)
        if api_result.get("success") and api_result.get("count", 0) > 0:
            return api_result
        else:
            # success=true but count=0 is a common case; still fallback
            print(f"[Douyin] API collect failed, fallback to page: {api_result.get('error')}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(**self._build_launch_args())
            context = await browser.new_context(
                storage_state=cookie_path,
                user_agent=DEFAULT_UA,
                viewport={"width": 1366, "height": 768},
            )
            page = await context.new_page()

            try:
                await page.goto("https://creator.douyin.com/creator-micro/content/manage", timeout=WAIT_TIMEOUT)
                await page.wait_for_load_state("networkidle")
                await self._close_douyin_popups(page)

                if "login" in page.url or "passport" in page.url:
                    return {"success": False, "error": "Login expired"}

                # 执行关闭引导路由
                await functional_route_manager.execute_close_guides(page, "douyin")

                await page.wait_for_selector(
                    "a[href*='/creator-micro/work-management/work-detail/'], "
                    "div[class*='video-card-info'], "
                    "[data-row-key], [data-id], .semi-table-row",
                    timeout=WAIT_TIMEOUT,
                )

                # 优先使用功能路由抓取 (DY_VIDEO_LIST)
                videos = await functional_route_manager.run_scraper(page, "douyin", "DY_VIDEO_LIST")

                if not videos:
                    # 备选提取逻辑
                    videos = await self._collect_with_scroll(
                        page,
                        """
                        () => {
                            const nodes = document.querySelectorAll('[data-row-key], [data-id], .semi-table-row, [class*="video-card"]');
                            return Array.from(nodes).map(node => {
                                const id = node.getAttribute('data-row-key') || node.getAttribute('data-id') || '';
                                const titleEl = node.querySelector('[class*="title"], .video-title');
                                return {
                                    video_id: id,
                                    title: titleEl ? titleEl.textContent.trim() : '',
                                    play_count: 0, like_count: 0, comment_count: 0
                                };
                            } ).filter(v => v.title);
                        }
                        """
                    )

                saved_count = 0
                for video in videos:
                    if video.get("video_id"):  # ✅ Changed from title to video_id
                        self.save_video_data(account_id, "douyin", video)
                        saved_count += 1

                if saved_count > 0:
                    print(f"[Douyin] Page collect finished: {saved_count} videos")
                    return {"success": True, "count": saved_count, "videos": videos}

                # Fallback: click each video card to navigate to work-detail page and extract ID from URL.
                print("[Douyin] No ids from DOM, trying click-to-detail fallback...")
                click_videos = await self._collect_douyin_ids_by_click(page, max_items=50)
                click_saved = 0
                for video in click_videos:
                    if video.get("video_id"):
                        self.save_video_data(account_id, "douyin", video)
                        click_saved += 1

                if click_saved > 0:
                    print(f"[Douyin] Collected {click_saved} videos (click fallback)")
                    return {"success": True, "count": click_saved, "videos": click_videos}

                return {"success": False, "error": "No work ids found (layout changed?)"}

            except PlaywrightTimeoutError:
                try:
                    await page.screenshot(path=BASE_DIR / "logs" / f"douyin_timeout_{now_beijing_naive().strftime('%Y%m%d_%H%M%S')}.png")
                except Exception:
                    pass
                return {"success": False, "error": "Timeout waiting for video list (login expired or layout changed)"}
            except Exception as e:  # noqa: BLE001
                print(f"[Douyin] Collect failed: {e}")
                try:
                    await page.screenshot(path=BASE_DIR / "logs" / f"douyin_error_{now_beijing_naive().strftime('%Y%m%d_%H%M%S')}.png")
                except Exception:
                    pass
                return {"success": False, "error": str(e)}
            finally:
                await browser.close()

    async def _close_douyin_popups(self, page: Page) -> None:
        """Best-effort close of Douyin newbie popups that block clicks."""
        selectors = [
            "button:has-text('我知道了')",
            "button:has-text('知道了')",
            "button:has-text('跳过')",
            "[role='dialog'] button:has-text('我知道了')",
            "[aria-label='关闭']",
            "[aria-label='close']",
        ]
        for _ in range(6):
            closed = False
            for sel in selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        await page.wait_for_timeout(250)
                        closed = True
                        break
                except Exception:
                    continue
            if not closed:
                return

    async def _collect_douyin_ids_by_click(self, page: Page, max_items: int = 50) -> List[Dict[str, Any]]:
        """
        Extract Douyin work_id by clicking items in content manage list.
        The work detail URL looks like:
          https://creator.douyin.com/creator-micro/work-management/work-detail/<work_id>?...
        """
        manage_url = "https://creator.douyin.com/creator-micro/content/manage"
        work_re = re.compile(r"/creator-micro/work-management/work-detail/(\d+)")

        def parse_work_id(url: str) -> str:
            m = work_re.search(url or "")
            return m.group(1) if m else ""

        # Fast path: if there are links with href, parse directly without navigation.
        ids: List[str] = []
        try:
            link_loc = page.locator("a[href*='/creator-micro/work-management/work-detail/']")
            link_count = await link_loc.count()
            for i in range(min(link_count, max_items)):
                href = await link_loc.nth(i).get_attribute("href")
                work_id = parse_work_id(href or "")
                if work_id:
                    ids.append(work_id)
        except Exception:
            ids = []

        if ids:
            uniq = []
            seen = set()
            for wid in ids:
                if wid in seen:
                    continue
                seen.add(wid)
                uniq.append(wid)
            return [{"video_id": wid, "title": "", "cover_url": ""} for wid in uniq]

        results: List[Dict[str, Any]] = []
        seen_ids = set()

        # UI path: click card info area to open detail page, then parse URL for work_id.
        # User-provided XPath points to `div.video-card-info-*`.
        card_selectors = [
            "div[class*='video-card-info']",
            "div[class*='video-card-content'] div[class*='video-card-info']",
            ".video-card-info-aglKIQ",
        ]

        cards = None
        for sel in card_selectors:
            loc = page.locator(sel)
            try:
                if await loc.count() > 0:
                    cards = loc
                    break
            except Exception:
                continue

        if cards is None:
            return []

        count = await cards.count()
        for idx in range(min(count, max_items)):
            detail_page = page
            try:
                await self._close_douyin_popups(page)
                item = cards.nth(idx)
                await item.scroll_into_view_if_needed()
                # Some layouts open detail in a new tab; handle both.
                try:
                    async with page.expect_popup(timeout=1500) as popup_info:
                        await item.click()
                    detail_page = await popup_info.value
                except PlaywrightTimeoutError:
                    await item.click()

                # Poll URL until it becomes a work-detail page.
                work_id = ""
                for _ in range(20):  # ~10s
                    work_id = parse_work_id(detail_page.url)
                    if work_id:
                        break
                    await detail_page.wait_for_timeout(500)

                if work_id and work_id not in seen_ids:
                    seen_ids.add(work_id)
                    # Try scraping stats on detail page
                    stats = {"video_id": work_id, "title": "", "cover_url": "", "play_count": 0, "like_count": 0, "comment_count": 0, "share_count": 0}  # ✅ Standardized
                    try:
                        # Wait for page to stabilize
                        await detail_page.wait_for_load_state("domcontentloaded", timeout=5000)

                        # Try multiple selectors for title
                        title_selectors = [
                            "textarea[placeholder*='添加标题']",  # 编辑框
                            "input[placeholder*='标题']",
                            ".title-input",
                            "[class*='title-input']",
                            "h1",
                            ".video-title",
                            "[class*='video-title']",
                            "[class*='work-title']"
                        ]

                        for sel in title_selectors:
                            try:
                                title_loc = detail_page.locator(sel).first
                                if await title_loc.count() > 0:
                                    title_text = await title_loc.input_value() if 'textarea' in sel or 'input' in sel else await title_loc.inner_text()
                                    if title_text and title_text.strip():
                                        stats["title"] = title_text.strip()
                                        break
                            except: continue

                        # Try multiple selectors for stats
                        stat_selectors = [
                            "[class*='data-card']",
                            "[class*='work-data']",
                            "[class*='data-item']",
                            ".data-list",
                            "[class*='stat']"
                        ]

                        data_items = []
                        for sel in stat_selectors:
                            try:
                                items = await detail_page.locator(sel).all()
                                if items:
                                    data_items = items
                                    break
                            except: continue

                        for item in data_items:
                            try:
                                text = await item.inner_text()
                                # 提取数字 (支持万、亿等单位)
                                val = 0
                                if '万' in text:
                                    num_m = re.search(r'([\d.]+)万', text)
                                    if num_m: val = int(float(num_m.group(1)) * 10000)
                                elif '亿' in text:
                                    num_m = re.search(r'([\d.]+)亿', text)
                                    if num_m: val = int(float(num_m.group(1)) * 100000000)
                                else:
                                    val_m = re.search(r'(\d+)', text.replace(',', ''))
                                    val = int(val_m.group(1)) if val_m else 0

                                # ✅ Standardized field names
                                if "播放" in text or "观看" in text: stats["play_count"] = val
                                elif "点赞" in text: stats["like_count"] = val
                                elif "评论" in text: stats["comment_count"] = val
                                elif "分享" in text or "转发" in text: stats["share_count"] = val
                            except: pass

                        logger.debug(f"Scraped douyin video {work_id}: {stats['title'][:30] if stats['title'] else 'NO_TITLE'}, play_count={stats['play_count']}")  # ✅ Updated log
                    except Exception as e:
                        logger.warning(f"Failed to scrape stats for {work_id}: {e}")
                    results.append(stats)

            except Exception:
                pass
            finally:
                if detail_page is not page:
                    try:
                        await detail_page.close()
                    except Exception:
                        pass
                # Return to manage page for next item
                try:
                    await page.goto(manage_url, timeout=WAIT_TIMEOUT)
                    await page.wait_for_load_state("networkidle")
                    await self._close_douyin_popups(page)
                except Exception:
                    pass

        return results

    async def collect_channels_data(self, cookie_file: str, account_id: str) -> Dict[str, Any]:
        """Collect WeChat Channels videos for the given account."""
        print("[Channels] Start collecting data...")

        cookie_path = self._resolve_cookie_path(cookie_file)
        if not cookie_path.exists():
            return {"success": False, "error": "Cookie file not found"}

        async with async_playwright() as p:
            browser = await p.chromium.launch(**self._build_launch_args())
            context = await browser.new_context(
                storage_state=cookie_path,
                user_agent=DEFAULT_UA,
                viewport={"width": 1366, "height": 768},
            )
            page = await context.new_page()

            try:
                await page.goto("https://channels.weixin.qq.com/platform/post/list", timeout=30000)
                await page.wait_for_load_state("networkidle")

                if "login" in page.url:
                    return {"success": False, "error": "Login expired"}

                await page.wait_for_selector(".video-item, .post-item, [data-feedid], [data-id]", timeout=WAIT_TIMEOUT)

                videos = await self._collect_with_scroll(
                    page,
                    """
                    () => {
                        const items = document.querySelectorAll('.video-item, .post-item');
                        return Array.from(items).map(item => {
                            return {
                                video_id: item.getAttribute('data-feedid') || item.getAttribute('data-id') || '',
                                title: item.querySelector('.title, .post-title')?.textContent.trim() || '',
                                cover_url: item.querySelector('img')?.src || '',
                                play_count: parseInt(item.querySelector('.view-num, [class*="view"]')?.textContent.replace(/[^0-9]/g, '') || '0'),
                                like_count: parseInt(item.querySelector('.like-num, [class*="like"]')?.textContent.replace(/[^0-9]/g, '') || '0'),
                                comment_count: parseInt(item.querySelector('.comment-num, [class*="comment"]')?.textContent.replace(/[^0-9]/g, '') || '0'),
                                share_count: parseInt(item.querySelector('.share-num, [class*="share"]')?.textContent.replace(/[^0-9]/g, '') || '0'),
                                publish_time: item.querySelector('.publish-time, .time')?.textContent.trim() || ''
                            };
                        });
                    }
                    """,
                    max_rounds=40,
                    wait_ms=1200,
                )

                saved_count = 0
                for video in videos:
                    if video.get("video_id"):
                        self.save_video_data(account_id, "channels", video)
                        saved_count += 1

                print(f"[Channels] Collected {saved_count} videos")
                return {"success": True, "count": saved_count, "videos": videos}

            except PlaywrightTimeoutError:
                return {"success": False, "error": "Timeout waiting for post list (login expired or layout changed)"}
            except Exception as e:  # noqa: BLE001
                print(f"[Channels] Collect failed: {e}")
                return {"success": False, "error": str(e)}
            finally:
                await browser.close()

    async def _collect_kuaishou_ids_by_click(self, page: Page, max_items: int = 50) -> List[Dict[str, Any]]:
        """
        Extract Kuaishou photoId by clicking items in management list.
        The work detail URL usually matches:
          https://cp.kuaishou.com/article/manage/video/detail/<photoId>
        """
        manage_url = "https://cp.kuaishou.com/article/manage/video"
        photo_re = re.compile(r"/detail/([^/?#]+)")

        def parse_photo_id(url: str) -> str:
            m = photo_re.search(url or "")
            return m.group(1) if m else ""

        results: List[Dict[str, Any]] = []
        seen_ids = set()

        # Selection of work items
        card_selectors = [
            ".video-item",
            ".content-item",
            "[class*='item-wrapper']",
            "[class*='content-card']"
        ]

        cards = None
        for sel in card_selectors:
            loc = page.locator(sel)
            try:
                if await loc.count() > 0:
                    cards = loc
                    break
            except Exception:
                continue

        if cards is None:
            return []

        count = await cards.count()
        for idx in range(min(count, max_items)):
            detail_page = page
            try:
                item = cards.nth(idx)
                await item.scroll_into_view_if_needed()
                
                # Try clicking the item
                try:
                    async with page.expect_popup(timeout=2000) as popup_info:
                        await item.click()
                    detail_page = await popup_info.value
                except PlaywrightTimeoutError:
                    await item.click()

                # Poll URL for photoId
                photo_id = ""
                for _ in range(20):
                    photo_id = parse_photo_id(detail_page.url)
                    if photo_id:
                        break
                    await detail_page.wait_for_timeout(500)

                if photo_id and photo_id not in seen_ids:
                    seen_ids.add(photo_id)
                    # Try to extract title/stats on the detail page if possible
                    stats = {"video_id": photo_id, "title": "", "cover_url": "", "play_count": 0, "like_count": 0, "comment_count": 0}
                    try:
                        title_el = await detail_page.locator("h1, .video-title, [class*='title']").first
                        if await title_el.count() > 0:
                            stats["title"] = await title_el.inner_text()
                        
                        # Kuaishou detail stats
                        stats_el = await detail_page.locator(".data-num, [class*='data-item']").all()
                        for idx, s_el in enumerate(stats_el):
                            text = await s_el.inner_text()
                            val_m = re.search(r'(\d+)', text.replace(',', ''))
                            val = int(val_m.group(1)) if val_m else 0
                            # Guessing order if no text labels: play_count, like_count, comment_count
                            if idx == 0: stats["play_count"] = val
                            elif idx == 1: stats["like_count"] = val
                            elif idx == 2: stats["comment_count"] = val
                    except: pass
                    
                    results.append(stats)

            except Exception:
                pass
            finally:
                if detail_page is not page:
                    try: await detail_page.close()
                    except: pass
                # Navigation back if needed
                if page.url != manage_url:
                    try:
                        await page.goto(manage_url, timeout=WAIT_TIMEOUT)
                        await page.wait_for_load_state("networkidle")
                    except: pass

        return results


    async def collect_all_accounts(
        self,
        account_ids: Optional[List[str]] = None,
        platform_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Collect videos for all valid accounts, optionally filtered."""
        from myUtils.cookie_manager import cookie_manager

        allowed_ids = set(account_ids) if account_ids else None
        platform_name = platform_filter.lower() if platform_filter else None

        accounts = cookie_manager.list_flat_accounts()
        results: Dict[str, Any] = {"total": 0, "success": 0, "failed": 0, "details": []}

        tikhub_client = get_tikhub_client()

        @asynccontextmanager
        async def _maybe_tikhub(client: Optional[TikHubClient]):
            if not client:
                yield None
                return
            async with client as opened:
                yield opened

        async with _maybe_tikhub(tikhub_client) as tikhub:
            for account in accounts:
                if account.get("status") != "valid" or not account.get("cookie_file"):
                    continue
                if allowed_ids and account.get("account_id") not in allowed_ids:
                    continue
                if platform_name and account.get("platform") != platform_name:
                    continue

                platform = account["platform"]
                account_id = account["account_id"]
                cookie_file = account["cookie_file"]

                print("\n" + "=" * 50)
                print(f"[Collector] Collect account: {account['name']} ({platform})")
                print("=" * 50)

                result: Optional[Dict[str, Any]] = None
                if platform == "kuaishou":
                    if tikhub:
                        result = await self.collect_kuaishou_data_tikhub(account, tikhub, TIKHUB_MAX_PAGES)
                        if result.get("success"):
                            pass
                        else:
                            logger.warning(f"[Kuaishou] TikHub failed, falling back: {result.get('error')}")
                            result = await self.collect_kuaishou_data(cookie_file, account_id)
                    else:
                        result = await self.collect_kuaishou_data(cookie_file, account_id)
                elif platform == "xiaohongshu":
                    if tikhub:
                        result = await self.collect_xiaohongshu_data_tikhub(account, tikhub, TIKHUB_MAX_PAGES)
                        if result.get("success"):
                            pass
                        else:
                            logger.warning(f"[XHS] TikHub failed, falling back: {result.get('error')}")
                            result = await self.collect_xiaohongshu_data(cookie_file, account_id)
                    else:
                        result = await self.collect_xiaohongshu_data(cookie_file, account_id)
                elif platform == "douyin":
                    result = await self.collect_douyin_data(cookie_file, account_id)
                elif platform == "channels":
                    if tikhub:
                        result = await self.collect_channels_data_tikhub(account, tikhub, TIKHUB_MAX_PAGES)
                        if result.get("success"):
                            pass
                        else:
                            logger.warning(f"[Channels] TikHub failed, falling back: {result.get('error')}")
                            result = await self.collect_channels_data(cookie_file, account_id)
                    else:
                        result = await self.collect_channels_data(cookie_file, account_id)

                if result:
                    results["total"] += 1
                    if result.get("success"):
                        results["success"] += 1
                    else:
                        results["failed"] += 1

                    results["details"].append(
                        {
                            "account": account["name"],
                            "account_id": account_id,
                            "platform": platform,
                            **result,
                        }
                    )

        return results


collector = VideoDataCollector()


if __name__ == "__main__":
    print("=" * 50)
    print("Video data auto-collector")
    print("=" * 50)

    results = asyncio.run(collector.collect_all_accounts())

    print("\n" + "=" * 50)
    print("Collection report")
    print("=" * 50)
    print(f"Total accounts: {results['total']}")
    print(f"Success: {results['success']}")
    print(f"Failed: {results['failed']}")

    for detail in results["details"]:
        status = "OK" if detail.get("success") else "FAIL"
        count = detail.get("count", 0)
        error = detail.get("error", "")
        if detail.get("success"):
            print(f"{status} {detail['account']} ({detail['platform']}): {count} videos")
        else:
            print(f"{status} {detail['account']} ({detail['platform']}): {error}")
