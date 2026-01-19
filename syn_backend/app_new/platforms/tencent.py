"""
Tencent (Weixin Channels) Platform Adapter - 视频号平台适配器

Playwright扫码实现
复制自: syn_backend/fastapi_app/api/v1/auth/services.py::TencentLoginService
"""
import asyncio
import uuid
from typing import Dict, Any

from loguru import logger
from playwright.async_api import async_playwright, Page
from myUtils.playwright_context_factory import create_context_with_policy

from .base import PlatformAdapter, QRCodeData, UserInfo, LoginResult, LoginStatus
from ..session_manager import tencent_session_manager


class TencentAdapter(PlatformAdapter):
    """视频号登录适配器 (Playwright扫码)"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.platform_name = "tencent"  # channels
        self.headless = config.get("headless", True) if config else True
        self.account_id = config.get("account_id") if config else None

    async def get_qrcode(self) -> QRCodeData:
        """
        生成视频号登录二维码

        访问: https://channels.weixin.qq.com
        提取二维码图片 (在iframe中)
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
            tencent_session_manager.create_session(session_id, {
                "playwright": playwright,
                "browser": browser,
                "context": context,
                "page": page
            })

            # 访问视频号平台
            await page.goto("https://channels.weixin.qq.com", timeout=60000)
            await asyncio.sleep(2)

            # 二维码在iframe中
            frame = page.frame_locator("iframe").first
            img = frame.get_by_role("img").first

            await asyncio.sleep(2)
            src = await img.get_attribute("src")

            if src:
                logger.info(f"[Tencent] QR code extracted: session={session_id[:8]}")
                return QRCodeData(
                    session_id=session_id,
                    qr_url="https://channels.weixin.qq.com",
                    qr_image=src,
                    expires_in=300
                )

            # 降级: 截图
            png = await img.screenshot(type="png")
            import base64
            b64 = base64.b64encode(png).decode("utf-8")

            logger.warning(f"[Tencent] QR not found, using screenshot: session={session_id[:8]}")
            return QRCodeData(
                session_id=session_id,
                qr_url="https://channels.weixin.qq.com",
                qr_image=f"data:image/png;base64,{b64}",
                expires_in=300
            )

        except Exception as e:
            await self.cleanup_session(session_id)
            logger.error(f"[Tencent] QR generation failed: {e}")
            raise

    async def poll_status(self, session_id: str) -> LoginResult:
        """
        轮询视频号登录状态

        判断标准:
        - 关键Cookie存在 (session_key, ticket, wxuin, uin, finder_username等)
        """
        # ✅ 使用 SessionManager 获取会话（内存优先，Redis 兜底）
        session = tencent_session_manager.get_session(session_id)
        if not session:
            return LoginResult(status=LoginStatus.EXPIRED, message="Session expired")

        page = session["page"]
        context = session["context"]

        try:
            cookies_list = await context.cookies()

            # 检查关键Cookie
            if any(c["name"] in ["session_key", "ticket", "ticket_id", "wxuin", "uin", "finder_username"] for c in cookies_list):
                # ⚠️ 关键修复：登录成功后主动导航到 /platform 页面，确保能看到 finder-uid-copy 元素
                logger.info(f"[Tencent] Login detected, navigating to platform page")
                try:
                    await page.goto("https://channels.weixin.qq.com/platform", timeout=10000, wait_until="domcontentloaded")
                    await asyncio.sleep(2)  # 等待页面加载
                except Exception as e:
                    logger.warning(f"[Tencent] Navigate to platform failed: {e}")

                cookies_dict = {c["name"]: c["value"] for c in cookies_list}

                # 提取用户信息
                user_info = await self._extract_user_info(page, cookies_list)

                try:
                    full_state = await context.storage_state()
                except Exception as e:
                    logger.error(f"[Tencent] storage_state failed: {e}")
                    full_state = None

                await self.cleanup_session(session_id)

                logger.info(f"[Tencent] Login confirmed: finder_username={user_info.user_id}")

                return LoginResult(
                    status=LoginStatus.CONFIRMED,
                    message="Login successful",
                    cookies=cookies_dict,
                    user_info=user_info,
                    full_state=full_state
                )

            return LoginResult(status=LoginStatus.WAITING, message="Waiting for scan")

        except Exception as e:
            logger.error(f"[Tencent] Poll failed: {e}")
            return LoginResult(status=LoginStatus.FAILED, message=str(e))

    async def cleanup_session(self, session_id: str):
        """清理Playwright会话"""
        # ✅ 使用 SessionManager 移除会话（内存 + Redis）
        session = tencent_session_manager.remove_session(session_id)
        if not session:
            return

        try:
            # ✅ 安全关闭 browser（检查是否为 None）
            browser = session.get("browser")
            if browser:
                await browser.close()
                logger.debug(f"[Tencent] Browser closed for session {session_id}")

            # ✅ 安全停止 playwright（检查是否为 None）
            playwright = session.get("playwright")
            if playwright:
                await playwright.stop()
                logger.debug(f"[Tencent] Playwright stopped for session {session_id}")
        except Exception as e:
            logger.warning(f"[Tencent] Cleanup failed: {e}")

    async def supports_api_login(self) -> bool:
        return False  # 需要Playwright

    # ========== Helper Methods ==========

    async def _extract_user_info(self, page: Page, cookies_list: list) -> UserInfo:
        """从页面提取用户信息（参考fetch_user_info_service的逻辑）"""
        try:
            # 等待页面完全加载
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=8000)
            except Exception:
                pass
            await asyncio.sleep(1)
            user_info = UserInfo()

            # 调试：记录当前页面URL
            logger.info(f"[Tencent] Current page URL: {page.url}")

            # ⚠️ 方法1: 优先从DOM元素提取真正的finder_username（最可靠！）
            # selectors: ['xpath=//span[@id="finder-uid-copy"]', '.finder-uniq-id-wrap span', '#finder-uid-copy']
            try:
                for selector in ['xpath=//span[@id="finder-uid-copy"]', '.finder-uniq-id-wrap span', '#finder-uid-copy']:
                    try:
                        logger.debug(f"[Tencent] Trying selector: {selector}")
                        elem = await page.wait_for_selector(selector, timeout=3000)
                        if elem:
                            user_id_text = await elem.inner_text()
                            logger.info(f"[Tencent] Found DOM element text: {user_id_text}")
                            if user_id_text and user_id_text.strip():
                                user_info.user_id = user_id_text.strip()
                                user_info.extra = {"finder_username": user_id_text.strip()}
                                logger.info(f"[Tencent] Extracted user_id from DOM: {user_info.user_id}")
                                break
                    except Exception as e:
                        logger.debug(f"[Tencent] Selector {selector} failed: {e}")
                        continue
            except Exception as e:
                logger.warning(f"[Tencent] DOM extraction failed: {e}")

            # 方法2: 从JS全局变量提取（补全 name/avatar；user_id 仅在缺失时使用，避免覆盖 DOM 提取的 finder-uid）
            try:
                js_info = await page.evaluate("""() => {
                    if (window.__INITIAL_STATE__?.userInfo) return window.__INITIAL_STATE__.userInfo;
                    if (window.userInfo) return window.userInfo;
                    if (window.__NEXT_DATA__?.props?.pageProps?.user) return window.__NEXT_DATA__.props.pageProps.user;
                    return null;
                }""")

                if js_info and isinstance(js_info, dict):
                    if not user_info.user_id:
                        finder_username = js_info.get("finderUsername", js_info.get("finderId", ""))
                        if finder_username:
                            user_info.user_id = finder_username
                            user_info.extra = {"finder_username": finder_username}
                            logger.info(f"[Tencent] Fallback to JS finderUsername: {user_info.user_id}")

                    if not user_info.name:
                        user_info.name = js_info.get("name", js_info.get("nickname", js_info.get("nickName", "")))
                    if not user_info.avatar:
                        user_info.avatar = js_info.get("headImgUrl", js_info.get("avatar", ""))
            except Exception as e:
                logger.warning(f"[Tencent] JS user info failed: {e}")

            # 方法2.5: 从DOM提取昵称/头像（JS 取不到时常见）
            if not user_info.name:
                for selector in [".finder-nickname", ".nickname", ".name", "span[class*='nickname']", "div[class*='nickname']"]:
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

            # 方法2.6: 再兜底一次（避免 .name 命中无关元素）
            if not user_info.name:
                try:
                    candidate = await page.evaluate(
                        """() => {
                          const sels = [
                            '.finder-nickname',
                            '.finder-username',
                            '[data-testid*=\"nickname\"]',
                            'header [class*=\"nickname\"]',
                            'header [class*=\"name\"]',
                          ];
                          for (const sel of sels) {
                            const el = document.querySelector(sel);
                            if (!el) continue;
                            const t = (el.textContent || '').trim();
                            if (t && t.length >= 2 && t.length <= 64) return t.split('\\n')[0].trim();
                          }
                          const title = (document.title || '').trim();
                          if (title && !title.includes('视频号') && title.length <= 64) return title;
                          return '';
                        }"""
                    )
                    if isinstance(candidate, str) and candidate.strip():
                        user_info.name = candidate.strip()
                except Exception:
                    pass

            if not user_info.avatar:
                for selector in [".finder-avatar img", ".avatar img", "img[src*='head']", "img[class*='avatar']"]:
                    try:
                        img = await page.query_selector(selector)
                        if img:
                            src = await img.get_attribute("src")
                            if src and src.strip():
                                user_info.avatar = src.strip()
                                break
                    except Exception:
                        continue

            if not user_info.avatar:
                try:
                    candidate = await page.evaluate(
                        """() => {
                          const imgs = Array.from(document.images || []);
                          for (const img of imgs) {
                            const src = (img.currentSrc || img.src || '').trim();
                            if (!src) continue;
                            if (src.startsWith('data:')) continue;
                            const alt = (img.alt || '').trim();
                            const cls = (img.className || '').toString();
                            if (/avatar|head|portrait|finder/i.test(src) || /头像|avatar|head/i.test(alt) || /avatar|head/i.test(cls)) {
                              return src;
                            }
                          }
                          return '';
                        }"""
                    )
                    if isinstance(candidate, str) and candidate.strip():
                        user_info.avatar = candidate.strip()
                except Exception:
                    pass

            # 方法3: 从Cookie提取（最后兜底，注意这些是数字ID不是真正的finder_username）
            if not user_info.user_id:
                for c in cookies_list:
                    if c["name"] in ["wxuin", "uin", "finder_username"]:
                        user_info.user_id = c["value"]
                        user_info.extra = {"finder_username": c["value"]}
                        logger.warning(f"[Tencent] Fallback to cookie (may be numeric ID): {user_info.user_id}")
                        break

            # 兜底：若昵称仍为空且 user_id 可用，至少不要返回 None
            if not user_info.name and user_info.user_id:
                user_info.name = str(user_info.user_id)

            logger.info(f"[Tencent] Final extracted user_info: user_id={user_info.user_id}, name={user_info.name}")
            return user_info

        except Exception as e:
            logger.error(f"[Tencent] Extract user info failed: {e}")
            return UserInfo()
