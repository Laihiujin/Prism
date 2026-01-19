"""
平台基类 - 定义统一的平台API接口规范
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from playwright.async_api import Page, BrowserContext
import logging

logger = logging.getLogger(__name__)


class BasePlatform(ABC):
    """平台基类 - 所有平台模块都应继承此类"""
    
    def __init__(self, platform_code: int, platform_name: str):
        self.platform_code = platform_code
        self.platform_name = platform_name
        
    @abstractmethod
    async def login(self, account_id: str, **kwargs) -> Dict[str, Any]:
        """
        登录接口
        
        Args:
            account_id: 账号ID（用于保存cookie文件名）
            **kwargs: 其他平台特定参数
            
        Returns:
            {
                "success": bool,
                "message": str,
                "data": {...}  # 平台特定数据
            }
        """
        pass
    
    @abstractmethod
    async def upload(self, 
                    account_file: str,
                    title: str,
                    file_path: str,
                    tags: list,
                    **kwargs) -> Dict[str, Any]:
        """
        上传视频接口
        
        Args:
            account_file: 账号cookie文件路径
            title: 视频标题
            file_path: 视频文件路径
            tags: 标签列表
            **kwargs: 其他平台特定参数（如定时发布、POI等）
            
        Returns:
            {
                "success": bool,
                "message": str,
                "data": {...}
            }
        """
        pass
    
    async def handle_verification(self, 
                                  page: Page, 
                                  account_id: str,
                                  trigger_selector: Optional[str] = None) -> bool:
        """
        处理验证码流程（通用方法）
        
        Args:
            page: Playwright Page对象
            account_id: 账号ID
            trigger_selector: 触发验证码按钮的选择器（如"获取验证码"）
            
        Returns:
            是否验证成功
        """
        from .verification import verification_manager
        
        # 如果提供了trigger_selector，先点击触发按钮
        if trigger_selector:
            try:
                btn = page.locator(trigger_selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    logger.info(f"已点击验证码触发按钮: {trigger_selector}")
            except Exception as e:
                logger.warning(f"点击验证码按钮失败: {e}")
        
        # 请求验证码
        verification_manager.request_verification(
            account_id=account_id,
            platform=self.platform_code,
            message=f"{self.platform_name}需要验证码，请输入6位数字"
        )
        
        # 等待用户输入
        code = await verification_manager.wait_for_code(account_id, timeout=120)
        if not code:
            return False
        
        # 填入验证码（子类可以覆盖这个方法来自定义填入逻辑）
        return await self.fill_verification_code(page, code)
    
    async def fill_verification_code(self, page: Page, code: str) -> bool:
        """
        填入验证码（默认实现，子类可覆盖）
        
        Args:
            page: Playwright Page对象
            code: 验证码
            
        Returns:
            是否填入成功
        """
        try:
            # 尝试常见的验证码输入框选择器
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
                    logger.info(f"已填入验证码: {selector}")
                    
                    # 尝试点击提交/验证按钮
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
                            logger.info(f"已点击提交按钮: {btn_selector}")
                            return True
                    return True
            
            logger.error("未找到验证码输入框")
            return False
        except Exception as e:
            logger.error(f"填入验证码失败: {e}")
            return False
