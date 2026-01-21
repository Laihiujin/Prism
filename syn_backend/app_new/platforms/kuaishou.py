"""
Kuaishou Platform Adapter - 快手平台适配器

Playwright扫码实现
复制自: syn_backend/fastapi_app/api/v1/auth/services.py::KuaishouLoginService
"""
import asyncio
import uuid
from typing import Dict, Any

from loguru import logger
from playwright.async_api import async_playwright, Page
from myUtils.playwright_context_factory import create_context_with_policy

from .base import PlatformAdapter, QRCodeData, UserInfo, LoginResult, LoginStatus
from ..session_manager import kuaishou_session_manager


class KuaishouAdapter(PlatformAdapter):
    """快手登录适配器 (Playwright扫码)"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.platform_name = "kuaishou"
        self.headless = config.get("headless", True) if config else True
        self.account_id = config.get("account_id") if config else None

    async def get_qrcode(self) -> QRCodeData:
        """
        生成快手登录二维码

        访问: https://cp.kuaishou.com/profile
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
            kuaishou_session_manager.create_session(session_id, {
                "playwright": playwright,
                "browser": browser,
                "context": context,
                "page": page
            })

            # 访问快手创作者中心
            await page.goto("https://cp.kuaishou.com/profile", timeout=60000)

            # 尝试点击登录按钮
            try:
                await page.get_by_role("link", name="立即登录").click(timeout=3000)
            except Exception:
                pass

            # 切换到扫码登录
            try:
                await page.get_by_text("扫码登录").click(timeout=3000)
            except Exception:
                pass

            # 等待二维码加载
            await asyncio.sleep(2)

            # 提取二维码
            img = page.get_by_role("img", name="qrcode")
            src = await img.get_attribute("src") if await img.count() > 0 else None

            if not src:
                await asyncio.sleep(2)
                src = await img.get_attribute("src") if await img.count() > 0 else None

            if src:
                logger.info(f"[Kuaishou] QR code extracted: session={session_id[:8]}")
                return QRCodeData(
                    session_id=session_id,
                    qr_url="https://cp.kuaishou.com/profile",
                    qr_image=src,
                    expires_in=300
                )

            # 降级: 截图
            elem = await page.query_selector("img") or await page.query_selector("body")
            png = await elem.screenshot(type="png")
            import base64
            b64 = base64.b64encode(png).decode("utf-8")

            logger.warning(f"[Kuaishou] QR not found, using screenshot: session={session_id[:8]}")
            return QRCodeData(
                session_id=session_id,
                qr_url="https://cp.kuaishou.com/profile",
                qr_image=f"data:image/png;base64,{b64}",
                expires_in=300
            )

        except Exception as e:
            await self.cleanup_session(session_id)
            logger.error(f"[Kuaishou] QR generation failed: {e}")
            raise

    async def poll_status(self, session_id: str) -> LoginResult:
        """
        轮询快手登录状态

        判断标准:
        - URL为 cp.kuaishou.com/profile 且不含 'login'
        """
        # ✅ 使用 SessionManager 获取会话（内存优先，Redis 兜底）
        session = kuaishou_session_manager.get_session(session_id)
        if not session:
            return LoginResult(status=LoginStatus.EXPIRED, message="Session expired")

        page = session["page"]
        context = session["context"]

        try:
            # 检查URL状态
            if "cp.kuaishou.com" in page.url and "login" not in page.url:
                # ⚠️ 关键修复：登录成功后主动导航到 /profile 页面，确保能看到"快手号"文本
                if "cp.kuaishou.com/profile" not in page.url:
                    logger.info(f"[Kuaishou] Login detected, navigating to profile page")
                    try:
                        await page.goto("https://cp.kuaishou.com/profile", timeout=10000, wait_until="domcontentloaded")
                        await asyncio.sleep(2)  # 等待页面加载
                    except Exception as e:
                        logger.warning(f"[Kuaishou] Navigate to profile failed: {e}")

                cookies_list = await context.cookies()
                cookies_dict = {c["name"]: c["value"] for c in cookies_list}

                try:
                    full_state = await context.storage_state()
                except Exception as e:
                    logger.error(f"[Kuaishou] storage_state failed: {e}")
                    full_state = None

                # 提取用户信息
                user_info = await self._extract_user_info(page, cookies_list, full_state)

                await self.cleanup_session(session_id)

                logger.info(f"[Kuaishou] Login confirmed: uid={user_info.user_id}")

                return LoginResult(
                    status=LoginStatus.CONFIRMED,
                    message="Login successful",
                    cookies=cookies_dict,
                    user_info=user_info,
                    full_state=full_state
                )

            return LoginResult(status=LoginStatus.WAITING, message="Waiting for scan")

        except Exception as e:
            logger.error(f"[Kuaishou] Poll failed: {e}")
            return LoginResult(status=LoginStatus.FAILED, message=str(e))

    async def cleanup_session(self, session_id: str):
        """清理Playwright会话"""
        # ✅ 使用 SessionManager 移除会话（内存 + Redis）
        session = kuaishou_session_manager.remove_session(session_id)
        if not session:
            return

        try:
            # ✅ 安全关闭 browser（检查是否为 None）
            browser = session.get("browser")
            if browser:
                await browser.close()
                logger.debug(f"[Kuaishou] Browser closed for session {session_id}")

            # ✅ 安全停止 playwright（检查是否为 None）
            playwright = session.get("playwright")
            if playwright:
                await playwright.stop()
                logger.debug(f"[Kuaishou] Playwright stopped for session {session_id}")
        except Exception as e:
            logger.warning(f"[Kuaishou] Cleanup failed: {e}")

    async def supports_api_login(self) -> bool:
        return False  # 需要Playwright

    # ========== Helper Methods ==========

    async def _extract_user_info(self, page: Page, cookies_list: list, full_state: Dict = None) -> UserInfo:
        """从页面提取用户信息（参考fetch_user_info_service：先DOM后cookie）"""
        try:
            # 等待页面完全加载
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=8000)
            except Exception:
                pass
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            await asyncio.sleep(1)
            user_info = UserInfo()

            # 调试：记录当前页面URL
            logger.info(f"[Kuaishou] Current page URL: {page.url}")

            # ⚠️ 方法1: 优先从DOM文本提取快手号（最可靠！）
            try:
                import re
                # text=/快手号[:：]?\s*\w+/
                logger.info("[Kuaishou] Attempting DOM text extraction (no wait)...")
                elem = await page.query_selector('text=/快手号[:：]?\\s*[\\w-]+/')
                if elem:
                    text = await elem.inner_text()
                    logger.info(f"[Kuaishou] Found DOM text: {text}")
                    match = re.search(r'快手号[:：]?\s*([\\w-]+)', text)
                    if match:
                        user_info.user_id = match.group(1)
                        logger.info(f"[Kuaishou] Extracted user_id from DOM text: {user_info.user_id}")
            except Exception as e:
                logger.warning(f"[Kuaishou] DOM text extraction failed: {e}")
                # 调试：检查页面是否有"快手号"文本
                try:
                    page_content = await page.content()
                    if "快手号" in page_content:
                        logger.warning(f"[Kuaishou] Page contains '快手号' text, but selector timed out - may need different selector")
                    else:
                        logger.warning(f"[Kuaishou] Page does NOT contain '快手号' text - may not be on profile page yet")
                except Exception:
                    pass

            # 方法2: 从cookie提取（兜底，快手的userId cookie是正确的）
            if not user_info.user_id:
                for pref in ["userId", "kuaishou.user.id", "bUserId"]:
                    for c in cookies_list:
                        if c["name"] == pref and c.get("value"):
                            user_info.user_id = c["value"]
                            logger.info(f"[Kuaishou] Fallback to cookie {pref}: {user_info.user_id}")
                            break
                    if user_info.user_id:
                        break

            # 方法3: 从JS全局变量提取name/avatar
            try:
                js_info = await page.evaluate("""() => {
                    if (window.__INITIAL_STATE__?.user) return window.__INITIAL_STATE__.user;
                    if (window.__INITIAL_STATE__?.userInfo) return window.__INITIAL_STATE__.userInfo;
                    if (window.userInfo) return window.userInfo;
                    return null;
                }""")

                if js_info and isinstance(js_info, dict):
                    user_info.name = js_info.get("name", js_info.get("userName", js_info.get("nickname", user_info.name or "")))
                    user_info.avatar = js_info.get("avatar", js_info.get("headUrl", js_info.get("headurl", user_info.avatar or "")))
            except Exception as e:
                logger.warning(f"[Kuaishou] JS user info failed: {e}")

            # 方法3.5: 从DOM提取昵称/头像（JS 取不到时常见）
            if not user_info.name or (user_info.user_id and user_info.name == user_info.user_id):
                for selector in [".user-info-name", "section.header-bar .user-info-name", "div[class*='user-info-name']", "span[class*='name']"]:
                    try:
                        h = await page.query_selector(selector)
                        if h:
                            text = (await h.inner_text()) or ""
                            text = text.strip()
                            if text:
                                user_info.name = text.split("\n")[0].strip()
                                break
                    except Exception:
                        continue

            if not user_info.avatar:
                for selector in ["section.header-bar .user-info-avatar img", "div[class*='user-info-avatar'] img", ".avatar-wrapper img", "img[class*='avatar']"]:
                    try:
                        img = await page.query_selector(selector)
                        if img:
                            src = await img.get_attribute("src")
                            if src and src.strip():
                                user_info.avatar = src.strip()
                                break
                    except Exception:
                        continue

            if not user_info.name or (user_info.user_id and user_info.name == user_info.user_id):
                try:
                    candidate = await page.evaluate(
                        """() => {
                          const sels = [
                            '.user-info-name',
                            'section.header-bar .user-info-name',
                            '[class*=\"user-info-name\"]',
                            '[class*=\"nickname\"]',
                            '[class*=\"userName\"]',
                            'header [class*=\"name\"]',
                          ];
                          for (const sel of sels) {
                            const el = document.querySelector(sel);
                            if (!el) continue;
                            const t = (el.textContent || '').trim();
                            if (t && t.length >= 2 && t.length <= 64) return t.split('\\n')[0].trim();
                          }
                          const title = (document.title || '').trim();
                          if (title && title.length <= 64) return title;
                          return '';
                        }"""
                    )
                    if isinstance(candidate, str) and candidate.strip():
                        user_info.name = candidate.strip()
                except Exception:
                    pass

            # 如果name仍为空,使用user_id作为name
            if not user_info.name and user_info.user_id:
                user_info.name = user_info.user_id

            logger.info(f"[Kuaishou] Final extracted user_info: user_id={user_info.user_id}, name={user_info.name}")
            return user_info

        except Exception as e:
            logger.error(f"[Kuaishou] Extract user info failed: {e}")
            return UserInfo()
