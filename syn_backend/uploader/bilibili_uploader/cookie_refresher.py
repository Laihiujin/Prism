"""
Bilibili Cookie 刷新器
通过无头浏览器访问 B站，自动刷新 Cookie 并获取最新的认证信息
"""
import asyncio
import json
import os
from playwright.async_api import async_playwright
from utils.log import bilibili_logger
from myUtils.browser_context import build_context_options, build_browser_args
from utils.base_social_media import set_init_script, HEADLESS_FLAG


def _to_cookie_list(cookie_data: dict) -> list[dict]:
    if not isinstance(cookie_data, dict):
        return []

    if isinstance(cookie_data.get("cookie_info"), dict) and isinstance(cookie_data["cookie_info"].get("cookies"), list):
        return cookie_data["cookie_info"]["cookies"]

    if isinstance(cookie_data.get("cookies"), list):
        return cookie_data["cookies"]

    # name->value dict
    cookies = []
    for k, v in cookie_data.items():
        if not k or v is None:
            continue
        cookies.append({"name": str(k), "value": str(v)})
    return cookies


def to_biliup_cookie_format(cookie_data: dict) -> dict:
    cookies_list = _to_cookie_list(cookie_data)
    # Ensure bilibili domain/path for Playwright injection, but keep minimal keys for biliup
    normalized = []
    for c in cookies_list:
        name = c.get("name")
        value = c.get("value")
        if not name or value is None:
            continue
        # Ensure value is string, not dict or other types
        if isinstance(value, dict):
            bilibili_logger.warning(f"[Cookie Formatter] Cookie '{name}' has dict value, skipping: {value}")
            continue
        normalized.append({"name": name, "value": str(value), "domain": ".bilibili.com", "path": "/"})

    access_token = ""
    if isinstance(cookie_data, dict):
        access_token = (
            (cookie_data.get("token_info") or {}).get("access_token")
            if isinstance(cookie_data.get("token_info"), dict)
            else cookie_data.get("access_token", "")
        ) or ""

    return {
        "cookie_info": {"cookies": normalized},
        "token_info": {"access_token": access_token},
    }


async def refresh_bilibili_cookies(cookie_data: dict, proxy: dict = None) -> dict:
    """
    使用现有的 Bilibili Cookie，通过无头浏览器访问 B站并刷新 Cookie

    Args:
        cookie_data: 现有的 Cookie 字典（包含 SESSDATA, bili_jct 等）

    Returns:
        dict: 刷新后的完整 Cookie 字典
    """
    bilibili_logger.info("[Cookie Refresher] 开始刷新 B站 Cookie...")

    # Normalize to biliup cookie format, then extract cookie list for Playwright injection
    biliup_cookie = to_biliup_cookie_format(cookie_data)
    cookies_list = biliup_cookie["cookie_info"]["cookies"]

    async with async_playwright() as playwright:
        try:
            # 启动浏览器
            launch_kwargs = build_browser_args()
            launch_kwargs["headless"] = HEADLESS_FLAG
            if not launch_kwargs.get("executable_path"):
                launch_kwargs.pop("executable_path", None)
            if proxy:
                 launch_kwargs["proxy"] = proxy
                 bilibili_logger.info(f"Using Proxy: {proxy.get('server')}")

            browser = await playwright.chromium.launch(**launch_kwargs)
            
            # 创建上下文并注入 Cookie
            context = await browser.new_context(**build_context_options())
            await context.add_cookies(cookies_list)
            context = await set_init_script(context)
            
            # 创建页面并访问 B站
            page = await context.new_page()
            bilibili_logger.info("[Cookie Refresher] 正在访问 bilibili.com...")
            
            try:
                await page.goto("https://www.bilibili.com", timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception as e:
                bilibili_logger.warning(f"[Cookie Refresher] 页面加载超时: {e}")
            
            # 等待一下让浏览器完成所有认证操作
            await asyncio.sleep(2)
            
            # 检查是否登录成功
            logged_in = False
            try:
                # 检查是否有登录指示器（用户头像）
                user_avatar = page.locator(".header-avatar-wrap")
                if await user_avatar.count() > 0:
                    bilibili_logger.success("[Cookie Refresher] 检测到已登录状态")
                    logged_in = True
                else:
                    # 检查是否有登录按钮（说明未登录）
                    login_button = page.locator("text=登录")
                    if await login_button.count() > 0:
                        bilibili_logger.warning("[Cookie Refresher] Cookie 可能已失效")
            except Exception as e:
                bilibili_logger.warning(f"[Cookie Refresher] 检测登录状态失败: {e}")
            
            # 获取刷新后的 Cookie
            cookies_after = await context.cookies()
            bilibili_logger.info(f"[Cookie Refresher] 获取到 {len(cookies_after)} 个 Cookie")
            
            # Convert back to biliup cookie format
            refreshed_cookie_data = {
                "cookie_info": {"cookies": []},
                "token_info": {"access_token": biliup_cookie.get("token_info", {}).get("access_token", "")},
            }
            for cookie in cookies_after:
                name = cookie.get("name")
                value = cookie.get("value")
                if name and value:
                    refreshed_cookie_data["cookie_info"]["cookies"].append({
                        "name": name,
                        "value": value,
                        "domain": cookie.get("domain") or ".bilibili.com",
                        "path": cookie.get("path") or "/",
                    })
            
            # 检查关键 Cookie 是否存在
            key_cookies = ["SESSDATA", "bili_jct", "DedeUserID"]
            cookies_dict = {c.get("name"): c.get("value") for c in refreshed_cookie_data["cookie_info"]["cookies"]}
            missing_cookies = [key for key in key_cookies if key not in cookies_dict]
            if missing_cookies:
                bilibili_logger.warning(f"[Cookie Refresher] 缺少关键 Cookie: {missing_cookies}")
            else:
                bilibili_logger.success("[Cookie Refresher] 所有关键 Cookie 已获取")
            
            # 关闭浏览器
            await context.close()
            await browser.close()
            
            if logged_in:
                bilibili_logger.success("[Cookie Refresher] Cookie 刷新成功")
            else:
                bilibili_logger.warning("[Cookie Refresher] Cookie 刷新完成，但可能未登录")
            
            return refreshed_cookie_data
            
        except Exception as e:
            bilibili_logger.error(f"[Cookie Refresher] 刷新失败: {e}")
            return to_biliup_cookie_format(cookie_data)  # 失败时返回原 Cookie


if __name__ == "__main__":
    # 测试代码
    test_cookie = {
        "SESSDATA": "test_session",
        "bili_jct": "test_csrf",
        "DedeUserID": "123456"
    }
    
    result = asyncio.run(refresh_bilibili_cookies(test_cookie))
    print("Refreshed cookies:", result)
