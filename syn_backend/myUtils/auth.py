import asyncio
import sys
import os
import time
import contextlib
from pathlib import Path
from playwright.async_api import async_playwright
from loguru import logger
from myUtils.playwright_context_factory import create_context_with_policy
from myUtils.cookie_manager import cookie_manager

# 添加父目录到 Python 路径
sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

# Define BASE_DIR locally
BASE_DIR = Path(__file__).parent.parent

try:
    from utils.base_social_media import set_init_script, HEADLESS_FLAG
except ImportError:
    # Fallback if utils module not available
    HEADLESS_FLAG = True
    def set_init_script(page):
        pass


async def _open_context_with_policy(playwright, platform: str, file_path: Path):
    account_id = file_path.stem if file_path else None
    return await create_context_with_policy(
        playwright,
        platform=platform,
        account_id=account_id,
        headless=HEADLESS_FLAG,
        storage_state=str(file_path),
        launch_kwargs={"args": ["--no-sandbox"]},
    )


async def _close_context(browser, context):
    with contextlib.suppress(Exception):
        if context:
            await context.close()
    with contextlib.suppress(Exception):
        if browser:
            await browser.close()

async def cookie_auth_douyin(file_path):
    """通过二次抓取cookie验证cookie状态"""
    async with async_playwright() as p:
        browser, context, _, _ = await _open_context_with_policy(p, "douyin", Path(file_path))
        page = await context.new_page()
        try:
            logger.info(f"[Douyin Check] Validating cookie by re-capture...")

            # 获取初始cookies中的关键认证字段
            initial_cookies = await context.cookies()
            initial_auth_cookies = {
                cookie['name']: cookie['value']
                for cookie in initial_cookies
                if cookie['name'] in ['sessionid', 'sessionid_ss', 'sid_guard', 'sid_tt', 'passport_auth_id', 'odin_tt']
            }

            if not initial_auth_cookies:
                logger.error(f"[Douyin Check] No auth cookies found in file")
                return {"status": "expired"}

            logger.info(f"[Douyin Check] Initial auth cookies: {list(initial_auth_cookies.keys())}")

            # 访问平台页面（尽力而为，失败不影响验证结果）
            page_loaded = False
            try:
                await page.goto("https://creator.douyin.com/creator-micro/content/upload",
                               wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_load_state("networkidle", timeout=15000)
                page_loaded = True
            except Exception as net_err:
                # 页面加载失败，返回网络错误而不是valid
                logger.error(f"[Douyin Check] Page load failed: {net_err}")
                await browser.close()
                return {"status": "network_error", "error": f"Network error: {str(net_err)}", "avatar": None, "name": None, "user_id": None}

            # 只有页面成功加载才继续后续检查
            if not page_loaded:
                # 这个分支不会执行到，因为上面已经return了
                pass

            await asyncio.sleep(2)  # 确保cookie完全设置

            # URL跳转检查
            if "login" in page.url or "passport" in page.url:
                logger.info(f"[Douyin Check] Redirected to login: {page.url}")
                return {"status": "expired"}

            # 二次抓取cookie
            new_cookies = await context.cookies()
            new_auth_cookies = {
                cookie['name']: cookie['value']
                for cookie in new_cookies
                if cookie['name'] in ['sessionid', 'sessionid_ss', 'sid_guard', 'sid_tt', 'passport_auth_id', 'odin_tt']
            }

            logger.info(f"[Douyin Check] Re-captured auth cookies: {list(new_auth_cookies.keys())}")

            # 验证逻辑：检查关键cookie是否仍然存在且有效
            if not new_auth_cookies:
                logger.error(f"[Douyin Check] ❌ Failed to re-capture auth cookies - cookie expired")
                return {"status": "expired"}

            # 检查至少有一个关键认证cookie保持一致
            valid_cookie_found = False
            for key in initial_auth_cookies:
                if key in new_auth_cookies and new_auth_cookies[key] == initial_auth_cookies[key]:
                    valid_cookie_found = True
                    logger.info(f"[Douyin Check] ✅ Auth cookie '{key}' is valid")
                    break

            if not valid_cookie_found:
                logger.error(f"[Douyin Check] ❌ No valid auth cookies found - cookie expired")
                await page.screenshot(path=str(BASE_DIR / "logs" / f"douyin_fail_{int(time.time())}.png"))
                return {"status": "expired"}

            # Cookie有效，提取用户信息
            avatar_url = None
            real_name = None
            user_id = None

            # 提取user_id
            import re
            for cookie in new_cookies:
                if cookie.get('name') in ['passport_auth_id', 'uid', 'user_unique_id']:
                    user_id = cookie.get('value')
                    if user_id:
                        logger.info(f"[Douyin Check] Found user_id: {user_id}")
                        break

            # 尝试获取头像和名字(快速尝试,失败不影响验证结果)
            try:
                selectors = [".avatar img", "img[src*='aweme']", "[class*='avatar'] img"]
                for sel in selectors:
                    if await page.locator(sel).count() > 0:
                        avatar_url = await page.locator(sel).first.get_attribute("src")
                        if avatar_url:
                            break

                name_selectors = [".header-right-name", ".name", "[class*='username']"]
                for sel in name_selectors:
                    if await page.locator(sel).count() > 0:
                        real_name = await page.locator(sel).first.inner_text()
                        if real_name and len(real_name.strip()) > 0:
                            break
            except Exception as e:
                logger.error(f"[Douyin Check] Failed to extract user info (non-critical): {e}")

            logger.info(f"[Douyin Check] ✅ Cookie validation successful")
            return {"status": "valid", "avatar": avatar_url, "name": real_name, "user_id": user_id}

        except Exception as e:
            logger.error(f"[Douyin Check] Error: {e}")
            return {"status": "error"}
        finally:
            await _close_context(browser, context)

async def cookie_auth_tencent(file_path):
    """通过二次抓取cookie验证cookie状态"""
    async with async_playwright() as p:
        browser, context, _, _ = await _open_context_with_policy(p, "tencent", Path(file_path))
        page = await context.new_page()
        try:
            logger.info(f"[Tencent Check] Validating cookie by re-capture...")

            # 获取初始cookies中的关键认证字段
            initial_cookies = await context.cookies()
            initial_auth_cookies = {
                cookie['name']: cookie['value']
                for cookie in initial_cookies
                if cookie['name'] in ['finder_username', 'username', 'uin', 'wxuin', 'mm_lang', 'pgv_pvi', 'pgv_pvid']
            }

            if not initial_auth_cookies:
                logger.error(f"[Tencent Check] No auth cookies found in file")
                return {"status": "expired"}

            logger.info(f"[Tencent Check] Initial auth cookies: {list(initial_auth_cookies.keys())}")

            # 访问平台页面（尽力而为，失败不影响验证结果）
            page_loaded = False
            try:
                await page.goto("https://channels.weixin.qq.com/platform",
                               wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_load_state("networkidle", timeout=15000)
                page_loaded = True
            except Exception as net_err:
                # 页面加载失败，返回网络错误而不是valid
                logger.error(f"[Tencent Check] Page load failed: {net_err}")
                await browser.close()
                return {"status": "network_error", "error": f"Network error: {str(net_err)}", "avatar": None, "name": None, "user_id": None}

            await asyncio.sleep(2)

            # URL跳转检查
            if "login" in page.url.lower():
                logger.info(f"[Tencent Check] Redirected to login: {page.url}")
                return {"status": "expired"}

            # 二次抓取cookie
            new_cookies = await context.cookies()
            new_auth_cookies = {
                cookie['name']: cookie['value']
                for cookie in new_cookies
                if cookie['name'] in ['finder_username', 'username', 'uin', 'wxuin', 'mm_lang', 'pgv_pvi', 'pgv_pvid']
            }

            logger.info(f"[Tencent Check] Re-captured auth cookies: {list(new_auth_cookies.keys())}")

            # 验证逻辑
            if not new_auth_cookies:
                logger.error(f"[Tencent Check] ❌ Failed to re-capture auth cookies - cookie expired")
                return {"status": "expired"}

            valid_cookie_found = False
            for key in initial_auth_cookies:
                if key in new_auth_cookies and new_auth_cookies[key] == initial_auth_cookies[key]:
                    valid_cookie_found = True
                    logger.info(f"[Tencent Check] ✅ Auth cookie '{key}' is valid")
                    break

            if not valid_cookie_found:
                logger.error(f"[Tencent Check] ❌ No valid auth cookies found - cookie expired")
                return {"status": "expired"}

            # 提取用户信息
            avatar_url = None
            real_name = None
            user_id = None

            import re
            for cookie in new_cookies:
                if cookie.get('name') in ['finder_username', 'username', 'uin', 'wxuin']:
                    user_id = cookie.get('value')
                    if user_id:
                        logger.info(f"[Tencent Check] Found user_id: {user_id}")
                        break

            # 尝试获取头像和名字
            try:
                selectors = [".finder-avatar img", ".avatar img", "img[src*='qlogo']"]
                for sel in selectors:
                    if await page.locator(sel).count() > 0:
                        avatar_url = await page.locator(sel).first.get_attribute("src")
                        if avatar_url:
                            break

                name_selectors = [".finder-nickname", ".nickname", "[class*='nickname']"]
                for sel in name_selectors:
                    if await page.locator(sel).count() > 0:
                        real_name = await page.locator(sel).first.inner_text()
                        if real_name and len(real_name.strip()) > 0:
                            break
            except Exception as e:
                logger.error(f"[Tencent Check] Failed to extract user info (non-critical): {e}")

            logger.info(f"[Tencent Check] ✅ Cookie validation successful")
            return {"status": "valid", "avatar": avatar_url, "name": real_name, "user_id": user_id}

        except Exception as e:
            logger.error(f"[Tencent Check] Error: {e}")
            return {"status": "error"}
        finally:
            await _close_context(browser, context)

async def cookie_auth_ks(file_path):
    """通过二次抓取cookie验证cookie状态"""
    async with async_playwright() as p:
        browser, context, _, _ = await _open_context_with_policy(p, "kuaishou", Path(file_path))
        page = await context.new_page()
        try:
            logger.info(f"[Kuaishou Check] Validating cookie by re-capture...")

            # 获取初始cookies中的关键认证字段
            initial_cookies = await context.cookies()
            initial_auth_cookies = {
                cookie['name']: cookie['value']
                for cookie in initial_cookies
                if cookie['name'] in ['userId', 'did', 'kpf', 'kpn', 'clientid', 'token', 'kuaishou.user.id']
            }

            if not initial_auth_cookies:
                logger.error(f"[Kuaishou Check] No auth cookies found in file")
                return {"status": "expired"}

            logger.info(f"[Kuaishou Check] Initial auth cookies: {list(initial_auth_cookies.keys())}")

            # 访问平台页面（尽力而为，失败不影响验证结果）
            page_loaded = False
            try:
                await page.goto("https://cp.kuaishou.com/article/publish/video",
                               wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_load_state("networkidle", timeout=15000)
                page_loaded = True
            except Exception as net_err:
                # 页面加载失败，返回网络错误而不是valid
                logger.error(f"[Kuaishou Check] Page load failed: {net_err}")
                await browser.close()
                return {"status": "network_error", "error": f"Network error: {str(net_err)}", "avatar": None, "name": None, "user_id": None}

            await asyncio.sleep(2)

            # URL跳转检查
            if "login" in page.url or "passport" in page.url:
                logger.info(f"[Kuaishou Check] Redirected to login: {page.url}")
                return {"status": "expired"}

            # 二次抓取cookie
            new_cookies = await context.cookies()
            new_auth_cookies = {
                cookie['name']: cookie['value']
                for cookie in new_cookies
                if cookie['name'] in ['userId', 'did', 'kpf', 'kpn', 'clientid', 'token', 'kuaishou.user.id']
            }

            logger.info(f"[Kuaishou Check] Re-captured auth cookies: {list(new_auth_cookies.keys())}")

            # 验证逻辑
            if not new_auth_cookies:
                logger.error(f"[Kuaishou Check] ❌ Failed to re-capture auth cookies - cookie expired")
                await page.screenshot(path=str(BASE_DIR / "logs" / f"ks_fail_{int(time.time())}.png"))
                return {"status": "expired"}

            valid_cookie_found = False
            for key in initial_auth_cookies:
                if key in new_auth_cookies and new_auth_cookies[key] == initial_auth_cookies[key]:
                    valid_cookie_found = True
                    logger.info(f"[Kuaishou Check] ✅ Auth cookie '{key}' is valid")
                    break

            if not valid_cookie_found:
                logger.error(f"[Kuaishou Check] ❌ No valid auth cookies found - cookie expired")
                await page.screenshot(path=str(BASE_DIR / "logs" / f"ks_fail_{int(time.time())}.png"))
                return {"status": "expired"}

            # 提取用户信息
            avatar_url = None
            real_name = None
            user_id = None

            import re
            for cookie in new_cookies:
                if cookie.get('name') in ['userId', 'kuaishou.user.id']:
                    user_id = cookie.get('value')
                    if user_id:
                        logger.info(f"[Kuaishou Check] Found user_id: {user_id}")
                        break

            # 尝试获取头像和名字
            try:
                selectors = [".avatar-wrapper img", ".avatar img", "div[class*='avatar'] img"]
                for sel in selectors:
                    if await page.locator(sel).count() > 0:
                        avatar_url = await page.locator(sel).first.get_attribute("src")
                        if avatar_url:
                            break

                name_selectors = [".user-name", ".name", "[class*='username']"]
                for sel in name_selectors:
                    if await page.locator(sel).count() > 0:
                        real_name = await page.locator(sel).first.inner_text()
                        if real_name and len(real_name.strip()) > 0:
                            break
            except Exception as e:
                logger.error(f"[Kuaishou Check] Failed to extract user info (non-critical): {e}")

            logger.info(f"[Kuaishou Check] ✅ Cookie validation successful")
            return {"status": "valid", "avatar": avatar_url, "name": real_name, "user_id": user_id}

        except Exception as e:
            logger.error(f"[Kuaishou Check] Error: {e}")
            return {"status": "error"}
        finally:
            await _close_context(browser, context)

async def cookie_auth_xhs(file_path):
    """通过二次抓取cookie验证cookie状态"""
    async with async_playwright() as p:
        browser, context, _, _ = await _open_context_with_policy(p, "xiaohongshu", Path(file_path))
        page = await context.new_page()
        try:
            logger.info(f"[XHS Check] Validating cookie by re-capture...")

            # 获取初始cookies中的关键认证字段
            initial_cookies = await context.cookies()
            initial_auth_cookies = {
                cookie['name']: cookie['value']
                for cookie in initial_cookies
                if cookie['name'] in ['web_session', 'xhsuid', 'customer-sso-sid', 'a1', 'webId']
            }

            if not initial_auth_cookies:
                logger.error(f"[XHS Check] No auth cookies found in file")
                return {"status": "expired"}

            logger.info(f"[XHS Check] Initial auth cookies: {list(initial_auth_cookies.keys())}")

            # 访问平台页面（尽力而为，失败不影响验证结果）
            page_loaded = False
            try:
                await page.goto("https://creator.xiaohongshu.com/creator-micro/content/upload",
                               wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_load_state("networkidle", timeout=10000)
                page_loaded = True
            except Exception as net_err:
                # 页面加载失败，返回网络错误而不是valid
                logger.error(f"[XHS Check] Page load failed: {net_err}")
                await browser.close()
                return {"status": "network_error", "error": f"Network error: {str(net_err)}", "avatar": None, "name": None, "user_id": None}

            await asyncio.sleep(2)

            # URL跳转检查
            if "login" in page.url:
                logger.info(f"[XHS Check] Redirected to login: {page.url}")
                return {"status": "expired"}

            # 二次抓取cookie
            new_cookies = await context.cookies()
            new_auth_cookies = {
                cookie['name']: cookie['value']
                for cookie in new_cookies
                if cookie['name'] in ['web_session', 'xhsuid', 'customer-sso-sid', 'a1', 'webId']
            }

            logger.info(f"[XHS Check] Re-captured auth cookies: {list(new_auth_cookies.keys())}")

            # 验证逻辑
            if not new_auth_cookies:
                logger.error(f"[XHS Check] ❌ Failed to re-capture auth cookies - cookie expired")
                await page.screenshot(path=str(BASE_DIR / "logs" / f"xhs_fail_{int(time.time())}.png"))
                return {"status": "expired"}

            valid_cookie_found = False
            for key in initial_auth_cookies:
                if key in new_auth_cookies and new_auth_cookies[key] == initial_auth_cookies[key]:
                    valid_cookie_found = True
                    logger.info(f"[XHS Check] ✅ Auth cookie '{key}' is valid")
                    break

            if not valid_cookie_found:
                logger.error(f"[XHS Check] ❌ No valid auth cookies found - cookie expired")
                await page.screenshot(path=str(BASE_DIR / "logs" / f"xhs_fail_{int(time.time())}.png"))
                return {"status": "expired"}

            # 提取用户信息
            avatar_url = None
            real_name = None
            user_id = None

            import re
            for cookie in new_cookies:
                if cookie.get('name') in ['web_session', 'xhsuid', 'customer-sso-sid']:
                    user_id = cookie.get('value')
                    if user_id:
                        logger.info(f"[XHS Check] Found user_id: {user_id}")
                        break

            # 尝试获取头像和名字
            try:
                selectors = [".avatar img", ".user-avatar img", "img[class*='avatar']"]
                for sel in selectors:
                    if await page.locator(sel).count() > 0:
                        avatar_url = await page.locator(sel).first.get_attribute("src")
                        if avatar_url:
                            break

                name_selectors = [".user-name", ".name", "span[class*='name']"]
                for sel in name_selectors:
                    if await page.locator(sel).count() > 0:
                        real_name = await page.locator(sel).first.inner_text()
                        if real_name and len(real_name.strip()) > 0:
                            break
            except Exception as e:
                logger.error(f"[XHS Check] Failed to extract user info (non-critical): {e}")

            logger.info(f"[XHS Check] ✅ Cookie validation successful")
            return {"status": "valid", "avatar": avatar_url, "name": real_name, "user_id": user_id}

        except Exception as e:
            logger.error(f"[XHS Check] Error: {e}")
            return {"status": "error"}
        finally:
            await _close_context(browser, context)

async def cookie_auth_bilibili(file_path):
    """通过二次抓取cookie验证cookie状态"""
    async with async_playwright() as p:
        browser, context, _, _ = await _open_context_with_policy(p, "bilibili", Path(file_path))
        page = await context.new_page()
        try:
            logger.info(f"[Bilibili Check] Validating cookie by re-capture...")

            # 获取初始cookies中的关键认证字段
            initial_cookies = await context.cookies()
            initial_auth_cookies = {
                cookie['name']: cookie['value']
                for cookie in initial_cookies
                if cookie['name'] in ['DedeUserID', 'bili_jct', 'SESSDATA', 'buvid3']
            }

            if not initial_auth_cookies:
                logger.error(f"[Bilibili Check] No auth cookies found in file")
                return {"status": "expired"}

            logger.info(f"[Bilibili Check] Initial auth cookies: {list(initial_auth_cookies.keys())}")

            # 访问平台页面（尽力而为，失败不影响验证结果）
            page_loaded = False
            try:
                await page.goto("https://member.bilibili.com/platform/home",
                               wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_load_state("networkidle", timeout=10000)
                page_loaded = True
            except Exception as net_err:
                # 页面加载失败，返回网络错误而不是valid
                logger.error(f"[Bilibili Check] Page load failed: {net_err}")
                await browser.close()
                return {"status": "network_error", "error": f"Network error: {str(net_err)}", "avatar": None, "name": None, "user_id": None}

            await asyncio.sleep(2)

            # URL跳转检查
            if "passport.bilibili.com/login" in page.url:
                logger.info(f"[Bilibili Check] Redirected to login: {page.url}")
                return {"status": "expired"}

            # 二次抓取cookie
            new_cookies = await context.cookies()
            new_auth_cookies = {
                cookie['name']: cookie['value']
                for cookie in new_cookies
                if cookie['name'] in ['DedeUserID', 'bili_jct', 'SESSDATA', 'buvid3']
            }

            logger.info(f"[Bilibili Check] Re-captured auth cookies: {list(new_auth_cookies.keys())}")

            # 验证逻辑
            if not new_auth_cookies:
                logger.error(f"[Bilibili Check] ❌ Failed to re-capture auth cookies - cookie expired")
                await page.screenshot(path=str(BASE_DIR / "logs" / f"bili_fail_{int(time.time())}.png"))
                return {"status": "expired"}

            valid_cookie_found = False
            for key in initial_auth_cookies:
                if key in new_auth_cookies and new_auth_cookies[key] == initial_auth_cookies[key]:
                    valid_cookie_found = True
                    logger.info(f"[Bilibili Check] ✅ Auth cookie '{key}' is valid")
                    break

            if not valid_cookie_found:
                logger.error(f"[Bilibili Check] ❌ No valid auth cookies found - cookie expired")
                await page.screenshot(path=str(BASE_DIR / "logs" / f"bili_fail_{int(time.time())}.png"))
                return {"status": "expired"}

            # 提取用户信息
            avatar_url = None
            real_name = "Bilibili User"
            user_id = None

            import re
            for cookie in new_cookies:
                if cookie.get('name') == 'DedeUserID':
                    user_id = cookie.get('value')
                    logger.info(f"[Bilibili Check] Found user_id: {user_id}")
                    break

            # 尝试获取头像
            try:
                selectors = [".header-entry-avatar .face-img", ".avatar-img", ".header-avatar-wrap img"]
                for sel in selectors:
                    if await page.locator(sel).count() > 0:
                        avatar_url = await page.locator(sel).first.get_attribute("src")
                        if avatar_url:
                            break
            except Exception as e:
                logger.error(f"[Bilibili Check] Failed to extract avatar (non-critical): {e}")

            logger.info(f"[Bilibili Check] ✅ Cookie validation successful")
            return {"status": "valid", "avatar": avatar_url, "name": real_name, "user_id": user_id}

        except Exception as e:
            logger.error(f"[Bilibili Check] Error: {e}")
            return {"status": "error"}
        finally:
            await _close_context(browser, context)

async def _check_cookie_impl(type, file_path):
    """
    内部实现：验证Cookie并返回状态和用户信息
    This function runs with Playwright directly.
    """
    resolved_path = cookie_manager._resolve_cookie_path(file_path)
    match type:
        case 1: return await cookie_auth_xhs(resolved_path)
        case 2: return await cookie_auth_tencent(resolved_path)
        case 3: return await cookie_auth_douyin(resolved_path)
        case 4: return await cookie_auth_ks(resolved_path)
        case 5: return await cookie_auth_bilibili(resolved_path)
        case _: return {"status": "unknown"}


async def check_cookie(type, file_path):
    """
    验证Cookie并返回状态和用户信息（FastAPI兼容版本）

    Uses subprocess to avoid asyncio/Playwright compatibility issues on Windows.

    Returns:
        dict: {"status": "valid"|"expired"|"error"|"network_error", "avatar": str, "name": str}
    """
    try:
        import subprocess
        import json
        import sys
        from pathlib import Path

        # Run validation in subprocess to avoid asyncio issues
        validator_script = Path(__file__).parent / "cookie_validator_subprocess.py"
        result = subprocess.run(
            [sys.executable, str(validator_script), str(type), file_path],
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout
        )

        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            from loguru import logger
            logger.error(f"Cookie validation subprocess failed: {result.stderr}")
            return {"status": "error", "error": result.stderr}
    except subprocess.TimeoutExpired:
        from loguru import logger
        logger.error(f"Cookie validation timeout for type {type}")
        return {"status": "error", "error": "Validation timeout"}
    except Exception as e:
        from loguru import logger
        logger.error(f"Cookie validation failed for type {type}: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
