import asyncio
import random
import re
import json
from pathlib import Path
from playwright.async_api import Page, async_playwright
from myUtils.cookie_manager import cookie_manager

# 动态加载配置
def load_guide_config():
    """动态加载引导关键词配置"""
    config_file = Path(__file__).parent.parent / "config" / "guide_config.json"
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get("guide_keywords", []), config.get("close_selectors", [])
    
    # 默认配置
    return [
        r"我知道了", r"好的", r"下一步", r"我了解了", r"我学会了", 
        r"开始体验", r"跳过", r"关闭", r"Got it", r"Next", r"Skip",
        r"立即体验", r"不再提示", r"确定"
    ], [
        ".close", ".close-btn", "button[aria-label='Close']", 
        ".ant-modal-close", ".el-dialog__headerbtn"
    ]

# 红色/高亮按钮的特征 (辅助判断)
HIGHLIGHT_CLASSES = ["primary", "red", "confirm", "blue", "active"]

async def dismiss_guides(page: Page, duration: int = 60, platform: str = "unknown", enable_learning: bool = True):
    """
    智能消除引导弹窗
    :param page: Playwright Page对象
    :param duration: 持续检测时间(秒)，默认60秒
    :param platform: 平台名称，用于学习系统
    :param enable_learning: 是否启用学习模式
    """
    print(f"🛡️ [Guide Guard] 开始检测引导弹窗 (持续 {duration} 秒)...")
    
    # 动态加载配置
    GUIDE_KEYWORDS, close_selectors = load_guide_config()
    
    # 加载学习系统
    learner = None
    if enable_learning:
        try:
            from myUtils.guide_learner import learner as guide_learner
            learner = guide_learner
            print(f"🤖 [Guide Guard] 学习模式已启用")
        except Exception as e:
            print(f"⚠️ [Guide Guard] 学习系统加载失败: {e}")
    
    end_time = asyncio.get_event_loop().time() + duration
    
    # 编译正则
    pattern = re.compile("|".join(GUIDE_KEYWORDS))
    
    while asyncio.get_event_loop().time() < end_time:
        try:
            # 1. 查找包含关键词的按钮或可点击元素
            # 我们查找 button, a, div 等可能是按钮的元素
            # 使用 Playwright 的 locator 配合 filter
            
            found_action = False
            
            # 策略A: 直接搜索文本
            for keyword in GUIDE_KEYWORDS:
                # 查找可见的、包含关键词的元素
                # 注意：这里可能会找到多个，我们只点最上层的
                elements = page.get_by_text(keyword, exact=False)
                count = await elements.count()
                
                for i in range(count):
                    elem = elements.nth(i)
                    if await elem.is_visible():
                        # 检查是否是按钮状
                        tag_name = await elem.evaluate("el => el.tagName.toLowerCase()")
                        role = await elem.get_attribute("role")
                        
                        # 如果是 button, a, 或者有 button role，或者被包含在 button 中
                        is_clickable = tag_name in ['button', 'a'] or role == 'button'
                        
                        # 如果不是直接的可点击元素，尝试找父级
                        if not is_clickable:
                            parent = elem.locator("..")
                            if await parent.count() > 0:
                                p_tag = await parent.evaluate("el => el.tagName.toLowerCase()")
                                if p_tag in ['button', 'a']:
                                    elem = parent
                                    is_clickable = True
                        
                        if is_clickable:
                            print(f"👆 [Guide Guard] 点击引导按钮: '{keyword}'")
                            try:
                                await elem.click(timeout=1000)
                                found_action = True
                                await asyncio.sleep(1) # 等待UI反应
                                break # 重新扫描
                            except Exception as e:
                                print(f"  ⚠️ 点击失败: {e}")
                
                if found_action: break
            
            # 策略B: 查找常见的弹窗关闭按钮 (X)
            # 很多弹窗右上角有个 X，通常是 svg 或特定的 class
            close_selectors = [
                ".close", ".close-btn", "button[aria-label='Close']", 
                ".ant-modal-close", ".el-dialog__headerbtn"
            ]
            for sel in close_selectors:
                if await page.locator(sel).count() > 0:
                    elem = page.locator(sel).first
                    if await elem.is_visible():
                        print(f"👆 [Guide Guard] 点击关闭图标: {sel}")
                        try:
                            await elem.click()
                            found_action = True
                            await asyncio.sleep(1)
                        except: pass

            # 如果没有发现任何操作，就稍微等待一下
            if not found_action:
                await asyncio.sleep(2)
            else:
                # 如果执行了操作，可能还有下一个引导，稍微快点重试
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"⚠️ [Guide Guard] 扫描循环出错: {e}")
            await asyncio.sleep(2)

    print("✅ [Guide Guard] 检测结束")

async def maintain_account(platform_code: int, cookie_file: str, headless: bool = True):
    """
    对单个账号执行维护：登录 -> 停留 -> 清除弹窗
    """
    # 映射平台URL
    urls = {
        1: "https://creator.xiaohongshu.com/creator-micro/content/upload", # XHS
        2: "https://channels.weixin.qq.com/platform", # Tencent
        3: "https://creator.douyin.com/creator-micro/content/upload", # Douyin
        4: "https://cp.kuaishou.com/article/publish/video", # Kuaishou
        5: "https://member.bilibili.com/platform/home" # Bilibili
    }
    
    target_url = urls.get(platform_code)
    if not target_url:
        print(f"Unknown platform code: {platform_code}")
        return

    file_path = cookie_manager._resolve_cookie_path(cookie_file)
    if not file_path.exists():
        print(f"Cookie file not found: {file_path}")
        return

    print(f"🔧 [Maintenance] 开始维护账号: {cookie_file} ({target_url})")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(storage_state=file_path)
        page = await context.new_page()
        
        try:
            await page.goto(target_url, timeout=30000)
            await page.wait_for_load_state("domcontentloaded")
            
            # 检查是否登录失效
            if "login" in page.url or "passport" in page.url:
                print("❌ [Maintenance] 登录失效，无法维护")
                return "expired"

            # 执行引导消除 (停留 60s)
            await dismiss_guides(page, duration=60)
            
            print("✅ [Maintenance] 维护完成")
            return "success"
            
        except Exception as e:
            print(f"❌ [Maintenance] 维护出错: {e}")
            return "error"
        finally:
            await browser.close()
