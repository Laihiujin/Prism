"""
统一的扫码登录服务（五个平台）
逻辑目标：
- 生成二维码
- 轮询时判定成功：页面已到主站且不在 login，或关键 cookie 出现
- 成功时返回 cookies/cookie_str + user_info + full_state(storage_state)
- 不在轮询中使用同步 Playwright，避免事件循环冲突
"""
import asyncio
import base64
import io
import uuid
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import httpx
from loguru import logger
from playwright.async_api import async_playwright

from .schemas import PlatformType
from utils.chrome_detector import get_chrome_executable


# 全局 Playwright 会话
PLAYWRIGHT_SESSIONS: Dict[str, Dict[str, Any]] = {}

try:
    from config.conf import LOCAL_CHROME_PATH, PLAYWRIGHT_HEADLESS, BASE_DIR
except Exception:
    LOCAL_CHROME_PATH = ""
    PLAYWRIGHT_HEADLESS = True
    BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _resolve_browser_executable() -> Optional[str]:
    """Resolve a usable Chromium/Chrome binary path."""
    explicit_path = str(LOCAL_CHROME_PATH).strip() if LOCAL_CHROME_PATH else ""
    if explicit_path:
        configured = Path(explicit_path)
        if configured.exists():
            return str(configured)
        logger.warning(f"[Login] LOCAL_CHROME_PATH not found: {configured}. Falling back to auto-detect.")

    try:
        detected = get_chrome_executable()
        if detected and Path(detected).exists():
            return detected
    except FileNotFoundError as e:
        logger.warning(f"[Login] Auto-detect browser failed: {e}")
    except Exception as e:
        logger.warning(f"[Login] Unexpected browser detection error: {e}")

    return None


class PlaywrightLoginManager:
    @staticmethod
    async def create_browser(session_id: str):
        p = await async_playwright().start()
        launch_args = {"headless": PLAYWRIGHT_HEADLESS, "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]}
        executable_path = _resolve_browser_executable()
        if executable_path:
            launch_args["executable_path"] = executable_path
            logger.info(f"[Login] Using browser executable: {executable_path}")
        else:
            logger.info("[Login] Using bundled Playwright Chromium (no local browser configured)")
        browser = await p.chromium.launch(**launch_args)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()
        PLAYWRIGHT_SESSIONS[session_id] = {
            "playwright": p,
            "browser": browser,
            "context": context,
            "page": page,
            "created_at": time.time()
        }
        return page

    @staticmethod
    async def cleanup_session(session_id: str):
        s = PLAYWRIGHT_SESSIONS.get(session_id)
        if not s:
            return
        try:
            await s["browser"].close()
            await s["playwright"].stop()
        except Exception:
            pass
        PLAYWRIGHT_SESSIONS.pop(session_id, None)


def _b64_png_from_buffer(buf: bytes) -> str:
    return f"data:image/png;base64,{base64.b64encode(buf).decode('utf-8')}"


class BilibiliLoginService:
    """B站（API方式扫码）"""
    @staticmethod
    async def get_qrcode() -> Tuple[str, str, str]:
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://passport.bilibili.com/x/passport-login/web/qrcode/generate",
                                    headers={"User-Agent": "Mozilla/5.0"})
            data = resp.json()
            if data.get("code") != 0:
                raise Exception(data.get("message", "bilibili qrcode failed"))
            qrcode_url = data["data"]["url"]
            qrcode_key = data["data"]["qrcode_key"]
            buffer = io.BytesIO()
            try:
                import qrcode
                qr = qrcode.QRCode(version=1, box_size=10, border=2)
                qr.add_data(qrcode_url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                img.save(buffer, format="PNG")
            except Exception:
                # 退化：返回 URL
                return qrcode_key, qrcode_url, qrcode_url
            return qrcode_key, qrcode_url, _b64_png_from_buffer(buffer.getvalue())

    @staticmethod
    async def poll_status(qrcode_key: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get("https://passport.bilibili.com/x/passport-login/web/qrcode/poll",
                                    params={"qrcode_key": qrcode_key},
                                    headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                return {"status": "failed"}
            data = resp.json().get("data", {}) or {}
            code = data.get("code")
            status_map = {86101: "waiting", 86090: "scanned", 0: "confirmed", 86038: "expired"}
            status = status_map.get(code, "failed")
            if status != "confirmed":
                return {"status": status, "message": data.get("message", "")}

            login_url = data.get("url")
            cookies = {}
            user_info = {}
            try:
                # 获取 cookies + 用户信息
                c_resp = await client.get(login_url, headers={"User-Agent": "Mozilla/5.0"})
                cookies = dict(client.cookies)
                nav = await client.get("https://api.bilibili.com/x/web-interface/nav", cookies=cookies,
                                       headers={"User-Agent": "Mozilla/5.0"})
                nav_data = nav.json().get("data", {}) if nav.status_code == 200 else {}
                user_info = {
                    "user_id": str(nav_data.get("mid", "")),
                    "username": nav_data.get("uname", "Bilibili User"),
                    "avatar": nav_data.get("face", "")
                }
            except Exception as e:
                logger.error(f"[Bilibili] poll userinfo failed: {e}")

            return {
                "status": "confirmed",
                "data": {
                    "cookies": cookies,
                    "user_info": user_info
                }
            }

    @staticmethod
    async def supports_api_login() -> bool: return True
    @staticmethod
    def get_sse_type() -> Optional[str]: return None


class XiaohongshuLoginService:
    """小红书（Playwright扫码）"""
    @staticmethod
    async def get_qrcode() -> Tuple[str, str, str]:
        session_id = str(uuid.uuid4())
        page = await PlaywrightLoginManager.create_browser(session_id)
        try:
            await page.goto("https://creator.xiaohongshu.com/new/home", timeout=60000)
            await asyncio.sleep(2)
            # 尝试切换到扫码
            try:
                switch = await page.query_selector(".login-box-container img.css-wemwzq")
                if switch:
                    await switch.click()
                else:
                    btn = await page.get_by_text("扫码登录").element_handle()
                    if btn:
                        await btn.click()
            except Exception:
                pass

            selectors = [
                "div.css-dvxtzn img.css-1lhmg90",
                "img.css-1lhmg90",
                "img[src*='data:image']",
                ".css-dvxtzn img",
            ]
            for sel in selectors:
                try:
                    img = await page.wait_for_selector(sel, timeout=12000)
                    if img:
                        src = await img.get_attribute("src")
                        if src:
                            return session_id, "https://creator.xiaohongshu.com/new/home", src
                except Exception:
                    continue

            # 兜底截图
            try:
                box = await page.query_selector(".login-box-container") or await page.query_selector("body")
                if box:
                    png = await box.screenshot(type="png")
                    return session_id, "https://creator.xiaohongshu.com/new/home", _b64_png_from_buffer(png)
            except Exception:
                pass
            raise Exception("No QR code found for XHS")
        except Exception as e:
            await PlaywrightLoginManager.cleanup_session(session_id)
            raise e

    @staticmethod
    async def poll_status(session_id: str) -> Dict[str, Any]:
        if session_id not in PLAYWRIGHT_SESSIONS:
            return {"status": "expired"}
        session = PLAYWRIGHT_SESSIONS[session_id]
        page = session["page"]
        try:
            cookies = await session["context"].cookies()
            cookie_names = [c["name"] for c in cookies]
            logger.info(f"[XHS] poll cookies: {cookie_names}, url={page.url}")
            if (
                any(c["name"] in ["web_session", "xhsuid", "customer-sso-sid", "a1", "webId"] for c in cookies)
                and "login" not in page.url.lower()
            ):
                cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                login_info = await XiaohongshuLoginService.get_user_info_from_page(page, cookies)
                try:
                    full_state = await session["context"].storage_state()
                except Exception as e:
                    logger.error(f"[XHS] storage_state failed: {e}")
                    full_state = None
                await PlaywrightLoginManager.cleanup_session(session_id)
                return {
                    "status": "confirmed",
                    "data": {
                        "cookie": cookie_str,
                        "login_info": login_info,
                        "full_state": full_state
                    }
                }
            return {"status": "waiting"}
        except Exception as e:
            logger.error(f"XHS poll failed: {e}")
            return {"status": "failed"}

    @staticmethod
    async def get_user_info_from_page(page: Any, cookies_list: list = None) -> Dict[str, Any]:
        """从页面提取小红书用户信息（参考fetch_user_info_service的DOM抓取逻辑）"""
        try:
            await asyncio.sleep(1)
            user_info = {"name": "", "user_id": "", "avatar": ""}

            # ⚠️ 关键修复：先关闭可能遮挡DOM元素的弹窗
            try:
                # 点击空白区域关闭弹窗 (header 区域的空白处)
                header_blank = await page.query_selector('#header-area > div > div > div:nth-child(1) > div')
                if header_blank:
                    await header_blank.click()
                    await asyncio.sleep(0.5)  # 等待弹窗关闭动画
                    logger.info("[XHS] Clicked blank area to close popover")
            except Exception as e:
                logger.debug(f"[XHS] Close popover failed (may not exist): {e}")

            # ⚠️ 方法1: 从页面显示的"小红书账号"文本提取（最可靠！）
            try:
                import re

                # ✅ 根据实际DOM结构调整选择器：div.personal 内的 .description-text
                selectors_to_try = [
                    'div.personal .description-text',  # 优先：定位到 personal 区域内的 description-text
                    '.description-text div',  # 备选1：description-text下的div（直接包含文本）
                    '.description-text',  # 备选2：description-text本身
                    'text=/小红书账号[:：]?\\s*[\\w_]+/',  # 备选3：通用文本匹配
                    'text=/账号[:：]?\\s*[\\w_]+/',  # 备选4：最泛化的匹配
                ]

                patterns = [
                    r"小红书账号[:：]?\s*([\w_]+)",  # 主要模式
                    r"小红书号[:：]?\s*([\w_]+)",    # 备用模式
                    r"账号[:：]?\s*([\w_]+)",        # 泛化模式放最后
                ]

                for selector in selectors_to_try:
                    try:
                        elem = await page.wait_for_selector(selector, timeout=2500)
                        if not elem:
                            continue

                        text = (await elem.inner_text()) or ""
                        text = text.strip()

                        # 尝试所有正则模式
                        for regex in patterns:
                            match = re.search(regex, text)
                            if match:
                                candidate = match.group(1).strip()
                                # ✅ 验证：排除明显错误的ID（如过长的随机字符串）
                                if candidate and 3 <= len(candidate) <= 30 and candidate not in {"管理", "设置"}:
                                    user_info["user_id"] = candidate
                                    logger.info(f"[XHS] Extracted user_id from DOM text (selector={selector}): {user_info['user_id']}")
                                    break

                        if user_info.get("user_id"):
                            break
                    except Exception as e:
                        logger.debug(f"[XHS] Selector {selector} failed: {e}")
                        continue
            except Exception as e:
                logger.warning(f"[XHS] DOM text extraction failed: {e}")

            # 方法2: 从JS提取（作为兜底）
            if not user_info.get("user_id"):
                try:
                    js_info = await page.evaluate("""() => {
                        if (window.__INITIAL_SSR_STATE__?.Main?.user) return window.__INITIAL_SSR_STATE__.Main.user;
                        if (window.userInfo) return window.userInfo;
                        if (window.__INITIAL_STATE__?.user) return window.__INITIAL_STATE__.user;
                        return null;
                    }""")
                    logger.info(f"[XHS] JS evaluated user data: {js_info}")
                    if js_info and isinstance(js_info, dict):
                        user_info["user_id"] = js_info.get("userId", js_info.get("id", ""))
                        logger.info(f"[XHS] Fallback to JS userId: {user_info['user_id']}")
                except Exception as e:
                    logger.warning(f"XHS JS user info failed: {e}")

            # 方法3: 从正确的cookie字段提取user_id（最后兜底）
            if not user_info.get("user_id"):
                cookies = cookies_list or await page.context.cookies()
                for c in cookies:
                    # ⚠️ 小红书真正的user_id在 x-user-id-creator.xiaohongshu.com
                    if c.get("name") == "x-user-id-creator.xiaohongshu.com":
                        user_info["user_id"] = c.get("value")
                        logger.info(f"[XHS] Fallback to cookie x-user-id: {user_info['user_id']}")
                        break

            # 提取name
            try:
                name_selectors = ['.base .text .account-name', '.account-name', '.user-name', ".user-name", ".name", "span[class*='name']"]
                for selector in name_selectors:
                    try:
                        h = await page.query_selector(selector)
                        if h:
                            text = await h.inner_text()
                            if text and text.strip():
                                user_info["name"] = text.strip().split("\n")[0]
                                break
                    except:
                        continue
            except Exception as e:
                logger.warning(f"XHS name extraction failed: {e}")

            # 提取avatar
            try:
                avatar_selectors = ['.base .avatar img', '.avatar img', 'img[alt*="头像"]', "img[class*='avatar']"]
                for selector in avatar_selectors:
                    try:
                        h = await page.query_selector(selector)
                        if h:
                            src = await h.get_attribute("src")
                            if src:
                                user_info["avatar"] = src
                                break
                    except:
                        continue
            except Exception as e:
                logger.warning(f"XHS avatar extraction failed: {e}")

            if not user_info["name"] and user_info.get("user_id"):
                user_info["name"] = user_info["user_id"]

            logger.info(f"[XHS] Final extracted user_info: {user_info}")
            return user_info
        except Exception as e:
            logger.error(f"Get XHS user info failed: {e}")
            return {"name": "", "user_id": "", "avatar": ""}

    @staticmethod
    async def supports_api_login() -> bool: return True
    @staticmethod
    def get_sse_type() -> Optional[str]: return None


class DouyinLoginService:
    """抖音（Playwright扫码）"""
    @staticmethod
    async def get_qrcode() -> Tuple[str, str, str]:
        session_id = str(uuid.uuid4())
        page = await PlaywrightLoginManager.create_browser(session_id)
        try:
            # 直接访问 QR 登录页，尽快尝试 selector（不做截图兜底）
            try:
                await page.goto("https://creator.douyin.com/creator-micro/login?enter_from=qr", timeout=20000, wait_until="domcontentloaded")
            except Exception:
                # 回退主页
                await page.goto("https://creator.douyin.com/", timeout=20000, wait_until="domcontentloaded")

            async def ensure_qr_tab(frame):
                for txt in ["扫码登录", "二维码登录"]:
                    try:
                        btn = await frame.get_by_text(txt).element_handle(timeout=2000)
                        if btn:
                            await btn.click()
                            return True
                    except Exception:
                        continue
                return False

            selectors = [
                "img.qrcode_img-NPVTJs",
                "div.qrcode-vz0gH7 img",
                "img[alt*='二维码']",
                "img[src*='qrcode']",
                ".qrcode img",
                ".login-qrcode img",
                "img[class*='qrcode']",
                "img[data-e2e*='qr']",
                "img[src*='qr_code']",
                "img[src*='qr-code']",
            ]

            # 先尝试显式 xpath，等待二维码生成
            qr_xpath = "//div[@id='animate_qrcode_container']//img[contains(@class,'qrcode_img')]"
            try:
                h = await page.wait_for_selector(f"xpath={qr_xpath}", timeout=15000)
                if h:
                    src = await h.get_attribute("src")
                    if src:
                        return session_id, "https://creator.douyin.com/", src
                    try:
                        shot = await h.screenshot()
                        if shot:
                            import base64
                            return session_id, "https://creator.douyin.com/", f"data:image/png;base64,{base64.b64encode(shot).decode('utf-8')}"
                    except Exception:
                        pass
            except Exception:
                pass

            # 遍历页面及所有 iframe，尽量拿到二维码
            frames = [page] + page.frames
            for frame in frames:
                try:
                    await ensure_qr_tab(frame)
                except Exception:
                    pass

                for sel in selectors:
                    try:
                        h = await frame.query_selector(sel)
                        if h:
                            src = await h.get_attribute("src")
                            if src:
                                return session_id, "https://creator.douyin.com/", src
                    except Exception:
                        continue

                # 新版页面可能使用嵌套 div + img，尝试显式 xpath
                try:
                    xpath = "//div[@id='douyin_login_comp_scan_code']//img[contains(@class,'qrcode_img')]"
                    h = await frame.query_selector(f"xpath={xpath}")
                    if h:
                        src = await h.get_attribute("src")
                        if src:
                            return session_id, "https://creator.douyin.com/", src
                except Exception:
                    pass

            # 兜底：截图整页返回，避免直接报错（二维码通常在首屏）
            try:
                shot = await page.screenshot(full_page=True)
                if shot:
                    import base64
                    b64 = base64.b64encode(shot).decode("utf-8")
                    return session_id, "https://creator.douyin.com/", f"data:image/png;base64,{b64}"
            except Exception:
                pass

            raise Exception("No QR code found for Douyin (no img src)")
        except Exception as e:
            await PlaywrightLoginManager.cleanup_session(session_id)
            raise e

    @staticmethod
    async def poll_status(session_id: str) -> Dict[str, Any]:
        if session_id not in PLAYWRIGHT_SESSIONS:
            return {"status": "expired"}
        session = PLAYWRIGHT_SESSIONS[session_id]
        page = session["page"]
        try:
            cookies_list = await session["context"].cookies()
            cookies_dict = {c["name"]: c["value"] for c in cookies_list}
            auth_cookies = {k: v for k, v in cookies_dict.items() if k in ["sessionid", "sessionid_ss", "sid_guard", "sid_tt", "passport_auth_id", "odin_tt"] and v}
            is_on_creator = "creator.douyin.com" in page.url
            on_login_page = "login" in page.url.lower()

            user_info = await DouyinLoginService.get_user_info_from_page(page, cookies_list)
            has_user = bool(user_info.get("user_id"))

            if is_on_creator and not on_login_page and (auth_cookies or has_user):
                try:
                    full_state = await session["context"].storage_state()
                except Exception as e:
                    logger.error(f"[Douyin] storage_state failed: {e}")
                    full_state = None
                await PlaywrightLoginManager.cleanup_session(session_id)
                return {
                    "status": "confirmed",
                    "data": {
                        "cookies": cookies_dict,
                        "user_info": user_info,
                        "user_id": user_info.get("user_id", ""),
                        "token": "",
                        "full_state": full_state,
                    },
                }
            return {"status": "waiting"}
        except Exception as e:
            logger.error(f"抖音poll失败: {e}")
            return {"status": "failed"}

    @staticmethod
    async def get_user_info_from_page(page: Any, cookies_list: list = None) -> Dict[str, Any]:
        """Extract Douyin user info from DOM + JS."""
        try:
            await asyncio.sleep(1)
            user_info = {"name": "", "user_id": "", "avatar": ""}

            # Method 1: DOM text (preferred)
            try:
                import re
                # New UI sometimes exposes a unique_id-* node without label.
                try:
                    id_node = await page.wait_for_selector(
                        "div[class^='unique_id-'], div[class*='unique_id-']",
                        timeout=2000
                    )
                    if id_node:
                        raw_text = (await id_node.inner_text()) or ""
                        raw_text = raw_text.strip()
                        if raw_text:
                            match = re.search(r"(\\u6296\\u97f3\\u53f7|\\u6296\\u97f3ID|\\u6296\\u97f3id)[:\\uff1a]?\\s*([A-Za-z0-9_.-]+)", raw_text)
                            if match:
                                user_info["user_id"] = match.group(2)
                            else:
                                raw_match = re.search(r"[A-Za-z0-9_.-]+", raw_text)
                                user_info["user_id"] = raw_match.group(0) if raw_match else raw_text
                except Exception:
                    pass

                if not user_info.get("user_id"):
                    body_text = await page.inner_text("body")
                    match = re.search(r"(\\u6296\\u97f3\\u53f7|\\u6296\\u97f3ID|\\u6296\\u97f3id)[:\\uff1a]?\\s*([A-Za-z0-9_.-]+)", body_text)
                    if match:
                        user_info["user_id"] = match.group(2)
                        logger.info(f"[Douyin] Extracted user_id from DOM text: {user_info['user_id']}")
            except Exception as e:
                logger.warning(f"[Douyin] DOM text extraction failed: {e}")

            # Method 2: JS fallback
            if not user_info.get("user_id"):
                try:
                    js_info = await page.evaluate("""() => {
                        if (window._ROUTER_DATA?.loaderData) {
                            for (let key in window._ROUTER_DATA.loaderData) {
                                const data = window._ROUTER_DATA.loaderData[key];
                                if (data?.user) return data.user;
                            }
                        }
                        if (window.userData) return window.userData;
                        return null;
                    }""")
                    logger.info(f"[Douyin] JS evaluated user data: {js_info}")
                    if js_info and isinstance(js_info, dict):
                        user_info["user_id"] = (
                            js_info.get("uniqueId")
                            or js_info.get("unique_id")
                            or js_info.get("userId")
                            or ""
                        )
                        logger.info(f"[Douyin] Fallback to JS userId: {user_info['user_id']}")
                except Exception as e:
                    logger.error(f"[Douyin] JS extraction failed: {e}")

            # name
            try:
                name_selectors = ['xpath=//div[@class="name-_lSSDc"]', 'div[class*="name-_lSSDc"]', 'div[class*="header-right-name"]', '.header-right-name']
                for selector in name_selectors:
                    try:
                        elem = await page.wait_for_selector(selector, timeout=2000)
                        if elem:
                            text = await elem.inner_text()
                            if text:
                                user_info["name"] = text.strip().split("\n")[0]
                                break
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"[Douyin] name extraction failed: {e}")

            # avatar
            try:
                avatar_selectors = ["div[class*='avatar-'] img", ".semi-avatar img", "img[src*='aweme-avatar']"]
                for selector in avatar_selectors:
                    try:
                        h = await page.query_selector(selector)
                        if h:
                            src = await h.get_attribute("src")
                            if src:
                                user_info["avatar"] = src
                                break
                    except Exception:
                        continue
            except Exception:
                pass

            logger.info(f"[Douyin] Final extracted user_info: {user_info}")
            return user_info
        except Exception as e:
            logger.error(f"账号解析失败: {e}")
            return {"name": "", "user_id": "", "avatar": ""}

    @staticmethod
    async def supports_api_login() -> bool: return True
    @staticmethod
    def get_sse_type() -> Optional[str]: return None


class KuaishouLoginService:
    """快手（Playwright扫码）"""
    @staticmethod
    async def get_qrcode() -> Tuple[str, str, str]:
        session_id = str(uuid.uuid4())
        page = await PlaywrightLoginManager.create_browser(session_id)
        try:
            await page.goto("https://cp.kuaishou.com/profile", timeout=60000)
            try:
                await page.get_by_role("link", name="立即登录").click(timeout=3000)
            except Exception:
                pass
            try:
                await page.get_by_text("扫码登录").click(timeout=3000)
            except Exception:
                pass
            img = page.get_by_role("img", name="qrcode")
            src = await img.get_attribute("src") if await img.count() > 0 else None
            if not src:
                await asyncio.sleep(2)
                src = await img.get_attribute("src") if await img.count() > 0 else None
            if src:
                return session_id, "https://cp.kuaishou.com/profile", src
            elem = await page.query_selector("img") or await page.query_selector("body")
            png = await elem.screenshot(type="png")
            return session_id, "https://cp.kuaishou.com/profile", _b64_png_from_buffer(png)
        except Exception as e:
            await PlaywrightLoginManager.cleanup_session(session_id)
            raise e

    @staticmethod
    async def poll_status(session_id: str) -> Dict[str, Any]:
        if session_id not in PLAYWRIGHT_SESSIONS:
            return {"status": "expired"}
        session = PLAYWRIGHT_SESSIONS[session_id]
        page = session["page"]
        try:
            if "cp.kuaishou.com/profile" in page.url and "login" not in page.url:
                cookies_list = await session["context"].cookies()
                cookies_dict = {c["name"]: c["value"] for c in cookies_list}
                try:
                    full_state = await session["context"].storage_state()
                except Exception as e:
                    logger.error(f"[KS] storage_state failed: {e}")
                    full_state = None
                user_info = await KuaishouLoginService.get_user_info_from_page(page, cookies_list, full_state)
                await PlaywrightLoginManager.cleanup_session(session_id)
                return {
                    "status": "confirmed",
                    "data": {
                        "cookies": cookies_dict,
                        "user_info": user_info,
                        "full_state": full_state
                    }
                }
            return {"status": "waiting"}
        except Exception as e:
            logger.error(f"快手poll失败: {e}")
            return {"status": "failed"}

    @staticmethod
    async def get_user_info_from_page(page: Any, cookies_list: list = None, full_state: Dict[str, Any] = None) -> Dict[str, Any]:
        """从页面提取快手用户信息（参考fetch_user_info_service：先DOM后cookie）"""
        try:
            await asyncio.sleep(1)
            user_info = {"name": "", "user_id": "", "avatar": ""}

            # ⚠️ 方法1: 优先从DOM文本提取快手号（最可靠！）
            try:
                import re
                # text=/快手号[:：]?\s*\w+/
                elem = await page.wait_for_selector('text=/快手号[:：]?\\s*\\w+/', timeout=3000)
                if elem:
                    text = await elem.inner_text()
                    match = re.search(r'快手号[:：]?\s*(\w+)', text)
                    if match:
                        user_info["user_id"] = match.group(1)
                        logger.info(f"[KS] Extracted user_id from DOM text: {user_info['user_id']}")
            except Exception as e:
                logger.warning(f"[KS] DOM text extraction failed: {e}")

            # 方法2: 从cookie提取（兜底，快手的userId cookie是正确的）
            if not user_info.get("user_id"):
                cookies = cookies_list or await page.context.cookies()
                for pref in ["userId", "kuaishou.user.id", "bUserId"]:
                    for c in cookies:
                        if c["name"] == pref and c.get("value"):
                            user_info["user_id"] = c["value"]
                            logger.info(f"[KS] Fallback to cookie {pref}: {user_info['user_id']}")
                            break
                    if user_info["user_id"]:
                        break

            # 方法3: 从JS提取name/avatar
            try:
                js_info = await page.evaluate("""() => {
                    if (window.__INITIAL_STATE__?.user) return window.__INITIAL_STATE__.user;
                    if (window.__INITIAL_STATE__?.userInfo) return window.__INITIAL_STATE__.userInfo;
                    if (window.userInfo) return window.userInfo;
                    return null;
                }""")
                if js_info and isinstance(js_info, dict):
                    user_info["name"] = js_info.get("name", js_info.get("userName", js_info.get("nickname", user_info["name"])))
                    user_info["avatar"] = js_info.get("avatar", js_info.get("headUrl", js_info.get("headurl", user_info["avatar"])))
            except Exception as e:
                logger.warning(f"快手JS用户信息失败: {e}")

            # 如果仍缺少 name，用user_id代替
            if not user_info["name"] and user_info.get("user_id"):
                user_info["name"] = user_info["user_id"]

            logger.info(f"[KS] Final extracted user_info: {user_info}")
            return user_info
        except Exception as e:
            logger.error(f"获取快手用户信息失败: {e}")
            return {"name": "快手用户", "user_id": "", "avatar": ""}

    @staticmethod
    async def supports_api_login() -> bool: return True
    @staticmethod
    def get_sse_type() -> Optional[str]: return None


class TencentLoginService:
    """视频号（Playwright扫码）"""
    @staticmethod
    async def get_qrcode() -> Tuple[str, str, str]:
        session_id = str(uuid.uuid4())
        page = await PlaywrightLoginManager.create_browser(session_id)
        try:
            await page.goto("https://channels.weixin.qq.com", timeout=60000)
            frame = page.frame_locator("iframe").first
            img = frame.get_by_role("img").first
            await asyncio.sleep(2)
            src = await img.get_attribute("src")
            if src:
                return session_id, "https://channels.weixin.qq.com", src
            png = await img.screenshot(type="png")
            return session_id, "https://channels.weixin.qq.com", _b64_png_from_buffer(png)
        except Exception as e:
            await PlaywrightLoginManager.cleanup_session(session_id)
            raise e

    @staticmethod
    async def poll_status(session_id: str) -> Dict[str, Any]:
        if session_id not in PLAYWRIGHT_SESSIONS:
            return {"status": "expired"}
        session = PLAYWRIGHT_SESSIONS[session_id]
        page = session["page"]
        try:
            cookies_list = await session["context"].cookies()
            if any(c["name"] in ["session_key", "ticket", "ticket_id", "wxuin", "uin", "finder_username"] for c in cookies_list):
                cookies_dict = {c["name"]: c["value"] for c in cookies_list}
                user_info = await TencentLoginService.get_user_info(page, cookies_list)
                try:
                    full_state = await session["context"].storage_state()
                except Exception as e:
                    logger.error(f"[Tencent] storage_state failed: {e}")
                    full_state = None
                await PlaywrightLoginManager.cleanup_session(session_id)
                return {
                    "status": "confirmed",
                    "data": {
                        "cookies": cookies_dict,
                        "user_info": user_info,
                        "full_state": full_state
                    }
                }
            return {"status": "waiting"}
        except Exception as e:
            logger.error(f"视频号poll失败: {e}")
            return {"status": "failed"}

    @staticmethod
    async def get_user_info(page: Any, cookies_list: list = None) -> Dict[str, Any]:
        try:
            await asyncio.sleep(1)
            user_info = {"name": "", "finder_username": "", "avatar": "", "user_id": ""}
            cookies = cookies_list or await page.context.cookies()
            for c in cookies:
                if c["name"] in ["wxuin", "uin", "finder_username"]:
                    user_info["finder_username"] = c["value"]
                    user_info["user_id"] = c["value"]
                    break
            try:
                js_info = await page.evaluate("""() => {
                    if (window.__INITIAL_STATE__?.userInfo) return window.__INITIAL_STATE__.userInfo;
                    if (window.userInfo) return window.userInfo;
                    if (window.__NEXT_DATA__?.props?.pageProps?.user) return window.__NEXT_DATA__.props.pageProps.user;
                    return null;
                }""")
                if js_info and isinstance(js_info, dict):
                    user_info["name"] = js_info.get("name", js_info.get("nickname", js_info.get("nickName", "")))
                    if not user_info["finder_username"]:
                        user_info["finder_username"] = js_info.get("finderUsername", js_info.get("finderId", ""))
                        user_info["user_id"] = user_info["finder_username"]
                    user_info["avatar"] = js_info.get("headImgUrl", js_info.get("avatar", ""))
            except Exception as e:
                logger.warning(f"从JS获取视频号用户信息失败: {e}")
            return user_info
        except Exception as e:
            logger.error(f"获取视频号用户信息失败: {e}")
            return {"name": "", "finder_username": "", "avatar": "", "user_id": ""}

    @staticmethod
    async def supports_api_login() -> bool: return True
    @staticmethod
    def get_sse_type() -> Optional[str]: return None


LOGIN_SERVICES = {
    PlatformType.BILIBILI: BilibiliLoginService,
    PlatformType.XIAOHONGSHU: XiaohongshuLoginService,
    PlatformType.DOUYIN: DouyinLoginService,
    PlatformType.KUAISHOU: KuaishouLoginService,
    PlatformType.TENCENT: TencentLoginService,
}


def get_login_service(platform: PlatformType):
    return LOGIN_SERVICES[platform]
