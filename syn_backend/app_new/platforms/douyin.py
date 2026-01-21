"""
Douyin Platform Adapter - 抖音平台适配器

Playwright扫码实现
复制自: syn_backend/fastapi_app/api/v1/auth/services.py::DouyinLoginService
"""
import asyncio
import uuid
from typing import Dict, Any

from loguru import logger
from playwright.async_api import async_playwright, Page
from myUtils.playwright_context_factory import create_context_with_policy

from .base import PlatformAdapter, QRCodeData, UserInfo, LoginResult, LoginStatus
from ..session_manager import douyin_session_manager


class DouyinAdapter(PlatformAdapter):
    """抖音登录适配器 (Playwright扫码)"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.platform_name = "douyin"
        self.headless = config.get("headless", True) if config else True
        self.account_id = config.get("account_id") if config else None

    async def get_qrcode(self) -> QRCodeData:
        """
        生成抖音登录二维码

        访问: https://creator.douyin.com/creator-micro/login?enter_from=qr
        提取二维码图片
        """
        session_id = str(uuid.uuid4())

        try:
            # 创建浏览器会话
            playwright = await async_playwright().start()
            browser, context, _, _ = await create_context_with_policy(
                playwright,
                platform=self.platform_name,
                account_id=self.account_id,
                headless=self.headless,
                base_context_opts={"viewport": {"width": 1280, "height": 800}},
                launch_kwargs={"args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]},
            )
            page = await context.new_page()

            # ✅ 使用 SessionManager 存储会话（内存 + Redis）
            douyin_session_manager.create_session(session_id, {
                "playwright": playwright,
                "browser": browser,
                "context": context,
                "page": page
            })

            # 访问登录页
            try:
                await page.goto(
                    "https://creator.douyin.com/creator-micro/login?enter_from=qr",
                    timeout=20000,
                    wait_until="domcontentloaded"
                )
            except Exception:
                # 降级: 访问主页
                await page.goto("https://creator.douyin.com/", timeout=20000, wait_until="domcontentloaded")

            # 等待二维码加载
            await asyncio.sleep(2)

            # 尝试多个选择器提取二维码
            qr_xpath = "//div[@id='animate_qrcode_container']//img[contains(@class,'qrcode_img')]"
            try:
                h = await page.wait_for_selector(f"xpath={qr_xpath}", timeout=15000)
                if h:
                    src = await h.get_attribute("src")
                    if src:
                        logger.info(f"[Douyin] QR code extracted: session={session_id[:8]}")
                        return QRCodeData(
                            session_id=session_id,
                            qr_url="https://creator.douyin.com/",
                            qr_image=src,
                            expires_in=300
                        )
            except Exception as e:
                logger.warning(f"[Douyin] XPath selector failed: {e}")

            # 备用选择器
            selectors = [
                "img.qrcode_img-NPVTJs",
                "div.qrcode-vz0gH7 img",
                "img[alt*='二维码']",
                "img[src*='qrcode']",
                ".qrcode img",
            ]

            for sel in selectors:
                try:
                    h = await page.query_selector(sel)
                    if h:
                        src = await h.get_attribute("src")
                        if src:
                            logger.info(f"[Douyin] QR code extracted: session={session_id[:8]}")
                            return QRCodeData(
                                session_id=session_id,
                                qr_url="https://creator.douyin.com/",
                                qr_image=src,
                                expires_in=300
                            )
                except Exception:
                    continue

            # 最后兜底: 截图整页
            try:
                shot = await page.screenshot(full_page=False)
                if shot:
                    import base64
                    b64 = base64.b64encode(shot).decode("utf-8")
                    logger.warning(f"[Douyin] QR not found, using screenshot: session={session_id[:8]}")
                    return QRCodeData(
                        session_id=session_id,
                        qr_url="https://creator.douyin.com/",
                        qr_image=f"data:image/png;base64,{b64}",
                        expires_in=300
                    )
            except Exception:
                pass

            raise Exception("No QR code found for Douyin")

        except Exception as e:
            await self.cleanup_session(session_id)
            logger.error(f"[Douyin] QR generation failed: {e}")
            raise

    async def poll_status(self, session_id: str) -> LoginResult:
        """
        轮询抖音登录状态

        判断标准:
        - URL不包含 'login'
        - 关键Cookie存在 (sessionid, sid_guard等)
        - 可提取用户信息
        """
        # ✅ 使用 SessionManager 获取会话（内存优先，Redis 兜底）
        session = douyin_session_manager.get_session(session_id)
        if not session:
            return LoginResult(status=LoginStatus.EXPIRED, message="Session expired")

        page = session["page"]
        context = session["context"]

        try:
            cookies_list = await context.cookies()
            cookies_dict = {c["name"]: c["value"] for c in cookies_list}

            # 检查关键Cookie
            auth_cookies = {
                k: v for k, v in cookies_dict.items()
                if k in ["sessionid", "sessionid_ss", "sid_guard", "sid_tt", "passport_auth_id", "odin_tt"]
                and v
            }

            # 检查URL状态
            is_on_creator = "creator.douyin.com" in page.url
            on_login_page = "login" in page.url.lower()

            # 提取用户信息
            user_info = await self._extract_user_info(page, cookies_list)
            has_user = bool(user_info.user_id)

            # 判断登录成功
            if is_on_creator and not on_login_page and (auth_cookies or has_user):
                try:
                    full_state = await context.storage_state()
                except Exception as e:
                    logger.error(f"[Douyin] storage_state failed: {e}")
                    full_state = None

                await self.cleanup_session(session_id)

                logger.info(f"[Douyin] Login confirmed: uid={user_info.user_id}")

                return LoginResult(
                    status=LoginStatus.CONFIRMED,
                    message="Login successful",
                    cookies=cookies_dict,
                    user_info=user_info,
                    full_state=full_state
                )

            return LoginResult(status=LoginStatus.WAITING, message="Waiting for scan")

        except Exception as e:
            logger.error(f"[Douyin] Poll failed: {e}")
            return LoginResult(status=LoginStatus.FAILED, message=str(e))

    async def cleanup_session(self, session_id: str):
        """清理Playwright会话"""
        # ✅ 使用 SessionManager 移除会话（内存 + Redis）
        session = douyin_session_manager.remove_session(session_id)
        if not session:
            return

        try:
            # ✅ 安全关闭 browser（检查是否为 None）
            browser = session.get("browser")
            if browser:
                await browser.close()
                logger.debug(f"[Douyin] Browser closed for session {session_id}")

            # ✅ 安全停止 playwright（检查是否为 None）
            playwright = session.get("playwright")
            if playwright:
                await playwright.stop()
                logger.debug(f"[Douyin] Playwright stopped for session {session_id}")
        except Exception as e:
            logger.warning(f"[Douyin] Cleanup failed: {e}")

    async def supports_api_login(self) -> bool:
        return False  # 需要Playwright

    # ========== Helper Methods ==========

    async def _extract_user_info(self, page: Page, cookies_list: list) -> UserInfo:
        """Extract user info from page (DOM + JS)."""
        try:
            await asyncio.sleep(1)
            user_info = UserInfo()

            # Method 1: DOM text
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
                                user_info.user_id = match.group(2)
                            else:
                                raw_match = re.search(r"[A-Za-z0-9_.-]+", raw_text)
                                user_info.user_id = raw_match.group(0) if raw_match else raw_text
                except Exception:
                    pass

                if not user_info.user_id:
                    body_text = await page.inner_text("body")
                    match = re.search(r"(\\u6296\\u97f3\\u53f7|\\u6296\\u97f3ID|\\u6296\\u97f3id)[:\\uff1a]?\\s*([A-Za-z0-9_.-]+)", body_text)
                    if match:
                        user_info.user_id = match.group(2)
                        logger.info(f"[Douyin] Extracted user_id from DOM text: {user_info.user_id}")
            except Exception as e:
                logger.warning(f"[Douyin] DOM text extraction failed: {e}")

            # Method 2: JS fallback
            if not user_info.user_id:
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
                    if js_info and isinstance(js_info, dict):
                        user_info.user_id = (
                            js_info.get("uniqueId")
                            or js_info.get("unique_id")
                            or js_info.get("userId")
                            or ""
                        )
                        logger.info(f"[Douyin] Fallback to JS userId: {user_info.user_id}")
                except Exception as e:
                    logger.warning(f"[Douyin] JS user info failed: {e}")

            # name
            if not user_info.name:
                try:
                    name_selectors = ['xpath=//div[@class="name-_lSSDc"]', 'div[class*="name-_lSSDc"]', 'div[class*="header-right-name"]', '.header-right-name']
                    for selector in name_selectors:
                        try:
                            elem = await page.wait_for_selector(selector, timeout=2000)
                            if elem:
                                text = await elem.inner_text()
                                if text:
                                    user_info.name = text.strip().split("\n")[0]
                                    break
                        except Exception:
                            continue
                except Exception as e:
                    logger.warning(f"[Douyin] name extraction failed: {e}")

            # avatar
            if not user_info.avatar:
                try:
                    for sel in ["div[class*='avatar-'] img", ".semi-avatar img", "img[src*='aweme-avatar']"]:
                        h = await page.query_selector(sel)
                        if h:
                            src = await h.get_attribute("src")
                            if src:
                                user_info.avatar = src
                                break
                except Exception:
                    pass

            logger.info(f"[Douyin] Final extracted user_info: user_id={user_info.user_id}, name={user_info.name}")
            return user_info

        except Exception as e:
            logger.error(f"[Douyin] Extract user info failed: {e}")
            return UserInfo()

