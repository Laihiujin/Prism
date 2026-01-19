import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from typing import Dict, Optional
import os
from myUtils.cookie_manager import cookie_manager

BASE_DIR = Path(__file__).parent.parent
from config.conf import PLAYWRIGHT_HEADLESS

class HeaderExtractor:
    async def extract_headers(self, platform: str, cookie_file: str) -> Dict:
        """
        使用Playwright登录并提取API请求头
        """
        cookie_path = cookie_manager._resolve_cookie_path(cookie_file)
        if not cookie_path.exists():
            return {"success": False, "error": f"Cookie file not found: {cookie_file}"}

        async with async_playwright() as p:
            # 启动浏览器
            browser = await p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
            try:
                context = await browser.new_context(storage_state=str(cookie_path))
            except Exception as e:
                await browser.close()
                return {"success": False, "error": f"Invalid cookie file: {e}"}
                
            page = await context.new_page()
            
            headers_found = {}
            
            # 定义目标URL和API特征
            target_url = ""
            api_keywords = []
            
            if platform == 'kuaishou':
                target_url = "https://cp.kuaishou.com/article/manage/video"
                api_keywords = ["graphql", "rest/pc", "api"]
            elif platform == 'xiaohongshu':
                target_url = "https://creator.xiaohongshu.com/creator/post"
                api_keywords = ["api/sns", "api/galaxy"] 
            elif platform == 'douyin':
                target_url = "https://creator.douyin.com/creator-micro/content/manage"
                api_keywords = ["aweme", "web/api"]
            elif platform == 'channels':
                target_url = "https://channels.weixin.qq.com/platform/post/list"
                api_keywords = ["cgi-bin", "finder"]
            elif platform == 'bilibili':
                target_url = "https://member.bilibili.com/platform/upload-manager/article"
                api_keywords = ["x/web-interface", "api.bilibili.com"]
            else:
                await browser.close()
                return {"success": False, "error": f"Unsupported platform: {platform}"}

            # 监听请求
            async def handle_request(request):
                nonlocal headers_found
                if headers_found:
                    return
                
                url = request.url
                resource_type = request.resource_type
                
                # 只关注 XHR/Fetch 请求
                if resource_type not in ["xhr", "fetch"]:
                    return
                    
                # 检查URL是否包含关键词
                for keyword in api_keywords:
                    if keyword in url:
                        # 排除一些静态资源或无关请求
                        if ".js" in url or ".css" in url or ".png" in url:
                            continue
                            
                        # 获取请求头
                        headers = request.headers
                        
                        # 简单的有效性检查 (例如必须包含 Cookie)
                        if "cookie" in headers or "authorization" in headers:
                            headers_found = headers
                            print(f"✅ [HeaderExtractor] Found headers from: {url}")
                        break
            
            page.on("request", handle_request)
            
            try:
                print(f"🔍 [HeaderExtractor] Navigating to {target_url}...")
                await page.goto(target_url, timeout=45000)
                
                # 等待网络空闲，确保请求发出
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except:
                    pass # networkidle might timeout, but we might have already captured headers
                
                # 如果还没找到，额外等待一会儿
                if not headers_found:
                    await page.wait_for_timeout(5000)
                    
                if headers_found:
                    return {
                        "success": True, 
                        "platform": platform,
                        "headers": headers_found,
                        "source_url": page.url
                    }
                else:
                    return {
                        "success": False, 
                        "error": "No suitable API request found to extract headers",
                        "current_url": page.url
                    }
                    
            except Exception as e:
                return {"success": False, "error": str(e)}
            finally:
                await browser.close()

header_extractor = HeaderExtractor()
