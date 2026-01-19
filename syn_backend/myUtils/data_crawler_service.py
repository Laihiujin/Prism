"""
数据抓取服务
集成 TkDataRecycle 项目的抓取能力
支持抖音、快手、小红书、B站等平台的数据抓取
"""
import httpx
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from loguru import logger
from playwright.async_api import async_playwright
from myUtils.cookie_manager import cookie_manager


class DataCrawlerService:
    """数据抓取服务"""

    def __init__(self, tk_api_base_url: str = None):
        """
        初始化数据抓取服务

        Args:
            tk_api_base_url: TkDataRecycle API 基础URL
        """
        if not tk_api_base_url:
            tk_api_base_url = os.getenv(
                "DATA_CRAWLER_API_BASE_URL",
                "http://localhost:7000/api/v1/douyin-tiktok/api",
            )
        self.tk_api_base_url = tk_api_base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)
        self._cookies_dir = cookie_manager.cookies_dir
        self._default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # ==================== 抖音数据抓取 ====================

    async def fetch_douyin_video(self, aweme_id: str) -> Dict[str, Any]:
        """
        获取抖音视频详情

        Args:
            aweme_id: 抖音视频ID

        Returns:
            视频详细信息
        """
        try:
            url = f"{self.tk_api_base_url}/douyin/web/fetch_one_video"
            response = await self.client.get(url, params={"aweme_id": aweme_id})
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 200:
                return {
                    "success": True,
                    "data": data.get("data"),
                    "platform": "douyin"
                }
            else:
                logger.error(f"抖音视频抓取失败: {data}")
                return {
                    "success": False,
                    "error": "API返回错误",
                    "platform": "douyin"
                }

        except Exception as e:
            logger.error(f"抖音视频抓取异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "platform": "douyin"
            }

    async def _load_cookie_file(self, account_file: str) -> Optional[Dict[str, Any]]:
        """
        读取存储状态文件
        """
        file_path = cookie_manager._resolve_cookie_path(account_file)
        if not file_path.exists():
            return None
        try:
            with file_path.open("r", encoding="utf-8") as fp:
                return json.load(fp)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"读取cookie文件失败 {account_file}: {exc}")
            return None

    async def fetch_xiaohongshu_video(self, note_id: str, account_file: str) -> Dict[str, Any]:
        """
        使用 MediaCrawler 的 API 客户端抓取小红书笔记详情

        Args:
            note_id: 小红书笔记ID
            account_file: cookiesFile 下的账号 cookie 存储文件
        """
        try:
            cookie_state = await self._load_cookie_file(account_file)
            if not cookie_state:
                return {"success": False, "error": "Cookie 文件不存在", "platform": "xiaohongshu"}

            from mediacrawler.media_platform.xhs.client import XiaoHongShuClient
            from mediacrawler.tools.crawler_util import convert_cookies

            cookies = cookie_state.get("cookies") or []
            if not cookies:
                return {"success": False, "error": "Cookie 文件缺少 cookies 字段", "platform": "xiaohongshu"}

            cookie_str, cookie_dict = convert_cookies(cookies)

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    context = await browser.new_context(storage_state=cookie_state, user_agent=self._default_ua)
                    page = await context.new_page()
                    await page.goto("https://www.xiaohongshu.com", timeout=30000)

                    client = XiaoHongShuClient(
                        headers={
                            "accept": "application/json, text/plain, */*",
                            "accept-language": "zh-CN,zh;q=0.9",
                            "content-type": "application/json;charset=UTF-8",
                            "origin": "https://www.xiaohongshu.com",
                            "referer": "https://www.xiaohongshu.com/",
                            "user-agent": self._default_ua,
                            "Cookie": cookie_str,
                        },
                        playwright_page=page,
                        cookie_dict=cookie_dict,
                        proxy=None,
                    )

                    detail = await client.get_note_by_id(note_id)

                    if detail:
                        return {"success": True, "data": detail, "platform": "xiaohongshu"}
                    return {"success": False, "error": "未获取到笔记详情", "platform": "xiaohongshu"}
                finally:
                    await browser.close()

        except Exception as exc:  # noqa: BLE001
            logger.error(f"小红书视频抓取异常: {exc}")
            return {"success": False, "error": str(exc), "platform": "xiaohongshu"}

    async def fetch_douyin_user_posts(
        self,
        sec_user_id: str,
        max_cursor: int = 0,
        count: int = 20
    ) -> Dict[str, Any]:
        """
        获取抖音用户发布的视频列表

        Args:
            sec_user_id: 用户ID
            max_cursor: 分页游标
            count: 每页数量

        Returns:
            视频列表
        """
        try:
            url = f"{self.tk_api_base_url}/douyin/web/fetch_user_post_videos"
            response = await self.client.get(
                url,
                params={
                    "sec_user_id": sec_user_id,
                    "max_cursor": max_cursor,
                    "count": count
                }
            )
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 200:
                return {
                    "success": True,
                    "data": data.get("data"),
                    "platform": "douyin"
                }
            else:
                return {
                    "success": False,
                    "error": "API返回错误",
                    "platform": "douyin"
                }

        except Exception as e:
            logger.error(f"抖音用户视频抓取异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "platform": "douyin"
            }

    async def fetch_douyin_video_comments(
        self,
        aweme_id: str,
        cursor: int = 0,
        count: int = 20
    ) -> Dict[str, Any]:
        """
        获取抖音视频评论

        Args:
            aweme_id: 视频ID
            cursor: 分页游标
            count: 每页数量

        Returns:
            评论列表
        """
        try:
            url = f"{self.tk_api_base_url}/douyin/web/fetch_video_comments"
            response = await self.client.get(
                url,
                params={
                    "aweme_id": aweme_id,
                    "cursor": cursor,
                    "count": count
                }
            )
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 200:
                return {
                    "success": True,
                    "data": data.get("data"),
                    "platform": "douyin"
                }
            else:
                return {
                    "success": False,
                    "error": "API返回错误",
                    "platform": "douyin"
                }

        except Exception as e:
            logger.error(f"抖音评论抓取异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "platform": "douyin"
            }

    async def fetch_douyin_hot_search(self) -> Dict[str, Any]:
        """
        获取抖音热榜

        Returns:
            热榜数据
        """
        try:
            url = f"{self.tk_api_base_url}/douyin/web/fetch_hot_search"
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 200:
                return {
                    "success": True,
                    "data": data.get("data"),
                    "platform": "douyin"
                }
            else:
                return {
                    "success": False,
                    "error": "API返回错误",
                    "platform": "douyin"
                }

        except Exception as e:
            logger.error(f"抖音热榜抓取异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "platform": "douyin"
            }

    # ==================== B站数据抓取 ====================

    async def fetch_bilibili_video(self, bvid: str) -> Dict[str, Any]:
        """
        获取B站视频详情

        Args:
            bvid: B站视频BVID

        Returns:
            视频详细信息
        """
        try:
            url = f"{self.tk_api_base_url}/bilibili/web/fetch_one_video"
            response = await self.client.get(url, params={"bvid": bvid})
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 200:
                return {
                    "success": True,
                    "data": data.get("data"),
                    "platform": "bilibili"
                }
            else:
                return {
                    "success": False,
                    "error": "API返回错误",
                    "platform": "bilibili"
                }

        except Exception as e:
            logger.error(f"B站视频抓取异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "platform": "bilibili"
            }

    # ==================== 通用数据抓取 ====================

    async def fetch_video_by_url(self, video_url: str) -> Dict[str, Any]:
        """
        根据URL抓取视频信息（支持多平台）

        Args:
            video_url: 视频URL

        Returns:
            视频信息
        """
        try:
            # 识别平台
            platform = self._detect_platform(video_url)

            if platform == "douyin":
                # 从URL提取aweme_id
                aweme_id = self._extract_douyin_id(video_url)
                return await self.fetch_douyin_video(aweme_id)

            elif platform == "xiaohongshu":
                note_id = self._extract_xiaohongshu_id(video_url)
                account_file = self._pick_default_cookie_file("xiaohongshu")
                if not account_file:
                    return {"success": False, "error": "未找到可用小红书账号", "platform": "xiaohongshu"}
                return await self.fetch_xiaohongshu_video(note_id, account_file)

            elif platform == "kuaishou":
                photo_id = self._extract_kuaishou_id(video_url)
                account_file = self._pick_default_cookie_file("kuaishou")
                if not account_file:
                    return {"success": False, "error": "未找到可用快手账号", "platform": "kuaishou"}
                return await self.fetch_kuaishou_video(photo_id, account_file)

            elif platform == "bilibili":
                # 从URL提取bvid
                bvid = self._extract_bilibili_id(video_url)
                return await self.fetch_bilibili_video(bvid)

            else:
                return {
                    "success": False,
                    "error": f"不支持的平台: {platform}",
                    "platform": "unknown"
                }

        except Exception as e:
            logger.error(f"URL视频抓取异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "platform": "unknown"
            }

    def _detect_platform(self, url: str) -> str:
        """检测平台类型"""
        if "douyin.com" in url or "iesdouyin.com" in url:
            return "douyin"
        elif "bilibili.com" in url:
            return "bilibili"
        elif "xiaohongshu.com" in url or "xhslink.com" in url:
            return "xiaohongshu"
        elif "kuaishou.com" in url:
            return "kuaishou"
        else:
            return "unknown"

    def _extract_xiaohongshu_id(self, url: str) -> str:
        """从小红书URL提取笔记ID"""
        import re

        # 支持 https://www.xiaohongshu.com/explore/<id>
        match = re.search(r"/explore/([a-zA-Z0-9]+)", url)
        if match:
            return match.group(1)
        raise ValueError("无法从URL提取笔记ID")

    def _extract_kuaishou_id(self, url: str) -> str:
        """从快手URL提取photoId"""
        import re

        match = re.search(r"short-video/([a-zA-Z0-9_-]+)", url)
        if match:
            return match.group(1)
        raise ValueError("无法从URL提取video ID")

    def _extract_douyin_id(self, url: str) -> str:
        """从抖音URL提取视频ID"""
        # 简化实现，实际需要更复杂的解析
        import re
        match = re.search(r'/video/(\d+)', url)
        if match:
            return match.group(1)
        # 尝试其他格式
        match = re.search(r'aweme_id=(\d+)', url)
        if match:
            return match.group(1)
        raise ValueError("无法从URL提取视频ID")

    def _extract_bilibili_id(self, url: str) -> str:
        """从B站URL提取视频ID"""
        import re
        match = re.search(r'BV[a-zA-Z0-9]+', url)
        if match:
            return match.group(0)
        raise ValueError("无法从URL提取视频ID")

    def _pick_default_cookie_file(self, platform: str) -> Optional[str]:
        """从 cookie_manager 选出一个有效账号的 cookie 文件。"""
        try:
            accounts = cookie_manager.list_flat_accounts()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"读取账号列表失败: {exc}")
            accounts = []

        for acc in accounts:
            if acc.get("status") != "valid":
                continue
            if (acc.get("platform") or "").lower() != platform:
                continue
            cookie_file = acc.get("cookie_file")
            if cookie_file:
                target = self._cookies_dir / cookie_file
                if target.exists():
                    return cookie_file

        # fallback: 按前缀寻找
        prefix_map = {"xiaohongshu": "xiaohongshu", "kuaishou": "kuaishou"}
        prefix = prefix_map.get(platform)
        if prefix:
            for path in self._cookies_dir.glob(f"{prefix}*.json"):
                return path.name
        return None

    async def fetch_kuaishou_video(self, photo_id: str, account_file: str) -> Dict[str, Any]:
        """使用 MediaCrawler 的 API 客户端抓取快手视频详情"""
        try:
            cookie_state = await self._load_cookie_file(account_file)
            if not cookie_state:
                return {"success": False, "error": "Cookie 文件不存在", "platform": "kuaishou"}

            from mediacrawler.media_platform.kuaishou.client import KuaiShouClient
            from mediacrawler.tools.crawler_util import convert_cookies

            cookies = cookie_state.get("cookies") or []
            if not cookies:
                return {"success": False, "error": "Cookie 文件缺少 cookies 字段", "platform": "kuaishou"}

            cookie_str, cookie_dict = convert_cookies(cookies)

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    context = await browser.new_context(storage_state=cookie_state, user_agent=self._default_ua)
                    page = await context.new_page()
                    await page.goto("https://www.kuaishou.com", timeout=30000)

                    client = KuaiShouClient(
                        headers={
                            "User-Agent": self._default_ua,
                            "Cookie": cookie_str,
                            "Origin": "https://www.kuaishou.com",
                            "Referer": "https://www.kuaishou.com",
                            "Content-Type": "application/json;charset=UTF-8",
                        },
                        playwright_page=page,
                        cookie_dict=cookie_dict,
                        proxy=None,
                    )

                    detail = await client.get_video_info(photo_id)

                    if detail:
                        return {"success": True, "data": detail, "platform": "kuaishou"}
                    return {"success": False, "error": "未获取到视频详情", "platform": "kuaishou"}
                finally:
                    await browser.close()

        except Exception as exc:  # noqa: BLE001
            logger.error(f"快手视频抓取异常: {exc}")
            return {"success": False, "error": str(exc), "platform": "kuaishou"}


# 全局实例
_data_crawler_service = None


def get_data_crawler_service() -> DataCrawlerService:
    """获取数据抓取服务实例"""
    global _data_crawler_service
    if _data_crawler_service is None:
        _data_crawler_service = DataCrawlerService()
    return _data_crawler_service
