"""
抖音 sec_uid 解析器
支持三种解析策略：
1. 从 cookie/数据库读取
2. 使用搜索接口（需要 a_bogus 签名）
3. 使用 Playwright 模拟搜索（降级方案）
"""
import re
import httpx
from typing import Optional, Dict, Any
from pathlib import Path
import sys

# 确保能导入 douyin_tiktok_api
BASE_DIR = Path(__file__).resolve().parents[4]
DOUYIN_API_PATH = BASE_DIR / "douyin_tiktok_api"
if DOUYIN_API_PATH.exists() and str(DOUYIN_API_PATH) not in sys.path:
    sys.path.insert(0, str(DOUYIN_API_PATH))

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class DouyinSecUidResolver:
    """抖音 sec_uid 解析器"""
    
    def __init__(self):
        self.search_api_url = "https://www.douyin.com/aweme/v1/web/discover/search/"
    
    async def resolve(
        self,
        user_id: str,
        cookie_header: Optional[str] = None,
        use_playwright: bool = False
    ) -> Optional[str]:
        """
        解析抖音用户 ID 到 sec_uid
        
        Args:
            user_id: 抖音号（数字ID）
            cookie_header: Cookie 字符串
            use_playwright: 是否使用 Playwright 降级方案
            
        Returns:
            sec_uid 或 None
        """
        # 策略1: 尝试使用搜索接口
        sec_uid = await self._resolve_via_search_api(user_id, cookie_header)
        if sec_uid:
            return sec_uid
        
        # 策略2: 降级到 Playwright
        if use_playwright:
            sec_uid = await self._resolve_via_playwright(user_id, cookie_header)
            if sec_uid:
                return sec_uid
        
        # 策略3: 最后尝试访问用户主页（当前实现）
        return await self._resolve_via_profile_page(user_id, cookie_header)
    
    async def _resolve_via_search_api(
        self,
        user_id: str,
        cookie_header: Optional[str] = None
    ) -> Optional[str]:
        """
        通过搜索接口解析 sec_uid
        
        注意：此方法需要 a_bogus 签名，如果没有签名工具会降级到直接请求
        """
        # 方法1: 尝试使用 douyin_tiktok_api 的 crawler（带签名）
        try:
            from crawlers.douyin.web.utils import BogusManager

            params = {
                "keyword": user_id,
                "search_channel": "aweme_user_web",
                "aid": "6383",
                "device_platform": "webapp",
                "pc_client_type": "1",
                "version_code": "170400",
                "version_name": "17.4.0",
                "search_source": "normal_search",
                "offset": "0",
                "count": "10",
            }
            params["msToken"] = ""
            params["a_bogus"] = BogusManager.ab_model_2_endpoint(params, DEFAULT_UA)

            headers = {
                "User-Agent": DEFAULT_UA,
                "Referer": "https://www.douyin.com/",
                "Origin": "https://www.douyin.com",
            }
            if cookie_header:
                headers["Cookie"] = cookie_header

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.search_api_url, params=params, headers=headers)
            if resp.status_code >= 400:
                return await self._resolve_via_direct_search(user_id, cookie_header)

            response = resp.json()

            # 解析结果
            if isinstance(response, dict):
                data = response.get("data") or response
                user_list = data.get("user_list", [])

                for user in user_list:
                    user_info = user.get("user_info", {})
                    # 匹配用户 ID
                    unique_id = user_info.get("unique_id", "")
                    uid = user_info.get("uid", "")
                    short_id = user_info.get("short_id", "")

                    if str(unique_id) == str(user_id) or str(uid) == str(user_id) or str(short_id) == str(user_id):
                        sec_uid = user_info.get("sec_uid")
                        if sec_uid:
                            return sec_uid

            return None

        except ImportError:
            # 方法2: 降级到直接 HTTP 请求（无签名，可能失败）
            print("  提示: douyin_tiktok_api 未安装，使用降级方案")
            return await self._resolve_via_direct_search(user_id, cookie_header)
        except Exception as e:
            print(f"  搜索接口解析失败: {e}")
            return None
    
    async def _resolve_via_direct_search(
        self,
        user_id: str,
        cookie_header: Optional[str] = None
    ) -> Optional[str]:
        """
        直接 HTTP 请求搜索接口（无 a_bogus 签名，成功率较低）
        """
        try:
            headers = {
                "User-Agent": DEFAULT_UA,
                "Referer": "https://www.douyin.com/",
            }
            if cookie_header:
                headers["Cookie"] = cookie_header
            
            params = {
                "keyword": user_id,
                "search_channel": "aweme_user_web",
                "aid": "6383",
                "device_platform": "webapp",
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    self.search_api_url,
                    params=params,
                    headers=headers
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    user_list = data.get("data", {}).get("user_list", [])
                    
                    for user in user_list:
                        user_info = user.get("user_info", {})
                        unique_id = user_info.get("unique_id", "")
                        uid = user_info.get("uid", "")
                        
                        if str(unique_id) == str(user_id) or str(uid) == str(user_id):
                            sec_uid = user_info.get("sec_uid")
                            if sec_uid:
                                return sec_uid
            
            return None
            
        except Exception as e:
            print(f"  直接搜索请求失败: {e}")
            return None

    
    async def _resolve_via_playwright(
        self,
        user_id: str,
        cookie_header: Optional[str] = None
    ) -> Optional[str]:
        """
        使用 Playwright 模拟搜索解析 sec_uid
        这是最稳定但性能最差的方案
        """
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                
                # 设置 cookie
                context_options = {}
                if cookie_header:
                    cookies = self._parse_cookie_header(cookie_header)
                    context_options["storage_state"] = {"cookies": cookies}
                
                context = await browser.new_context(**context_options)
                page = await context.new_page()
                
                try:
                    # 访问抖音首页
                    await page.goto("https://www.douyin.com/", wait_until="domcontentloaded")
                    await page.wait_for_timeout(2000)
                    
                    # 输入搜索关键词
                    search_input = await page.wait_for_selector('input[placeholder*="搜索"]', timeout=5000)
                    await search_input.fill(user_id)
                    await page.wait_for_timeout(500)
                    
                    # 点击搜索按钮
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(3000)
                    
                    # 切换到用户标签
                    try:
                        user_tab = await page.wait_for_selector('text=/用户/', timeout=3000)
                        await user_tab.click()
                        await page.wait_for_timeout(2000)
                    except:
                        pass
                    
                    # 提取 sec_uid
                    links = await page.query_selector_all('a[href*="/user/"]')
                    for link in links:
                        href = await link.get_attribute("href")
                        if href:
                            match = re.search(r'/user/([^/?#]+)', href)
                            if match:
                                sec_uid = match.group(1)
                                # 验证不是数字ID
                                if not sec_uid.isdigit() and len(sec_uid) > 20:
                                    return sec_uid
                    
                    return None
                    
                finally:
                    await browser.close()
                    
        except Exception as e:
            print(f"Playwright 解析失败: {e}")
            return None
    
    async def _resolve_via_profile_page(
        self,
        user_id: str,
        cookie_header: Optional[str] = None
    ) -> Optional[str]:
        """
        通过访问用户主页解析 sec_uid（当前实现的方法）
        """
        headers = {
            "User-Agent": DEFAULT_UA,
            "Referer": "https://www.douyin.com/",
        }
        if cookie_header:
            headers["Cookie"] = cookie_header
        
        url = f"https://www.douyin.com/user/{user_id}"
        
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
            
            # 从重定向URL提取
            final_url = str(resp.url)
            match = re.search(r"/user/([^/?#]+)", final_url)
            if match:
                sec_uid = match.group(1)
                if sec_uid and sec_uid != str(user_id):
                    return sec_uid
            
            # 从页面内容提取
            text = resp.text or ""
            match = re.search(r'"sec_uid"\s*:\s*"([^"]+)"', text) or \
                    re.search(r'"secUid"\s*:\s*"([^"]+)"', text)
            if match:
                return match.group(1)
            
        except Exception as e:
            print(f"主页访问解析失败: {e}")
        
        return None
    
    def _parse_cookie_header(self, cookie_header: str) -> list:
        """将 Cookie 字符串解析为 Playwright 格式"""
        cookies = []
        for item in cookie_header.split(";"):
            item = item.strip()
            if "=" in item:
                name, value = item.split("=", 1)
                cookies.append({
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": ".douyin.com",
                    "path": "/"
                })
        return cookies


# 全局单例
_resolver = DouyinSecUidResolver()


async def resolve_douyin_sec_uid(
    user_id: str,
    cookie_header: Optional[str] = None,
    use_playwright: bool = False
) -> Optional[str]:
    """
    解析抖音用户 ID 到 sec_uid
    
    Args:
        user_id: 抖音号（数字ID）
        cookie_header: Cookie 字符串
        use_playwright: 是否使用 Playwright 降级方案
        
    Returns:
        sec_uid 或 None
    """
    return await _resolver.resolve(user_id, cookie_header, use_playwright)
