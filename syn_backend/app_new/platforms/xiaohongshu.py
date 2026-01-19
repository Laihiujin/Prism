"""
Xiaohongshu Platform Adapter - 小红书平台适配器

Playwright扫码实现
复制自: syn_backend/fastapi_app/api/v1/auth/services.py::XiaohongshuLoginService
"""
import asyncio
import uuid
from typing import Dict, Any

from loguru import logger
from playwright.async_api import async_playwright, Page
from myUtils.playwright_context_factory import create_context_with_policy

from .base import PlatformAdapter, QRCodeData, UserInfo, LoginResult, LoginStatus
from ..session_manager import xiaohongshu_session_manager


class XiaohongshuAdapter(PlatformAdapter):
    """小红书登录适配器 (Playwright扫码)"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.platform_name = "xiaohongshu"
        self.headless = config.get("headless", True) if config else True
        self.account_id = config.get("account_id") if config else None

    async def get_qrcode(self) -> QRCodeData:
        """
        生成小红书登录二维码

        访问: https://creator.xiaohongshu.com/new/home
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
            xiaohongshu_session_manager.create_session(session_id, {
                "playwright": playwright,
                "browser": browser,
                "context": context,
                "page": page
            })

            # 访问小红书创作者中心
            await page.goto("https://creator.xiaohongshu.com/new/home", timeout=60000)
            await asyncio.sleep(2)

            # 尝试切换到扫码登录
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

            # 尝试多个选择器提取二维码
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
                            logger.info(f"[XHS] QR code extracted: session={session_id[:8]}")
                            return QRCodeData(
                                session_id=session_id,
                                qr_url="https://creator.xiaohongshu.com/new/home",
                                qr_image=src,
                                expires_in=300
                            )
                except Exception:
                    continue

            # 兜底: 截图登录框
            try:
                box = await page.query_selector(".login-box-container") or await page.query_selector("body")
                if box:
                    png = await box.screenshot(type="png")
                    import base64
                    b64 = base64.b64encode(png).decode("utf-8")
                    logger.warning(f"[XHS] QR not found, using screenshot: session={session_id[:8]}")
                    return QRCodeData(
                        session_id=session_id,
                        qr_url="https://creator.xiaohongshu.com/new/home",
                        qr_image=f"data:image/png;base64,{b64}",
                        expires_in=300
                    )
            except Exception:
                pass

            raise Exception("No QR code found for Xiaohongshu")

        except Exception as e:
            await self.cleanup_session(session_id)
            logger.error(f"[XHS] QR generation failed: {e}")
            raise

    async def poll_status(self, session_id: str) -> LoginResult:
        """
        轮询小红书登录状态

        判断标准:
        - 关键Cookie存在 (web_session, xhsuid, customer-sso-sid等)
        - URL不含 'login'
        """
        # ✅ 使用 SessionManager 获取会话（内存优先，Redis 兜底）
        session = xiaohongshu_session_manager.get_session(session_id)
        if not session:
            return LoginResult(status=LoginStatus.EXPIRED, message="Session expired")

        page = session["page"]
        context = session["context"]

        try:
            cookies = await context.cookies()
            cookie_names = [c["name"] for c in cookies]

            logger.debug(f"[XHS] poll cookies: {cookie_names}, url={page.url}")

            # 检查关键Cookie
            if (
                any(c["name"] in ["web_session", "xhsuid", "customer-sso-sid", "a1", "webId"] for c in cookies)
                and "login" not in page.url.lower()
            ):
                cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

                # 提取用户信息
                user_info = await self._extract_user_info(page, cookies)

                try:
                    full_state = await context.storage_state()
                except Exception as e:
                    logger.error(f"[XHS] storage_state failed: {e}")
                    full_state = None

                await self.cleanup_session(session_id)

                logger.info(f"[XHS] Login confirmed: uid={user_info.user_id}")

                return LoginResult(
                    status=LoginStatus.CONFIRMED,
                    message="Login successful",
                    cookies={"cookie": cookie_str},
                    user_info=user_info,
                    full_state=full_state
                )

            return LoginResult(status=LoginStatus.WAITING, message="Waiting for scan")

        except Exception as e:
            logger.error(f"[XHS] Poll failed: {e}")
            return LoginResult(status=LoginStatus.FAILED, message=str(e))

    async def cleanup_session(self, session_id: str):
        """清理Playwright会话"""
        # ✅ 使用 SessionManager 移除会话（内存 + Redis）
        session = xiaohongshu_session_manager.remove_session(session_id)
        if not session:
            return

        try:
            # ✅ 安全关闭 browser（检查是否为 None）
            browser = session.get("browser")
            if browser:
                await browser.close()
                logger.debug(f"[XHS] Browser closed for session {session_id}")

            # ✅ 安全停止 playwright（检查是否为 None）
            playwright = session.get("playwright")
            if playwright:
                await playwright.stop()
                logger.debug(f"[XHS] Playwright stopped for session {session_id}")
        except Exception as e:
            logger.warning(f"[XHS] Cleanup failed: {e}")

    async def supports_api_login(self) -> bool:
        return False  # 需要Playwright

    # ========== Helper Methods ==========

    async def _extract_user_info(self, page: Page, cookies_list: list) -> UserInfo:
        """从页面提取用户信息（参考fetch_user_info_service的逻辑）"""
        try:
            await asyncio.sleep(1)
            user_info = UserInfo()

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

            # ⚠️ 方法1: 优先从DOM文本提取"小红书账号/小红书号"（更接近你原先要的账号ID，避免拿到内部 numeric id）
            if not user_info.user_id:
                try:
                    import re

                    # ✅ 根据实际DOM结构调整选择器：div.personal 内的 .description-text
                    selectors_to_try = [
                        'div.personal .description-text',  # 优先：定位到 personal 区域内的 description-text
                        '.description-text div',  # 备选1：description-text下的div（直接包含文本）
                        '.description-text',  # 备选2：description-text本身
                        'text=/小红书账号[:：]?\\s*[\\w_]+/',  # 备选3：通用文本匹配
                    ]

                    patterns = [
                        r"小红书账号[:：]?\s*([\w_]+)",  # 主要模式
                        r"小红书号[:：]?\s*([\w_]+)",    # 备用模式
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
                                    if candidate and 3 <= len(candidate) <= 30:
                                        user_info.user_id = candidate
                                        logger.info(f"[XHS] Extracted user_id from DOM text (selector={selector}): {user_info.user_id}")
                                        break

                            if user_info.user_id:
                                break
                        except Exception as e:
                            logger.debug(f"[XHS] Selector {selector} failed: {e}")
                            continue
                except Exception as e:
                    logger.warning(f"[XHS] DOM user_id extraction failed: {e}")

            # 方法2: 从JS全局变量提取（兜底）
            if not user_info.user_id:
                try:
                    js_info = await page.evaluate("""() => {
                        if (window.__INITIAL_SSR_STATE__?.Main?.user) return window.__INITIAL_SSR_STATE__.Main.user;
                        if (window.userInfo) return window.userInfo;
                        if (window.__INITIAL_STATE__?.user) return window.__INITIAL_STATE__.user;
                        return null;
                    }""")

                    if js_info and isinstance(js_info, dict):
                        # 与旧版 services.py 保持一致：JS 兜底只拿 user_id，name/avatar 走 DOM 选择器
                        user_info.user_id = js_info.get("redId", js_info.get("red_id", js_info.get("userId", js_info.get("id", ""))))
                        logger.info(f"[XHS] Fallback to JS userId: {user_info.user_id}")
                except Exception as e:
                    logger.warning(f"[XHS] JS user info failed: {e}")

            # 方法3: 从 cookie 提取 user_id（最后兜底：可能是内部 id，但总比空强）
            if not user_info.user_id:
                try:
                    for c in cookies_list:
                        if c.get("name") == "x-user-id-creator.xiaohongshu.com" and c.get("value"):
                            user_info.user_id = str(c.get("value"))
                            logger.info(f"[XHS] Fallback to cookie x-user-id: {user_info.user_id}")
                            break
                except Exception:
                    pass

            # 方法4: 再兜底一次泛“账号”文本（容易误匹配，因此放最后且加过滤）
            if not user_info.user_id:
                try:
                    import re

                    elem = await page.wait_for_selector('text=/账号[:：]?\\s*[\\w_]+/', timeout=1500)
                    if elem:
                        text = (await elem.inner_text()) or ""
                        text = text.strip()
                        match = re.search(r'账号[:：]?\s*([\w_]+)', text)
                        if match:
                            candidate = match.group(1).strip()
                            if candidate and len(candidate) >= 3 and candidate not in {"管理", "设置"}:
                                user_info.user_id = candidate
                                logger.info(f"[XHS] Fallback extracted user_id from generic DOM: {user_info.user_id}")
                except Exception:
                    pass

            # 从DOM提取名称
            if not user_info.name:
                try:
                    name_selectors = ['.base .text .account-name', '.account-name', '.user-name', ".user-name", ".name", "span[class*='name']"]
                    for selector in name_selectors:
                        try:
                            h = await page.query_selector(selector)
                            if h:
                                text = await h.inner_text()
                                if text and text.strip():
                                    user_info.name = text.strip().split("\n")[0]
                                    break
                        except:
                            continue
                except Exception:
                    pass

            # 从DOM提取头像
            if not user_info.avatar:
                try:
                    avatar_selectors = ['.base .avatar img', '.avatar img', 'img[alt*="头像"]', "img[class*='avatar']"]
                    for selector in avatar_selectors:
                        try:
                            h = await page.query_selector(selector)
                            if h:
                                src = await h.get_attribute("src")
                                if src:
                                    user_info.avatar = src
                                    break
                        except:
                            continue
                except Exception:
                    pass

            # 兜底: 使用user_id作为name
            if not user_info.name and user_info.user_id:
                user_info.name = user_info.user_id

            logger.info(f"[XHS] Final extracted user_info: user_id={user_info.user_id}, name={user_info.name}")
            return user_info

        except Exception as e:
            logger.error(f"[XHS] Extract user info failed: {e}")
            return UserInfo()
