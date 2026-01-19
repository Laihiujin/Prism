"""
DOM 选择器配置管理器
支持配置化、优先级、降级、失败快照

解决问题：
- 视频号 DOM 频繁变动，选择器硬编码难以维护
- 缺少失败降级策略
- 修改选择器需要改代码并重启

使用方式：
    from myUtils.selector_manager import selector_manager

    # 查找元素（按优先级尝试多个选择器）
    file_input = await selector_manager.find_element(
        page=page,
        platform="channels",
        element_name="file_upload"
    )

    # 尝试触发按钮
    triggered = await selector_manager.try_trigger_buttons(
        page=page,
        platform="channels",
        element_name="file_upload"
    )
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout, Locator
from loguru import logger
from datetime import datetime


class SelectorManager:
    """选择器管理器"""

    def __init__(self, config_dir: Path = None):
        if config_dir is None:
            from config.conf import BASE_DIR
            config_dir = Path(BASE_DIR) / "syn_backend" / "config" / "selectors"

        self.config_dir = config_dir
        self.configs: Dict[str, Dict] = {}
        self._load_all_configs()

    def _load_all_configs(self):
        """加载所有选择器配置"""
        if not self.config_dir.exists():
            logger.warning(f"⚠️ 选择器配置目录不存在: {self.config_dir}，将跳过配置加载")
            self.config_dir.mkdir(parents=True, exist_ok=True)
            return

        config_files = list(self.config_dir.glob("*.json"))
        if not config_files:
            logger.warning(f"⚠️ 配置目录为空: {self.config_dir}")
            return

        for config_file in config_files:
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    platform = config.get("platform")
                    if platform:
                        self.configs[platform] = config
                        logger.info(f"✅ 加载选择器配置: {platform} (版本: {config.get('version')})")
            except Exception as e:
                logger.error(f"❌ 加载选择器配置失败 {config_file}: {e}")

    def reload_config(self, platform: str = None):
        """重新加载配置（无需重启应用）"""
        if platform:
            # 重新加载指定平台
            config_file = self.config_dir / f"{platform}_upload.json"
            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        self.configs[platform] = config
                        logger.info(f"✅ 重新加载配置: {platform}")
                except Exception as e:
                    logger.error(f"❌ 重新加载配置失败: {e}")
        else:
            # 重新加载所有配置
            self.configs.clear()
            self._load_all_configs()

    async def find_element(
        self,
        page: Page,
        platform: str,
        element_name: str,
        **kwargs
    ) -> Optional[Locator]:
        """
        根据配置查找元素，按优先级尝试

        Args:
            page: Playwright Page 对象
            platform: 平台名称 (douyin, channels, bilibili, kuaishou, xiaohongshu)
            element_name: 元素名称 (file_upload, title_input, publish_button, etc.)
            **kwargs: 额外参数传递给 locator

        Returns:
            Playwright Locator 对象，或 None
        """
        config = self.configs.get(platform)
        if not config:
            logger.warning(f"⚠️ 未找到平台 {platform} 的选择器配置，使用默认方式")
            return None

        selectors_config = config.get("selectors", {}).get(element_name)
        if not selectors_config:
            logger.warning(f"⚠️ 未找到元素 {element_name} 的配置")
            return None

        priority_list = selectors_config.get("priority", [])
        if not priority_list:
            logger.warning(f"⚠️ 元素 {element_name} 没有配置优先级列表")
            return None

        # 按优先级尝试每个选择器
        for idx, selector_def in enumerate(priority_list):
            try:
                selector_type = selector_def["type"]
                selector_value = selector_def["value"]
                timeout = selector_def.get("timeout", 3000)

                logger.debug(f"[{platform}] 尝试选择器 {idx+1}/{len(priority_list)}: {selector_type}={selector_value}")

                # 根据类型定位
                if selector_type == "css":
                    locator = page.locator(selector_value)
                elif selector_type == "xpath":
                    locator = page.locator(f"xpath={selector_value}")
                elif selector_type == "text":
                    locator = page.get_by_text(selector_value)
                elif selector_type == "role":
                    role = selector_value
                    name = selector_def.get("name")
                    locator = page.get_by_role(role, name=name)
                else:
                    logger.warning(f"⚠️ 不支持的选择器类型: {selector_type}")
                    continue

                # 等待元素出现
                await locator.first.wait_for(state="visible", timeout=timeout)

                logger.success(f"✅ [{platform}] 找到元素: {element_name} (使用选择器 {idx+1})")
                return locator

            except PlaywrightTimeout:
                logger.debug(f"⏱️ 选择器超时 (尝试 {idx+1}/{len(priority_list)})")
                continue
            except Exception as e:
                logger.debug(f"⚠️ 选择器错误: {e}")
                continue

        # 所有选择器都失败，处理降级
        await self._handle_fallback(page, platform, element_name, selectors_config)
        return None

    async def _handle_fallback(
        self,
        page: Page,
        platform: str,
        element_name: str,
        config: Dict
    ):
        """处理选择器失败的降级策略"""
        fallback = config.get("fallback", "error")

        if fallback == "manual_intervention":
            logger.error(f"❌ [{platform}] 元素 {element_name} 未找到，需要人工介入")

            # 截图保存
            if config.get("dynamic_detection", {}).get("snapshot_on_failure", True):
                from config.conf import BASE_DIR
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = Path(BASE_DIR) / "syn_backend" / "logs" / f"{platform}_{element_name}_fail_{timestamp}.png"
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)

                try:
                    await page.screenshot(path=str(screenshot_path), full_page=True)
                    logger.warning(f"📸 已保存失败截图: {screenshot_path}")

                    # 保存 HTML 快照用于分析
                    html_path = screenshot_path.with_suffix(".html")
                    html = await page.content()
                    html_path.write_text(html, encoding='utf-8')
                    logger.warning(f"📄 已保存 HTML 快照: {html_path}")

                except Exception as e:
                    logger.error(f"保存快照失败: {e}")

        elif fallback == "skip":
            logger.warning(f"⏭️ [{platform}] 跳过元素 {element_name}")

        else:
            # 默认抛出异常
            raise Exception(f"[{platform}] 关键元素 {element_name} 未找到，发布失败")

    async def try_trigger_buttons(
        self,
        page: Page,
        platform: str,
        element_name: str
    ) -> bool:
        """
        尝试点击触发按钮以显示隐藏的元素

        Args:
            page: Playwright Page 对象
            platform: 平台名称
            element_name: 元素名称

        Returns:
            bool - 是否成功触发
        """
        config = self.configs.get(platform, {}).get("selectors", {}).get(element_name, {})
        trigger_buttons = config.get("trigger_buttons", [])

        if not trigger_buttons:
            return False

        for btn_def in trigger_buttons:
            try:
                btn_type = btn_def["type"]
                btn_value = btn_def["value"]
                action = btn_def.get("action", "click")

                logger.debug(f"[{platform}] 尝试触发按钮: {btn_type}={btn_value}")

                # 定位触发按钮
                if btn_type == "css":
                    btn = page.locator(btn_value)
                elif btn_type == "text":
                    btn = page.get_by_text(btn_value)
                elif btn_type == "role":
                    btn = page.get_by_role(btn_value)
                else:
                    continue

                # 检查按钮是否存在
                if await btn.count() > 0:
                    logger.info(f"✅ [{platform}] 找到触发按钮: {btn_value}")

                    # 执行操作
                    if action == "click":
                        await btn.first.click()
                        logger.success(f"✅ [{platform}] 已点击触发按钮")
                    elif action == "hover":
                        await btn.first.hover()
                        logger.success(f"✅ [{platform}] 已悬停触发按钮")

                    # 等待元素出现
                    await page.wait_for_timeout(1000)
                    return True

            except Exception as e:
                logger.debug(f"⚠️ 触发按钮失败: {e}")
                continue

        return False

    def get_config(self, platform: str) -> Optional[Dict]:
        """获取平台的完整配置"""
        return self.configs.get(platform)

    def list_platforms(self) -> List[str]:
        """列出已配置的平台"""
        return list(self.configs.keys())

    def validate_config(self, platform: str) -> Dict:
        """验证配置完整性"""
        config = self.configs.get(platform)
        if not config:
            return {
                "is_valid": False,
                "errors": [f"平台 {platform} 配置不存在"]
            }

        errors = []
        warnings = []

        # 检查必要字段
        if not config.get("platform"):
            errors.append("缺少 'platform' 字段")

        if not config.get("version"):
            warnings.append("缺少 'version' 字段")

        if not config.get("selectors"):
            errors.append("缺少 'selectors' 字段")

        # 检查每个选择器配置
        selectors = config.get("selectors", {})
        for element_name, selector_config in selectors.items():
            if not selector_config.get("priority"):
                errors.append(f"元素 '{element_name}' 缺少 'priority' 列表")

            priority_list = selector_config.get("priority", [])
            for idx, selector_def in enumerate(priority_list):
                if "type" not in selector_def:
                    errors.append(f"元素 '{element_name}' 的选择器 #{idx+1} 缺少 'type'")
                if "value" not in selector_def:
                    errors.append(f"元素 '{element_name}' 的选择器 #{idx+1} 缺少 'value'")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "total_selectors": len(selectors)
        }


# 全局实例
selector_manager = SelectorManager()
