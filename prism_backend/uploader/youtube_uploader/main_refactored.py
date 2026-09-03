# -*- coding: utf-8 -*-
"""YouTube uploader (browser automation via YouTube Studio).

Unlike the other platforms here, YouTube also offers an official Data API. We deliberately
use browser automation instead, because videos uploaded through an *unaudited* API project
are force-locked to private and cannot be made public without passing Google's compliance
audit (which is impractical for personal/single-channel use). Browser automation has no such
restriction and can publish public videos right away, and it matches the cookie-based pattern
used by every other uploader in this project.

Login is interactive (Google account, no QR code): the browser opens, the user signs in, and
the storage_state is saved. Reuse it afterwards for fully unattended uploads.
"""
import asyncio
import re
from pathlib import Path

from patchright.async_api import Page, Playwright, async_playwright

from config.conf import DEBUG_MODE, LOCAL_CHROME_PATH
from uploader.base_video import BaseVideoUploader
from utils.base_social_media import set_init_script
from utils.log import youtube_logger
from myUtils.browser_context import launch_optional_browser

try:
    # 国内直连 youtube.com 会超时，且 patchright 启的 chromium 不吃系统代理。
    # 在 conf.py 设 YT_PROXY = "http://127.0.0.1:7890"（本地代理端口）即可；不设则不走代理。
    from config.conf import YT_PROXY
except Exception:
    YT_PROXY = None

STUDIO_URL = "https://studio.youtube.com"
UPLOAD_URL = "https://www.youtube.com/upload"
VISIBILITY = {"public": "PUBLIC", "unlisted": "UNLISTED", "private": "PRIVATE"}


def _msg(emoji: str, text: str) -> str:
    return f"{emoji} {text}"


def _chrome_launch_options(*, headless: bool, **options):
    """Use the explicitly configured local Chrome before a browser channel."""
    launch_options = {
        "headless": headless,
        "args": [
            "--disable-blink-features=AutomationControlled",
        ],
        **options,
    }
    if LOCAL_CHROME_PATH:
        launch_options["executable_path"] = LOCAL_CHROME_PATH
    else:
        launch_options["channel"] = "chrome"
    return launch_options


def _build_login_result(success, status, message, account_file, current_url=""):
    return {
        "success": success,
        "status": status,
        "message": message,
        "account_file": str(account_file),
        "current_url": current_url,
    }


def _parse_youtube_account_id(account_file) -> str:
    """从 cookie 文件名解析 account_id：youtube_account_xxx.json -> account_xxx"""
    stem = Path(str(account_file)).stem
    if stem.startswith("youtube_"):
        return stem[len("youtube_"):] or stem
    return stem


def _register_youtube_placeholder(cookie_manager, account_id: str, cookie_file: str, user_id: str) -> None:
    """轻量占位入库（保留原 cookie 文件名）。

    反查不可用（TikHub 402/无 key）时使用：避免 add_account 把 cookie 文件改名为
    占位符格式（youtube_youtube_xxx.json），导致 CLI 的 account_file 路径失效。
    账号名暂用「YouTube-日期时间」占位，等 TikHub 反查可用后由 enrich-tikhub 补全
    真实频道信息；入库后即受账号库保护，不会再被 cleanup_orphan_cookie_files 删除。
    """
    import sqlite3
    from datetime import datetime

    display_name = f"YouTube-{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    conn = sqlite3.connect(cookie_manager.db_path)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO cookie_accounts
               (account_id, platform, platform_code, name, status, cookie_file, last_checked, user_id, note)
               VALUES (?, 'youtube', 7, ?, 'valid', ?, ?, ?, ?)""",
            (account_id, display_name, cookie_file, datetime.utcnow().isoformat(), user_id, account_id),
        )
        conn.commit()
    finally:
        conn.close()


_YT_CHANNEL_ID_RE = re.compile(r"/channel/(UC[\w-]+)")


def _extract_youtube_channel_id_from_url(url: str) -> str:
    """从 URL 提取 YouTube channel_id（/channel/UCxxx）。"""
    m = _YT_CHANNEL_ID_RE.search(str(url or ""))
    return m.group(1) if m else ""


async def _fetch_youtube_channel_id_from_session(account_file) -> str:
    """无头用登录态打开 YouTube 上传页，从重定向 URL 自动抓取 channel_id。

    www.youtube.com/upload 会自动跳转到 studio.youtube.com/channel/{channelId}/content?d=ud，
    其 URL 内嵌 channel_id。这解决了 channel_id 需手动填的问题：
    登录落库时即使未提供 URL/handle，也能从登录态自动拿到真实频道 ID。
    """
    try:
        path = Path(str(account_file))
        if not path.exists():
            return ""
        async with async_playwright() as pw:
            browser = await launch_optional_browser(pw, platform="youtube", **_chrome_launch_options(headless=True))
            try:
                context = await browser.new_context(storage_state=str(path))
                context = await set_init_script(context)
                page = await context.new_page()
                await page.goto("https://www.youtube.com/upload", wait_until="domcontentloaded", timeout=60000)
                cid = ""
                for _ in range(12):  # 等待重定向到带 channel_id 的 Studio URL
                    await page.wait_for_timeout(1500)
                    cid = _extract_youtube_channel_id_from_url(page.url)
                    if cid:
                        break
                return cid
            finally:
                await browser.close()
    except Exception as e:
        youtube_logger.warning(f"[YouTube] 从登录态抓取 channel_id 异常: {e}")
        return ""


async def _fetch_youtube_channel_info_local(channel_id: str, handle: str = "") -> dict[str, str]:
    """无头访问 YouTube 频道公开页（/channel/{id} 或 @handle）抓取频道名/头像。

    免费方案：不依赖 TikHub（其 get_channel_info 需付费），从页面 og 元信息抓取。
    返回 {name, avatar}；失败返回空 dict。
    """
    if not channel_id and not handle:
        return {}
    url = f"https://www.youtube.com/channel/{channel_id}" if channel_id else f"https://www.youtube.com/{handle}"
    try:
        async with async_playwright() as pw:
            browser = await launch_optional_browser(pw, platform="youtube", **_chrome_launch_options(headless=True))
            try:
                context = await browser.new_context()
                context = await set_init_script(context)
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(4000)
                name = ""
                avatar = ""
                for sel, key in (('meta[property="og:title"]', "name"), ('meta[property="og:image"]', "avatar")):
                    try:
                        v = await page.get_attribute(sel, "content")
                    except Exception:
                        v = None
                    if key == "name" and v:
                        name = v
                    elif key == "avatar" and v:
                        avatar = v
                # 兜底：从 title "Laihiujin - YouTube" 提取频道名
                if not name:
                    try:
                        t = await page.title()
                        if t and " - YouTube" in t:
                            name = t.split(" - YouTube")[0]
                    except Exception:
                        pass
                return {"name": name, "avatar": avatar}
            finally:
                await browser.close()
    except Exception as e:
        youtube_logger.warning(f"[YouTube] 本地抓取频道信息异常: {e}")
        return {}


async def _auto_register_account(account_file, original_account=None) -> None:
    """CLI/上传器路径登录成功后，把 YouTube 账号写入账号库。

    背景：browser_login API 登录会在 /status 里 add_account 入库；但 CLI
    `prism youtube login` 只保存 cookie 文件、不入库，账号既不在账号库，
    文件也会被 user_info_sync_scheduler 的 cleanup_orphan_cookie_files 当孤儿删除。
    这里补齐入库：

    - 优先用 TikHub 反查真实 channel_id（免费 get_channel_id_v2：URL/handle/UCxxx
      均可解析），文件名规范化为 youtube_{channel_id}.json；
    - 反查不可用（未配置 key / 网络异常）时用轻量占位入库，账号名暂用
      「YouTube-日期时间」，保留原 cookie 文件名，保证登录态不再被清理；
    - 已在库的账号跳过（幂等），之后可通过 /accounts/{id}/enrich-tikhub 反查补全。

    original_account: 登录时用户输入的原始账号名（可能是频道 URL / handle），
    用于反查；缺省时退化为从 cookie 文件名解析的 account_id。
    """
    try:
        path = Path(str(account_file))
        if not path.exists():
            return
        import json as _json
        from myUtils.cookie_manager import cookie_manager

        account_id = _parse_youtube_account_id(account_file)
        if cookie_manager.get_account_by_id(account_id):
            return  # 已在账号库，跳过

        data = _json.loads(path.read_text(encoding="utf-8"))
        cookie_data = data if isinstance(data, dict) else {}

        # 1) 尝试 TikHub 反查真实 channel_id（用原始账号名，能解析 URL/handle）
        channel_id = None
        try:
            from myUtils.tikhub_client import get_tikhub_client
            tikhub = get_tikhub_client()
            if tikhub:
                async with tikhub as client:
                    channel_id = await client.resolve_youtube_channel_id(original_account or account_id)
        except Exception as exc:
            youtube_logger.warning(f"[YouTube] 反查 channel_id 失败: {exc}")

        # 1b) TikHub 没拿到（如账号名是时间戳ID），回退从登录态自动抓取（无需手动填 id）
        if not channel_id:
            channel_id = await _fetch_youtube_channel_id_from_session(account_file)
            if channel_id:
                youtube_logger.info(f"[YouTube] 登录态自动抓取 channel_id: {channel_id}")

        if channel_id:
            # 2a) 反查成功：正常入库（文件名规范化为 youtube_{channel_id}.json）
            from datetime import datetime
            display_name = f"YouTube-{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            details = {
                "account_id": account_id,
                "cookie": cookie_data,
                "user_id": channel_id,
                "name": display_name,
                "note": original_account or account_id,
            }
            cookie_manager.add_account("youtube", details)
            youtube_logger.info(f"[YouTube] 登录态已入库(反查): account_id={account_id} channel_id={channel_id}")

            # 补全频道名/头像：优先本地无头抓取（免费，主方案），TikHub(需付费)兜底。
            update = {}
            try:
                local = await _fetch_youtube_channel_info_local(channel_id=channel_id)
                if local.get("name"):
                    update["name"] = str(local["name"])
                if local.get("avatar"):
                    update["avatar"] = str(local["avatar"])
                if update:
                    youtube_logger.info(f"[YouTube] 本地抓取频道信息成功: {update}")
            except Exception as exc:
                youtube_logger.warning(f"[YouTube] 本地抓取频道信息失败: {exc}")
            # 本地抓取补不到原频道名时，退回 TikHub 反查（若已配置）
            if not update.get("name") and not update.get("original_name"):
                try:
                    from myUtils.tikhub_client import get_tikhub_client as _get_tikhub
                    tikhub2 = _get_tikhub()
                    if tikhub2:
                        async with tikhub2 as client:
                            profile = await client.fetch_account_profile("youtube", channel_id)
                        if profile:
                            if profile.get("name"):
                                update["name"] = str(profile["name"])
                            if profile.get("original_name"):
                                update["original_name"] = str(profile["original_name"])
                            if profile.get("avatar"):
                                update["avatar"] = str(profile["avatar"])
                except Exception as exc:
                    youtube_logger.warning(f"[YouTube] TikHub 反查补全失败（不影响入库）: {exc}")
            if update:
                cookie_manager.update_account(account_id, **update)
                youtube_logger.info(f"[YouTube] 补全频道信息: {update}")
        else:
            # 2b) 反查不可用：轻量占位入库，保留原文件
            user_id = f"youtube_{account_id}"
            _register_youtube_placeholder(cookie_manager, account_id, path.name, user_id)
            youtube_logger.info(
                f"[YouTube] 登录态已入库(占位): account_id={account_id} user_id={user_id} file={path.name}"
            )
    except Exception as exc:
        youtube_logger.warning(f"[YouTube] 自动入库失败（不影响登录）: {exc}")


async def cookie_auth(account_file) -> bool:
    """登录态是否仍有效：带 cookie 打开 Studio，没被踢到 Google 登录页且进入了频道页即有效。"""
    async with async_playwright() as playwright:
        browser = await launch_optional_browser(playwright, platform="youtube", **_chrome_launch_options(headless=True))
        try:
            context = await browser.new_context(storage_state=account_file)
            context = await set_init_script(context)
            page = await context.new_page()
            await page.goto(STUDIO_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            url = page.url.lower()
            if "accounts.google.com" in url or "/signin" in url:
                return False
            # 已登录：停留在 Studio 首页（studio.youtube.com，不含 /channel/）或频道页/youtube 域内
            return "youtube.com" in url
        except Exception:
            return False
        finally:
            await browser.close()


async def youtube_cookie_gen(account_file, headless: bool = False):
    """交互式登录：开浏览器让用户登录 Google/YouTube，进入频道页后保存 storage_state。"""
    async with async_playwright() as playwright:
        # 登录必须显形，让用户输账号密码/二步验证
        browser = await launch_optional_browser(playwright, platform="youtube", **_chrome_launch_options(headless=False))
        context = await browser.new_context()
        context = await set_init_script(context)
        page = await context.new_page()
        await page.goto(STUDIO_URL, wait_until="domcontentloaded")
        youtube_logger.info(_msg("🔐", "请在弹出的浏览器里登录 Google / YouTube 账号，登录后会自动保存"))
        ok = False
        _login_cookies = {"SID", "HSID", "SSID", "SAPISID", "GAPS", "SIDCC"}
        for _ in range(600):  # 最多等 10 分钟
            url = page.url.lower()
            # 离开 Google 登录页并进入 YouTube，且已带 Google 登录 cookie
            if (
                "accounts.google.com" not in url
                and ("studio.youtube.com" in url or "/channel/" in url or "youtube.com" in url)
            ):
                state = await context.storage_state()
                names = {c.get("name") for c in state.get("cookies", [])}
                if names & _login_cookies:
                    await page.wait_for_timeout(2000)  # 让 cookie 落定
                    ok = True
                    break
            await asyncio.sleep(1)
        if ok:
            await context.storage_state(path=account_file)
            youtube_logger.success(_msg("✅", f"YouTube 登录态已保存: {account_file}"))
        else:
            youtube_logger.error(_msg("😵", "等待登录超时，未保存登录态"))
        await browser.close()
        return _build_login_result(ok, "logged_in" if ok else "timeout",
                                   "登录成功" if ok else "登录超时", account_file, page.url)


async def youtube_setup(account_file, handle: bool = False, return_detail: bool = False, headless: bool = False):
    """校验登录态，失效且 handle=True 时拉起交互式登录；成功后自动入库账号库。"""
    if not Path(account_file).exists() or not await cookie_auth(account_file):
        if not handle:
            result = _build_login_result(False, "cookie_invalid", "登录态不存在或已失效", account_file)
            return result if return_detail else False
        youtube_logger.info(_msg("🥹", "YouTube 登录态不存在或失效，准备打开浏览器登录"))
        result = await youtube_cookie_gen(account_file, headless=headless)
        if result.get("success"):
            await _auto_register_account(account_file)
        return result if return_detail else result["success"]
    result = _build_login_result(True, "cookie_valid", "登录态有效", account_file)
    if result.get("success"):
        # 磁盘已有有效登录态：回收进账号库（幂等，已在库则跳过）
        await _auto_register_account(account_file)
    return result if return_detail else True


async def _dismiss_autocomplete(page: Page):
    """关掉 # 话题 / @ 提及 自动补全下拉浮层（会挡住后续“继续/发布”按钮）。

    先 blur 失焦；若浮层仍可见再补一次 Escape——仅在检测到浮层时才按，
    避免在没有浮层时误关掉整个上传对话框。"""
    try:
        await page.evaluate("() => { const a = document.activeElement; if (a && a.blur) a.blur(); }")
    except Exception:
        pass
    try:
        dropdown = page.locator("tp-yt-iron-dropdown:visible")
        if await dropdown.count() > 0:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(200)
    except Exception:
        pass


async def _fill_editable(page: Page, selector: str, text: str):
    """填 YouTube Studio 的 contenteditable 富文本框（标题/简介），先清空再输入。

    用 fill() 一次性灌入而非逐字 type()：标题/简介里的 # 字符（如 #Shorts）会触发
    YouTube 的话题自动补全下拉浮层；逐字输入会让浮层持续跟随光标弹出、盖住输入框与
    后续“继续/发布”按钮，导致上传流程卡死。fill() 一次性写入不会逐字触发补全。"""
    box = page.locator(selector).first
    await box.wait_for(state="visible", timeout=30000)
    await box.click()
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Delete")
    try:
        await box.fill(text)            # 一次性灌入，不逐字触发 # 话题自动补全
    except Exception:
        await box.type(text, delay=6)   # 个别 contenteditable 不支持 fill 时退回逐字输入
    await page.wait_for_timeout(400)
    await _dismiss_autocomplete(page)   # 收尾关掉可能弹出的补全浮层


async def _click_if_present(page: Page, selector: str, timeout: int = 4000) -> bool:
    try:
        el = page.locator(selector).first
        await el.wait_for(state="visible", timeout=timeout)
        await el.click()
        return True
    except Exception:
        return False


async def _wait_upload_complete(page: Page, max_polls: int = 360) -> bool:
    """等网页上传从 X% 跑到 100% 再发布。浏览器上传靠窗口开着才传得完，
    若上传到一半就点发布并关闭浏览器，上传会被掐断卡在中途（如 76%）。
    出现“处理/检查/上传完成”或不再“正在上传”即视为传完。max_polls*5s=30min 上限。"""
    last = ""
    for _ in range(max_polls):
        txt = ""
        for sel in (".progress-label", "span.progress-label", "ytcp-video-upload-progress"):
            loc = page.locator(sel).first
            try:
                if await loc.count():
                    txt = (await loc.inner_text()).strip()
                    if txt:
                        break
            except Exception:
                pass
        if txt:
            if any(k in txt for k in ("处理", "检查", "上传完成", "已上传", "Processing", "complete", "Checks", "Finished")):
                youtube_logger.info(_msg("✅", f"上传完成: {txt[:40]}"))
                return True
            if txt != last:
                youtube_logger.info(_msg("⏳", f"上传中: {txt[:40]}"))
                last = txt
        await page.wait_for_timeout(5000)
    youtube_logger.warning(_msg("⚠️", "等上传超时(30min)，仍尝试发布"))
    return False


class YouTubeVideo(BaseVideoUploader):
    def __init__(self, title, file_path, tags, account_file, *,
                 description="", thumbnail_path=None, playlist=None,
                 visibility="public", debug=DEBUG_MODE, headless=False):
        self.title = title
        self.file_path = str(file_path)
        self.tags = tags or []
        self.account_file = str(account_file)
        self.description = description or ""
        self.thumbnail_path = str(thumbnail_path) if thumbnail_path else None
        self.playlist = playlist
        self.visibility = visibility if visibility in VISIBILITY else "public"
        self.debug = debug
        self.headless = headless

    async def upload(self, playwright: Playwright) -> None:
        browser = await launch_optional_browser(playwright, platform="youtube", 
            **_chrome_launch_options(
                headless=self.headless,
                proxy={"server": YT_PROXY} if YT_PROXY else None,
            )
        )
        context = await browser.new_context(storage_state=self.account_file)
        context = await set_init_script(context)
        page = await context.new_page()
        page.set_default_timeout(60000)

        youtube_logger.info(_msg("🎬", f"开始上传: {Path(self.file_path).name}"))
        await page.goto(UPLOAD_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        if "accounts.google.com" in page.url or "signin" in page.url.lower():
            await browser.close()
            raise RuntimeError("YouTube 登录态失效，请重新执行 login")

        # 1) 选择视频文件
        file_input = page.locator('input[type="file"]').first
        await file_input.wait_for(state="attached", timeout=60000)
        await file_input.set_input_files(self.file_path)

        # 2) 等详情对话框
        await page.locator("#title-textarea").wait_for(state="visible", timeout=120000)

        # 3) 标题
        youtube_logger.info(_msg("✍️", "填写标题"))
        await _fill_editable(page, "#title-textarea #textbox", self.title[:100])

        # 4) 简介
        if self.description.strip():
            youtube_logger.info(_msg("✍️", "填写简介"))
            await _fill_editable(page, "#description-textarea #textbox", self.description)

        # 5) 封面（处理到一定进度才允许传，失败不致命）
        if self.thumbnail_path and Path(self.thumbnail_path).exists():
            try:
                thumb_input = page.locator(
                    "#file-loader input[type='file'], ytcp-thumbnail-uploader input[type='file']"
                ).first
                await thumb_input.wait_for(state="attached", timeout=20000)
                await thumb_input.set_input_files(self.thumbnail_path)
                await page.wait_for_timeout(2000)
                youtube_logger.info(_msg("🖼️", "封面已上传"))
            except Exception as exc:
                youtube_logger.warning(_msg("⚠️", f"封面上传跳过（不影响发布）: {exc}"))

        # 6) 加入播放列表（连载/系列追更）。弹窗务必关闭，否则挡住后续步骤。
        if self.playlist:
            try:
                await _click_if_present(
                    page, "#basics ytcp-text-dropdown-trigger, ytcp-video-metadata-playlists ytcp-dropdown-trigger", 8000)
                await page.wait_for_timeout(1200)
                existing = page.locator(
                    f"tp-yt-paper-checkbox:has-text('{self.playlist}'), "
                    f"ytcp-checkbox-group:has-text('{self.playlist}')").first
                if await existing.count():
                    await existing.click()
                else:
                    if await _click_if_present(page, "ytcp-button:has-text('New playlist'), ytcp-button:has-text('创建播放列表')", 4000):
                        await page.wait_for_timeout(800)
                        await _click_if_present(page, "tp-yt-paper-item:has-text('New playlist'), tp-yt-paper-item:has-text('新建播放列表')", 3000)
                        title_box = page.locator("ytcp-playlist-metadata-editor #textbox, #create-playlist-form #textbox").first
                        if await title_box.count():
                            await title_box.click()
                            await title_box.type(self.playlist, delay=6)
                            await _click_if_present(page, "ytcp-button#create-button, tp-yt-paper-dialog ytcp-button:has-text('Create'), tp-yt-paper-dialog ytcp-button:has-text('创建')", 4000)
            except Exception as exc:
                youtube_logger.warning(_msg("⚠️", f"播放列表处理跳过（不影响发布）: {exc}"))
            finally:
                await _click_if_present(page, "ytcp-playlist-dialog #save-button, ytcp-button:has-text('Done'), ytcp-button:has-text('完成')", 3000)
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(600)

        # 7) 受众：非儿童向（必填）
        if not await _click_if_present(page, "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']", 10000):
            await _click_if_present(page, "tp-yt-paper-radio-button:has-text('not made for kids'), tp-yt-paper-radio-button:has-text('不是面向儿童')", 6000)

        # 8) 标签（“显示更多”里）
        if self.tags:
            try:
                await _click_if_present(page, "#toggle-button", 6000)
                await page.wait_for_timeout(800)
                tag_input = page.locator("#tags-container #text-input, ytcp-form-input-container#tags-container input").first
                await tag_input.click()
                await tag_input.type(",".join(self.tags)[:500] + ",", delay=4)
            except Exception as exc:
                youtube_logger.warning(_msg("⚠️", f"标签填写跳过（不影响发布）: {exc}"))

        # 9) 连点 Next 到“可见性”步骤
        for _ in range(5):
            vis = page.locator("tp-yt-paper-radio-button[name='PUBLIC']")
            if await vis.count() and await vis.first.is_visible():
                break
            if not await _click_if_present(page, "#next-button", 6000):
                await page.wait_for_timeout(1200)
            await page.wait_for_timeout(1000)

        # 10) 可见性
        youtube_logger.info(_msg("🌐", f"设置可见性 = {self.visibility}"))
        await _click_if_present(page, f"tp-yt-paper-radio-button[name='{VISIBILITY[self.visibility]}']", 10000)

        # 10.5) 关键：等上传真正传完再发布。浏览器上传靠窗口开着传，
        #       传到一半就点发布+关浏览器 = 上传被掐断卡在中途（如 76%）。
        youtube_logger.info(_msg("📤", "等待上传完成（传完才发布）…"))
        await _wait_upload_complete(page)

        # 11) 发布
        await page.wait_for_timeout(1200)
        if not await _click_if_present(page, "#done-button", 15000):
            youtube_logger.warning(_msg("🤔", "未找到发布按钮，可能上传未到可发布进度；请在窗口里手动发布"))
        else:
            await page.wait_for_timeout(4000)
            video_url = ""
            try:
                link = page.locator("a[href*='youtu.be'], a[href*='watch?v=']").first
                if await link.count():
                    video_url = await link.get_attribute("href") or ""
            except Exception:
                pass
            await _click_if_present(page, "ytcp-button:has-text('Close'), ytcp-button:has-text('关闭'), #close-button", 8000)
            youtube_logger.success(_msg("🥳", f"发布完成（{self.visibility}）{(' ' + video_url) if video_url else ''}"))

        # 刷新 cookie
        try:
            await context.storage_state(path=self.account_file)
        except Exception:
            pass
        await page.wait_for_timeout(2000)
        await browser.close()

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
