from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

BrowserContext = Any
Page = Any

logger = logging.getLogger(__name__)


class BasePlatform(ABC):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "upload" in cls.__dict__:
            from .publish_verification import publishing_upload
            cls.upload = publishing_upload(cls.upload)

    def __init__(self, platform_code: int, platform_name: str):
        self.platform_code = platform_code
        self.platform_name = platform_name

    @abstractmethod
    async def login(self, account_id: str, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def upload(
        self,
        account_file: str,
        title: str,
        file_path: str,
        tags: list,
        **kwargs,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    async def handle_verification(
        self,
        page: Page,
        account_id: str,
        trigger_selector: Optional[str] = None,
    ) -> bool:
        from .publish_verification import publishing, verify_page
        metadata = publishing.get() or {"platform": self.platform_code, "account": account_id}
        return await verify_page(page, metadata, trigger_selector)

    async def fill_verification_code(self, page: Page, code: str) -> bool:
        try:
            selectors = [
                "input[placeholder*='验证码']",
                "input[placeholder*='code']",
                "input[type='text'][maxlength='6']",
                ".verification-code-input input",
            ]

            for selector in selectors:
                input_field = page.locator(selector).first
                if await input_field.count() > 0:
                    await input_field.fill(code)
                    logger.info(f"filled verification code using {selector}")

                    submit_btns = [
                        "button:has-text('验证')",
                        "button:has-text('提交')",
                        "button:has-text('确定')",
                        "button:has-text('确认')",
                    ]
                    for btn_selector in submit_btns:
                        btn = page.locator(btn_selector).first
                        if await btn.count() > 0 and await btn.is_visible():
                            await btn.click()
                            logger.info(f"clicked verification submit button: {btn_selector}")
                            return True
                    return True

            logger.error("verification input not found")
            return False
        except Exception:
            logger.error("failed to fill verification code")
            return False
