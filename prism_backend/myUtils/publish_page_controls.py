"""Interact with publishing controls without removing business DOM."""
import re


async def douyin_video_upload_input(page):
    """Use the hidden video input, recovering one redirect to creator home."""
    await dismiss_publish_guides(page)
    video = page.locator('input[type="file"][accept*="video"]')
    try:
        await video.wait_for(state="attached", timeout=15000)
    except Exception as exc:
        if "/creator-micro/home" not in page.url:
            raise RuntimeError(f"抖音视频上传控件未挂载，当前页面：{page.url}") from exc
        await dismiss_publish_guides(page)
        await page.goto("https://creator.douyin.com/creator-micro/content/upload", wait_until="domcontentloaded")
        await dismiss_publish_guides(page)
        await video.wait_for(state="attached", timeout=15000)
    return video


GUIDE_SELECTORS = (
    '.semi-popover-content',
    '[id^="react-joyride-step"], .react-joyride__tooltip',
    '.shepherd-element, [class*="guide-modal"], [class*="tour-tooltip"], [class*="mention-wrapper"]',
    '[role="dialog"], [role="alertdialog"]',
)
GUIDE_TEXT = re.compile(r"新版本|新版|新增|新功能|欢迎体验|引导|下一步|新手|视频预览功能")


async def dismiss_publish_guides(page, max_steps=6):
    """Click Skip/acknowledge inside a recognized guide; never force-click/delete."""
    closed = 0
    for _ in range(max_steps):
        acted = False
        for selector in GUIDE_SELECTORS:
            containers = page.locator(selector)
            for index in range(await containers.count()):
                container = containers.nth(index)
                if not await container.is_visible():
                    continue
                text = await container.inner_text()
                if not GUIDE_TEXT.search(text) and not await container.locator('[data-action="skip"], [aria-label="Skip"]').count():
                    continue
                for label in ("跳过", "暂不", "稍后再说", "我知道了", "知道了", "完成"):
                    control = container.get_by_text(label, exact=True)
                    if await control.count() == 1 and await control.is_visible():
                        await control.click(timeout=1500)
                        acted = True
                        break
                if not acted:
                    control = container.locator('[data-action="skip"], [aria-label="Skip"]')
                    if await control.count() == 1 and await control.is_visible():
                        await control.click(timeout=1500)
                        acted = True
                if acted:
                    closed += 1
                    await page.wait_for_timeout(150)
                    break
            if acted:
                break
        if not acted:
            break
    return closed


async def set_radio_choice(page, label, value):
    """Only select a unique option in the labeled row and verify its state."""
    anchor = page.get_by_text(label, exact=True)
    if await anchor.count() != 1:
        raise ValueError(f"发布页未找到唯一的「{label}」配置")
    row = anchor.locator('xpath=..')
    for _ in range(4):
        options = row.locator('label, [role="radio"]')
        target = options.filter(has_text=re.compile(r"^\s*" + re.escape(value) + r"\s*$"))
        if await target.count() == 1:
            await target.click(timeout=3000)
            selected = await target.evaluate("el => el.getAttribute('aria-checked') === 'true' || el.getAttribute('data-checked') === 'true' || !!el.querySelector('input:checked') || /radio-wrapper-checked/.test(el.className)")
            if not selected:
                raise ValueError(f"「{label}」未成功选中「{value}」")
            return
        row = row.locator('xpath=..')
    raise ValueError(f"发布页「{label}」不支持「{value}」")


async def set_named_switch(page, label, checked):
    anchor = page.get_by_text(label, exact=True)
    if await anchor.count() != 1:
        raise ValueError(f"发布页未找到唯一的「{label}」开关")
    row = anchor.locator('xpath=..')
    for _ in range(4):
        switch = row.locator('[role="switch"], input[type="checkbox"]')
        if await switch.count() == 1:
            await switch.set_checked(checked, timeout=3000)
            state = await switch.evaluate("el => el.getAttribute('aria-checked') === 'true' || el.checked === true")
            if state != checked:
                raise ValueError(f"「{label}」开关未生效")
            return
        row = row.locator('xpath=..')
    raise ValueError(f"发布页未找到「{label}」开关")
