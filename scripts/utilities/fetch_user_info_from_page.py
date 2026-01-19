"""
通过访问页面抓取用户信息(name, avatar)并更新cookie文件
"""
import asyncio
import json
import sys
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# 确保能找到仓库内的 myUtils（位于 syn_backend/myUtils）
ROOT = Path(__file__).resolve().parents[2]
sys.path.extend([str(ROOT / "syn_backend"), str(ROOT)])
from myUtils.cookie_manager import cookie_manager

# 平台配置
PLATFORM_CONFIGS = {
    'kuaishou': {
        'url': 'https://cp.kuaishou.com/profile',
        'selectors': {
            'name': ['.user-info-name', 'section.header-bar .user-info-name', 'div[class*="user-info-name"]'],
            'avatar': ['section.header-bar .user-info-avatar img', 'div[class*="user-info-avatar"] img', '.avatar-wrapper img'],
            'user_id_text': 'text=/快手号[:：]?\\s*\\w+/'
        }
    },
    'douyin': {
        'url': 'https://creator.douyin.com/creator-micro/home',
        'selectors': {
            'name': ['xpath=//div[@class="name-_lSSDc"]', 'div[class*="name-_lSSDc"]', 'div[class*="header-right-name"]', '.header-right-name'],
            'avatar': ['div[class*="avatar-"] img', '.semi-avatar img', '.header-right-avatar img'],
            'user_id_text': 'text=/抖音号[:：]?\\s*\\d+/'
        }
    },
    'channels': {
        'url': 'https://channels.weixin.qq.com/platform',
        'selectors': {
            'name': ['.finder-nickname', '.nickname', '.name'],
            'avatar': ['.finder-avatar img', '.avatar img', 'img[src*="head"]'],
            'user_id': ['xpath=//span[@id="finder-uid-copy"]', '.finder-uniq-id-wrap span', '#finder-uid-copy']
        }
    },
    'xiaohongshu': {
        'url': 'https://creator.xiaohongshu.com/creator/home',
        'selectors': {
            'name': ['.base .text .account-name', '.account-name', '.user-name'],
            'avatar': ['.base .avatar img', '.avatar img', 'img[alt*="头像"]'],
            'user_id_text': 'text=/小红书账号[:：]?\s*[\w_]+/'
        }
    },
    'bilibili': {
        'url': 'https://member.bilibili.com/platform/home',
        'selectors': {
            'name': ['xpath=//div[@class="username"]', '.header-entry-avatar .username', '.username', '.user-name', 'div[class*="username"]'],
            'avatar': ['xpath=//img[@class="face-img"]', '.header-entry-avatar .face-img', '.avatar-img', '.header-avatar-wrap img', 'img[class*="face"]'],
        }
    }
}


async def fetch_user_info(platform: str, cookie_file: Path):
    """访问页面抓取用户信息"""
    config = PLATFORM_CONFIGS.get(platform)
    if not config:
        print(f"  不支持的平台: {platform}")
        return None

    try:
        # 读取cookie文件
        with open(cookie_file, 'r', encoding='utf-8') as f:
            cookie_data = json.load(f)

        # 转换为Playwright storage_state格式
        if 'cookies' in cookie_data:
            storage_state = cookie_data
        elif 'cookie_info' in cookie_data and 'cookies' in cookie_data['cookie_info']:
            # Bilibili格式: cookie_info.cookies - 需要添加domain
            cookies = cookie_data['cookie_info']['cookies']
            # 为每个cookie添加domain字段
            for cookie in cookies:
                if 'domain' not in cookie:
                    cookie['domain'] = '.bilibili.com'
                if 'path' not in cookie:
                    cookie['path'] = '/'
            storage_state = {'cookies': cookies}
        else:
            print(f"  Cookie格式错误")
            return None

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(storage_state=storage_state)
            page = await context.new_page()

            try:
                print(f"  访问: {config['url']}")
                await page.goto(config['url'], wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(5000)  # 等待页面加载

                # 检查是否跳转到登录页
                current_url = page.url
                if 'login' in current_url.lower() or 'passport' in current_url.lower():
                    print(f"  Cookie已过期,跳转到登录页")
                    return None

                result = {'name': None, 'avatar': None, 'user_id': None}

                # 抓取name
                for selector in config['selectors'].get('name', []):
                    try:
                        elem = await page.wait_for_selector(selector, timeout=3000)
                        if elem:
                            text = await elem.inner_text()
                            if text:
                                result['name'] = text.strip().split('\n')[0]
                                print(f"  Name: {result['name']}")
                                break
                    except:
                        continue

                # 抓取avatar
                for selector in config['selectors'].get('avatar', []):
                    try:
                        elem = await page.wait_for_selector(selector, timeout=3000)
                        if elem:
                            avatar_url = await elem.get_attribute('src')
                            if avatar_url:
                                result['avatar'] = avatar_url
                                print(f"  Avatar: {avatar_url[:60]}...")
                                break
                    except:
                        continue

                # 抓取user_id (如果有文本选择器)
                if 'user_id_text' in config['selectors']:
                    try:
                        elem = await page.wait_for_selector(config['selectors']['user_id_text'], timeout=2000)
                        if elem:
                            text = await elem.inner_text()
                            import re
                            if platform == 'kuaishou':
                                match = re.search(r'快手号[:：]?\s*(\w+)', text)
                            elif platform == 'douyin':
                                match = re.search(r'抖音号[:：]?\s*(\d+)', text)
                            elif platform == 'xiaohongshu':
                                match = re.search(r'账号[:：]?\s*([\w_]+)', text)
                            else:
                                match = None

                            if match:
                                result['user_id'] = match.group(1)
                                print(f"  UserID: {result['user_id']}")
                    except:
                        pass

                # 抓取user_id (如果有直接选择器)
                if 'user_id' in config['selectors'] and not result.get('user_id'):
                    for selector in config['selectors'].get('user_id', []):
                        try:
                            elem = await page.wait_for_selector(selector, timeout=2000)
                            if elem:
                                user_id_text = await elem.inner_text()
                                if user_id_text:
                                    result['user_id'] = user_id_text.strip()
                                    print(f"  UserID: {result['user_id']}")
                                    break
                        except:
                            continue

                return result

            finally:
                await browser.close()

    except Exception as e:
        print(f"  错误: {e}")
        return None


async def main():
    """主函数"""
    print("="*70)
    print("从页面抓取用户信息")
    print("="*70)

    # 获取所有账号
    accounts = cookie_manager.list_flat_accounts()

    stats = {'total': len(accounts), 'updated': 0, 'failed': 0}

    for i, account in enumerate(accounts, 1):
        account_id = account['account_id']
        platform = account['platform']
        cookie_file = account.get('cookie_file')

        print(f"\n[{i}/{stats['total']}] {platform:12s} | {account_id}")

        if not cookie_file:
            print("  跳过: 无Cookie文件")
            stats['failed'] += 1
            continue

        # 查找cookie文件（优先使用 cookie_manager 配置的目录）
        cookie_path = cookie_manager.cookies_dir / cookie_file
        if not cookie_path.exists():
            cookie_path = Path(__file__).parent.parent / 'config' / 'cookiesFile' / cookie_file

        if not cookie_path.exists():
            print(f"  跳过: 文件不存在")
            stats['failed'] += 1
            continue

        # 抓取信息
        info = await fetch_user_info(platform, cookie_path)

        if info and (info['name'] or info['avatar']):
            # 读取cookie文件
            with open(cookie_path, 'r', encoding='utf-8') as f:
                cookie_data = json.load(f)

            # 更新或创建user_info
            if 'user_info' not in cookie_data:
                cookie_data['user_info'] = {}

            if info['name']:
                cookie_data['user_info']['name'] = info['name']
            if info['avatar']:
                cookie_data['user_info']['avatar'] = info['avatar']
            if info['user_id']:
                cookie_data['user_info']['user_id'] = info['user_id']

            # 如果user_id还没有,从cookie中提取
            if not cookie_data['user_info'].get('user_id'):
                # 对于Bilibili格式,需要传入正确的结构
                if 'cookie_info' in cookie_data:
                    user_id = cookie_manager._extract_user_id_from_cookie(platform, cookie_data['cookie_info'])
                else:
                    user_id = cookie_manager._extract_user_id_from_cookie(platform, cookie_data)
                if user_id:
                    cookie_data['user_info']['user_id'] = user_id

            # 保存回文件
            with open(cookie_path, 'w', encoding='utf-8') as f:
                json.dump(cookie_data, f, ensure_ascii=False, indent=2)

            # 更新数据库
            updates = {}
            if info['name']:
                updates['name'] = info['name']
            if info['avatar']:
                updates['avatar'] = info['avatar']
            if cookie_data['user_info'].get('user_id'):
                updates['user_id'] = cookie_data['user_info']['user_id']

            if updates:
                cookie_manager.update_account(account_id, **updates)
                print("  -> 已更新cookie文件和数据库")
                stats['updated'] += 1
        else:
            print("  -> 未能抓取到信息")
            stats['failed'] += 1

        # 延迟避免请求过快
        await asyncio.sleep(2)

    print("\n" + "="*70)
    print("抓取完成")
    print("="*70)
    print(f"总数:   {stats['total']}")
    print(f"已更新: {stats['updated']}")
    print(f"失败:   {stats['failed']}")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
