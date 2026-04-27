from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

BrowserContext = Any
Page = Any

logger = logging.getLogger(__name__)


class BasePlatform(ABC):
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
        from .verification import verification_manager

        if trigger_selector:
            try:
                btn = page.locator(trigger_selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    logger.info(f"clicked verification trigger: {trigger_selector}")
            except Exception as e:
                logger.warning(f"failed to click verification trigger: {e}")

        verification_manager.request_verification(
            account_id=account_id,
            platform=self.platform_code,
            message=f"{self.platform_name} requires verification code, please enter 6 digits",
        )

        code = await verification_manager.wait_for_code(account_id, timeout=120)
        if not code:
            return False

        return await self.fill_verification_code(page, code)

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
        except Exception as e:
            logger.error(f"failed to fill verification code: {e}")
            return False
