"""YouTube Studio uploader built on Prism's Patchright runtime.

Google sign-in has no reliable QR-code flow for this application.  Login is a
visible, local-browser operation; its storage state is then reused by queued
uploads.  The uploader intentionally waits for the upload to complete before
clicking the final visibility action.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Optional

from utils.automation_provider import Page, async_playwright
from utils.base_social_media import set_init_script
from utils.log import youtube_logger


STUDIO_URL = "https://studio.youtube.com"
UPLOAD_URL = "https://www.youtube.com/upload"
VISIBILITY = {"public": "PUBLIC", "unlisted": "UNLISTED", "private": "PRIVATE"}


async def _launch_chromium(playwright: Any, *, headless: bool, proxy: Optional[str] = None):
    options: dict[str, Any] = {"headless": headless}
    if proxy:
        options["proxy"] = {"server": proxy}
    # Chrome has the most reliable existing Google sign-in profile support.
    # Patchright's bundled Chromium remains a portable fallback (including Docker).
    try:
        return await playwright.chromium.launch(channel="chrome", **options)
    except Exception:
        return await playwright.chromium.launch(**options)


def _is_signed_in(url: str) -> bool:
    normalized = (url or "").lower()
    return "accounts.google.com" not in normalized and "signin" not in normalized


async def cookie_auth(account_file: str) -> bool:
    if not Path(account_file).is_file():
        return False
    async with async_playwright() as playwright:
        browser = await _launch_chromium(playwright, headless=True)
        try:
            context = await browser.new_context(storage_state=account_file)
            context = await set_init_script(context)
            page = await context.new_page()
            await page.goto(STUDIO_URL, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(2_500)
            return _is_signed_in(page.url) and ("studio.youtube.com" in page.url or "/channel/" in page.url)
        except Exception:
            return False
        finally:
            await browser.close()


async def youtube_cookie_gen(account_file: str) -> bool:
    """Open a visible local browser and save storage state after Studio login."""
    Path(account_file).parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await _launch_chromium(playwright, headless=False, proxy=os.getenv("YT_PROXY"))
        context = await browser.new_context()
        context = await set_init_script(context)
        page = await context.new_page()
        try:
            await page.goto(STUDIO_URL, wait_until="domcontentloaded", timeout=60_000)
            youtube_logger.info("Please sign in to Google / YouTube Studio in the opened browser (timeout: 10 minutes).")
            for _ in range(600):
                if _is_signed_in(page.url) and ("studio.youtube.com" in page.url or "/channel/" in page.url):
                    await page.wait_for_timeout(1_000)
                    await context.storage_state(path=account_file)
                    youtube_logger.success(f"YouTube login state saved: {account_file}")
                    return True
                await asyncio.sleep(1)
            youtube_logger.error("YouTube interactive login timed out.")
            return False
        finally:
            await context.close()
            await browser.close()


async def youtube_setup(account_file: str, handle: bool = False) -> bool:
    if await cookie_auth(account_file):
        return True
    return await youtube_cookie_gen(account_file) if handle else False


async def _click(page: Page, selector: str, timeout: int = 8_000) -> bool:
    try:
        locator = page.locator(selector).first
        await locator.wait_for(state="visible", timeout=timeout)
        await locator.click()
        return True
    except Exception:
        return False


async def _fill_editable(page: Page, selector: str, value: str) -> None:
    locator = page.locator(selector).first
    await locator.wait_for(state="visible", timeout=30_000)
    await locator.click()
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Delete")
    try:
        await locator.fill(value)
    except Exception:
        await locator.type(value, delay=4)


async def _wait_for_upload(page: Page, timeout_seconds: int = 1_800) -> None:
    """Wait until Studio enables the completion action or exposes a completion label."""
    polls = max(1, timeout_seconds // 5)
    for _ in range(polls):
        done = page.locator("#done-button").first
        try:
            if await done.count() and await done.is_enabled():
                return
        except Exception:
            pass
        labels = page.locator(".progress-label, ytcp-video-upload-progress").first
        try:
            text = (await labels.inner_text()).lower()
            if any(marker in text for marker in ("complete", "finished", "checks", "处理完毕", "上传完成")):
                return
        except Exception:
            pass
        await page.wait_for_timeout(5_000)
    raise TimeoutError("YouTube upload did not become publishable within 30 minutes")


async def _set_playlist(page: Page, playlist: str) -> None:
    """Select an existing Studio playlist; missing playlists never block publishing."""
    opened = await _click(
        page,
        "ytcp-video-metadata-playlists ytcp-dropdown-trigger, #basics ytcp-text-dropdown-trigger",
        8_000,
    )
    if not opened:
        youtube_logger.warning("YouTube playlist menu was unavailable; continuing without a playlist.")
        return
    await page.wait_for_timeout(750)
    option = page.locator(
        f"tp-yt-paper-checkbox:has-text('{playlist}'), ytcp-checkbox-group:has-text('{playlist}')"
    ).first
    try:
        await option.wait_for(state="visible", timeout=5_000)
        await option.click()
        await _click(page, "ytcp-playlist-dialog #save-button, ytcp-button:has-text('Done'), ytcp-button:has-text('完成')", 5_000)
    except Exception:
        youtube_logger.warning(f"YouTube playlist '{playlist}' was not found; continuing without it.")
    finally:
        await page.keyboard.press("Escape")


class YouTubeVideo:
    def __init__(
        self,
        title: str,
        file_path: str,
        tags: list[str],
        account_file: str,
        *,
        description: str = "",
        thumbnail_path: Optional[str] = None,
        playlist: Optional[str] = None,
        visibility: str = "public",
    ) -> None:
        self.title = title
        self.file_path = file_path
        self.tags = tags
        self.account_file = account_file
        self.description = description
        self.thumbnail_path = thumbnail_path
        self.playlist = playlist
        self.visibility = visibility.lower() if visibility.lower() in VISIBILITY else "public"

    async def main(self) -> dict[str, Any]:
        if not Path(self.file_path).is_file():
            raise FileNotFoundError(self.file_path)
        if not await cookie_auth(self.account_file):
            raise RuntimeError("YouTube login state is missing or expired; run `prism youtube login` first.")

        async with async_playwright() as playwright:
            browser = await _launch_chromium(playwright, headless=False, proxy=os.getenv("YT_PROXY"))
            context = await browser.new_context(storage_state=self.account_file)
            context = await set_init_script(context)
            page = await context.new_page()
            page.set_default_timeout(60_000)
            try:
                await page.goto(UPLOAD_URL, wait_until="domcontentloaded")
                if not _is_signed_in(page.url):
                    raise RuntimeError("YouTube redirected to Google sign-in; run `prism youtube login` again.")

                file_input = page.locator("input[type='file']").first
                await file_input.wait_for(state="attached", timeout=60_000)
                await file_input.set_input_files(self.file_path)
                await page.locator("#title-textarea").wait_for(state="visible", timeout=120_000)
                await _fill_editable(page, "#title-textarea #textbox", self.title[:100])
                if self.description.strip():
                    await _fill_editable(page, "#description-textarea #textbox", self.description[:5_000])

                if self.thumbnail_path and Path(self.thumbnail_path).is_file():
                    thumbnail = page.locator("ytcp-thumbnail-uploader input[type='file']").first
                    try:
                        await thumbnail.set_input_files(self.thumbnail_path)
                    except Exception as exc:
                        youtube_logger.warning(f"YouTube thumbnail skipped: {exc}")

                if self.playlist:
                    await _set_playlist(page, self.playlist)

                await _click(page, "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']", 12_000)
                if self.tags:
                    if await _click(page, "#toggle-button", 6_000):
                        tag_input = page.locator("#tags-container input, ytcp-form-input-container#tags-container input").first
                        try:
                            await tag_input.fill(",".join(self.tags)[:500])
                        except Exception:
                            youtube_logger.warning("YouTube tags field was unavailable; continuing without tags.")

                for _ in range(5):
                    visibility = page.locator(f"tp-yt-paper-radio-button[name='{VISIBILITY[self.visibility]}']").first
                    if await visibility.count() and await visibility.is_visible():
                        break
                    await _click(page, "#next-button")
                    await page.wait_for_timeout(800)
                await _click(page, f"tp-yt-paper-radio-button[name='{VISIBILITY[self.visibility]}']", 12_000)
                await _wait_for_upload(page)

                if not await _click(page, "#done-button", 20_000):
                    raise RuntimeError("YouTube Studio did not expose the final publish button")
                await page.wait_for_timeout(3_000)
                await context.storage_state(path=self.account_file)
                return {
                    "success": True,
                    "message": "YouTube upload submitted",
                    "platform": "youtube",
                    "visibility": self.visibility,
                }
            finally:
                await context.close()
                await browser.close()
