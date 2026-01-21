"""
平台深度探索器 (Platform Explorer)
功能：
1. 自动导航到内容管理页面
2. 智能识别数据表格和表头
3. 发现页面上的引导弹窗和新关键词
4. 探测平台特有功能（如关联小程序、封面要求等）
"""
import asyncio
import json
import re
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright, Page, BrowserContext

# 导入配置
from config.conf import BASE_DIR, PLAYWRIGHT_HEADLESS
from myUtils.cookie_manager import cookie_manager
from myUtils.maintenance import load_guide_config

class PlatformExplorer:
    def __init__(self):
        self.guide_keywords, self.close_selectors = load_guide_config()
        self.results = {}

    def reset_results(self):
        """为每次账号探索重新初始化结果容器"""
        self.results = {
            "headers": {},      # 发现的表头
            "features": {},     # 发现的功能
            "new_guides": [],   # 新发现的引导词
            "urls": {},         # 关键页面URL
            "videos": {}        # 作品数据
        }
        
    async def start_exploration(self, account_info: dict):
        """开始探索指定账号的平台"""
        platform = account_info['platform']
        cookie_file = account_info['cookie_file']
        # 每个账号单独重置结果，避免交叉污染
        self.reset_results()
        
        print(f"🚀 [Explorer] 开始探索平台: {platform} ({account_info['name']})")
        
        cookie_path = cookie_manager._resolve_cookie_path(cookie_file)
        if not cookie_path.exists():
            print(f"❌ Cookie文件不存在: {cookie_file}")
            return
            
        async with async_playwright() as p:
            # 账号管理"跳转创作中心"功能：强制显示浏览器（便于用户操作）
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(storage_state=cookie_path)
            page = await context.new_page()
            
            try:
                # 根据平台分发任务
                if platform == 'kuaishou':
                    await self.explore_kuaishou(page)
                elif platform == 'douyin':
                    await self.explore_douyin(page)
                elif platform == 'xiaohongshu':
                    await self.explore_xiaohongshu(page)
                elif platform == 'channels':
                    await self.explore_channels(page)
                elif platform == 'bilibili':
                    await self.explore_bilibili(page)
                    
                # 保存探索结果
                self.save_results(platform)
                
            except Exception as e:
                print(f"❌ [Explorer] 探索过程中出错: {e}")
                import traceback
                traceback.print_exc()
            finally:
                await context.close()
                await browser.close()

    async def explore_kuaishou(self, page: Page):
        """快手深度探索流程"""
        print("📍 正在进入快手创作者服务平台...")
        await page.goto("https://cp.kuaishou.com/article/publish/video", timeout=30000)
        await page.wait_for_load_state("networkidle")
        
        await self.detect_and_handle_guides(page, "kuaishou_publish")
        print("🔍 探索发布页面功能...")
        await self.analyze_publish_features(page, "kuaishou")

        print("📍 导航到内容管理...")
        try:
            await page.goto("https://cp.kuaishou.com/article/manage/video")
            await page.wait_for_load_state("networkidle")
        except Exception as e:
            print(f"⚠️ 导航失败: {e}")
            
        print("📊 正在提取数据表头...")
        headers = await self.extract_table_headers(page)
        if headers:
            self.results["headers"]["kuaishou"] = headers
            print(f"✅ 发现表头: {headers}")

    async def explore_douyin(self, page: Page):
        """抖音深度探索流程"""
        print("📍 正在进入抖音创作者服务平台...")
        # 发布页面
        await page.goto("https://creator.douyin.com/creator-micro/content/upload", timeout=30000)
        await page.wait_for_load_state("networkidle")
        
        await self.detect_and_handle_guides(page, "douyin_publish")
        print("🔍 探索发布页面功能...")
        await self.analyze_publish_features(page, "douyin")

        # 内容管理页面
        print("📍 导航到内容管理...")
        try:
            await page.goto("https://creator.douyin.com/creator-micro/content/manage")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000) # 等待列表加载
            await self.extract_douyin_videos(page)
        except Exception as e:
            print(f"⚠️ 导航失败: {e}")

        print("📊 正在提取数据表头...")
        headers = await self.extract_table_headers(page)
        if headers:
            self.results["headers"]["douyin"] = headers
            print(f"✅ 发现表头: {headers}")

    async def explore_xiaohongshu(self, page: Page):
        """小红书深度探索流程"""
        print("📍 正在进入小红书创作服务平台...")
        # 发布页面
        await page.goto("https://creator.xiaohongshu.com/publish/publish", timeout=30000)
        await page.wait_for_load_state("networkidle")
        
        await self.detect_and_handle_guides(page, "xhs_publish")
        print("🔍 探索发布页面功能...")
        await self.analyze_publish_features(page, "xiaohongshu")

        # 笔记管理页面
        print("📍 导航到笔记管理...")
        try:
            await page.goto("https://creator.xiaohongshu.com/note-manager")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"⚠️ 导航失败: {e}")

        print("📊 正在提取数据表头...")
        headers = await self.extract_table_headers(page)
        if headers:
            self.results["headers"]["xiaohongshu"] = headers
            print(f"✅ 发现表头: {headers}")

    async def explore_channels(self, page: Page):
        """视频号深度探索流程"""
        print("📍 正在进入视频号助手...")
        # 发布页面
        await page.goto("https://channels.weixin.qq.com/platform/post/create", timeout=30000)
        await page.wait_for_load_state("networkidle")
        
        await self.detect_and_handle_guides(page, "channels_publish")
        print("🔍 探索发布页面功能...")
        await self.analyze_publish_features(page, "channels")

        # 内容管理页面
        print("📍 导航到内容管理...")
        try:
            await page.goto("https://channels.weixin.qq.com/platform/post/list")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"⚠️ 导航失败: {e}")

        print("📊 正在提取数据表头...")
        headers = await self.extract_table_headers(page)
        if headers:
            self.results["headers"]["channels"] = headers
            print(f"✅ 发现表头: {headers}")

    async def explore_bilibili(self, page: Page):
        """B站深度探索流程"""
        print("📍 正在进入B站创作中心...")
        # 发布页面
        await page.goto("https://member.bilibili.com/platform/upload/video/frame", timeout=30000)
        await page.wait_for_load_state("networkidle")
        
        await self.detect_and_handle_guides(page, "bilibili_publish")
        print("🔍 探索发布页面功能...")
        await self.analyze_publish_features(page, "bilibili")

        # 内容管理页面
        print("📍 导航到内容管理...")
        try:
            await page.goto("https://member.bilibili.com/platform/upload-manager/article")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"⚠️ 导航失败: {e}")

        print("📊 正在提取数据表头...")
        headers = await self.extract_table_headers(page)
        if headers:
            self.results["headers"]["bilibili"] = headers
            print(f"✅ 发现表头: {headers}")

    async def extract_table_headers(self, page: Page) -> list:
        """通用表头提取逻辑"""
        # 尝试常见的表头选择器
        selectors = [
            "thead th", 
            ".table-header .cell", 
            ".ant-table-thead th", 
            ".el-table__header th",
            "tr:first-child th",
            "tr:first-child td" # 有些表格用td做表头
        ]
        
        found_headers = []
        
        for selector in selectors:
            try:
                elements = await page.locator(selector).all()
                if len(elements) > 3: # 如果找到超过3个元素，很可能是表头
                    texts = [await el.inner_text() for el in elements]
                    # 清理文本
                    texts = [t.strip().replace('\n', ' ') for t in texts if t.strip()]
                    if texts:
                        found_headers = texts
                        break
            except:
                continue
                
        return found_headers

    async def extract_douyin_videos(self, page: Page):
        """提取抖音作品列表的基础指标（播放/点赞/评论）。"""
        try:
            # 尝试滚动加载更多卡片
            for _ in range(3):
                await page.mouse.wheel(0, 1200)
                await page.wait_for_timeout(800)
        except Exception:
            pass

        cards = await page.locator(".video-card-zQ02ng, .video-card-new-pWwRVu").all()
        videos = []
        for idx, card in enumerate(cards[:50]):  # 最多抓取 50 条，防止过多
            try:
                title = await card.locator(".title-text, .video-card-title, .video-card-info-aglKIQ h3").first.inner_text()
            except Exception:
                title = f"作品{idx+1}"

            # 抖音页面指标 class: metric-container-Rc61p9 -> metric-item-container-NMaNDn -> metric-value-k4R5P_
            metric_values = await card.locator(".metric-container-Rc61p9 .metric-value-k4R5P_").all()
            def _metric(n):
                try:
                    return metric_values[n].inner_text()
                except Exception:
                    return ""
            play = await _metric(0)
            like = await _metric(1)
            comment = await _metric(2)

            videos.append({
                "title": title.strip(),
                "play": play.strip(),
                "like": like.strip(),
                "comment": comment.strip()
            })

        if videos:
            self.results.setdefault("videos", {})
            self.results["videos"]["douyin"] = videos
            print(f"🎯 抓取抖音作品 {len(videos)} 条")
        else:
            print("⚠️ 未找到抖音作品卡片，可能页面样式变更")

    async def detect_and_handle_guides(self, page: Page, context_name: str):
        """检测并处理引导弹窗，同时学习新关键词"""
        print(f"🛡️ 检测引导弹窗 ({context_name})...")
        
        # 获取页面上所有可见的按钮文本
        buttons = await page.locator("button, .btn, [role='button']").all()
        
        for btn in buttons:
            try:
                if not await btn.is_visible():
                    continue
                    
                text = await btn.inner_text()
                text = text.strip()
                
                # 检查是否是已知引导词
                is_known = False
                for keyword in self.guide_keywords:
                    if re.search(keyword, text, re.IGNORECASE):
                        is_known = True
                        break
                
                # 如果不是已知词，但看起来像引导按钮（简短、高亮等），记录下来
                if not is_known and 2 <= len(text) <= 10:
                    # 简单的启发式规则：通常引导按钮文字较短
                    print(f"💡 发现潜在新引导词: [{text}]")
                    self.results["new_guides"].append({
                        "text": text,
                        "context": context_name,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                # 如果是已知引导词，点击它
                if is_known:
                    print(f"👆 点击引导按钮: [{text}]")
                    await btn.click()
                    await page.wait_for_timeout(1000) # 等待动画
            except:
                pass

    async def analyze_publish_features(self, page: Page, platform: str):
        """分析发布页面的特有功能"""
        features = {
            "inputs": [],
            "buttons": [],
            "cover_requirements": [],
            "upload_paths": []
        }
        
        # 1. 检测输入框提示词
        inputs = await page.locator("input[placeholder], textarea[placeholder], .editor-content").all()
        for inp in inputs:
            try:
                ph = await inp.get_attribute("placeholder")
                if not ph:
                    ph = await inp.inner_text() # 有些富文本编辑器没有placeholder
                
                if ph:
                    features["inputs"].append(ph.strip())
                    if "@" in ph or "#" in ph or "话题" in ph:
                        print(f"✨ 发现富文本输入特性: {ph.strip()}")
            except:
                pass
                
        # 2. 检测封面要求
        # 寻找包含"封面"字样的区域，并提取附近的文本
        try:
            cover_area = page.locator("text=封面").first
            if await cover_area.count() > 0:
                # 获取父级容器的文本，通常包含要求
                parent_text = await cover_area.locator("..").inner_text()
                features["cover_requirements"].append(parent_text.strip())
                print(f"🖼️ 发现封面要求: {parent_text.strip()[:50]}...")
        except:
            pass

        # 3. 检测上传路径 (测试最快路径)
        # 寻找上传按钮
        upload_btns = await page.locator("text=上传视频").all()
        if upload_btns:
            features["upload_paths"].append("常规上传按钮")
            
        # 4. 检测特定功能按钮
        keywords = ["关联", "小程序", "商品", "合集", "定时发布", "贴纸"]
        page_text = await page.content()
        
        for kw in keywords:
            if kw in page_text:
                features["buttons"].append(kw)
                
        self.results["features"][platform] = features
        print(f"✨ 发现特性汇总: {json.dumps(features, ensure_ascii=False)}")

    def save_results(self, platform):
        """保存探索结果到文件"""
        output_file = BASE_DIR / "config" / f"platform_features_{platform}.json"
        
        # 读取旧数据以合并
        if output_file.exists():
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                    # 简单的合并逻辑，实际可能需要更复杂
                    old_data.update(self.results) 
                    self.results = old_data
            except:
                pass
                
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        print(f"💾 探索结果已保存: {output_file}")

# 全局实例
explorer = PlatformExplorer()
