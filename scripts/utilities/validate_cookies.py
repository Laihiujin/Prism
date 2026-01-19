"""
统一 Cookie 验证脚本
基于各平台的 Cookie 访问平台页面，获取真实的 user_id、name、avatar
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Optional
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

sys.path.insert(0, str(Path(__file__).parent))

from myUtils.cookie_manager import cookie_manager

try:
    from loguru import logger
except Exception:
    class _SimpleLogger:
        def info(self, msg): print(f"[INFO] {msg}")
        def warning(self, msg): print(f"[WARN] {msg}")
        def error(self, msg): print(f"[ERROR] {msg}")
        def success(self, msg): print(f"[OK] {msg}")
    logger = _SimpleLogger()


# 平台验证配置
PLATFORM_CONFIGS = {
    'kuaishou': {
        'url': 'https://cp.kuaishou.com/article/publish/video',
        'js_extract': """() => {
            if (window.__INITIAL_STATE__?.user) return window.__INITIAL_STATE__.user;
            if (window.__INITIAL_STATE__?.userInfo) return window.__INITIAL_STATE__.userInfo;
            if (window.userInfo) return window.userInfo;
            return null;
        }""",
        'user_id_keys': ['userId', 'id'],
        'name_keys': ['name', 'userName', 'nickname'],
        'avatar_keys': ['avatar', 'headUrl', 'headurl']
    },
    'douyin': {
        'url': 'https://creator.douyin.com/creator-micro/content/upload',
        'js_extract': """() => {
            if (window._ROUTER_DATA?.loaderData) {
                for (const key in window._ROUTER_DATA.loaderData) {
                    const data = window._ROUTER_DATA.loaderData[key];
                    if (data?.user) return data.user;
                }
            }
            if (window.userData) return window.userData;
            return null;
        }""",
        'user_id_keys': ['userId', 'uid', 'user_id'],
        'name_keys': ['name', 'nickname', 'userName'],
        'avatar_keys': ['avatar', 'avatarUrl', 'avatarThumb']
    },
    'xiaohongshu': {
        'url': 'https://creator.xiaohongshu.com/creator-micro/content/upload',
        'js_extract': """() => {
            // 尝试从全局变量中获取用户信息
            if (window.__INITIAL_SSR_STATE__?.Main?.user) return window.__INITIAL_SSR_STATE__.Main.user;
            if (window.userInfo) return window.userInfo;
            if (window.__INITIAL_STATE__?.user) return window.__INITIAL_STATE__.user;

            // 尝试从页面 script 标签中解析
            const scripts = document.querySelectorAll('script');
            for (const script of scripts) {
                const content = script.textContent;
                if (content && content.includes('userName')) {
                    try {
                        // 查找包含用户信息的 JSON
                        const match = content.match(/\{"userName":"[^"]+","userAvatar":"[^"]+","redId":"[^"]+"/);
                        if (match) {
                            // 扩展匹配到完整的 JSON 对象
                            const start = content.indexOf(match[0]);
                            let end = start;
                            let braceCount = 0;
                            for (let i = start; i < content.length; i++) {
                                if (content[i] === '{') braceCount++;
                                if (content[i] === '}') braceCount--;
                                if (braceCount === 0) {
                                    end = i + 1;
                                    break;
                                }
                            }
                            const jsonStr = content.substring(start, end);
                            return JSON.parse(jsonStr);
                        }
                    } catch (e) {
                        console.log('Parse error:', e);
                    }
                }
            }
            return null;
        }""",
        'user_id_keys': ['redId', 'userId', 'id', 'user_id'],  # redId 是小红书号
        'name_keys': ['userName', 'name', 'nickname'],
        'avatar_keys': ['userAvatar', 'avatar', 'imageb']
    },
    'channels': {
        'url': 'https://channels.weixin.qq.com/platform',
        'js_extract': """() => {
            if (window.__INITIAL_STATE__?.userInfo) return window.__INITIAL_STATE__.userInfo;
            if (window.userInfo) return window.userInfo;
            if (window.__NEXT_DATA__?.props?.pageProps?.user) return window.__NEXT_DATA__.props.pageProps.user;
            return null;
        }""",
        'user_id_keys': ['finderUsername', 'finderId', 'uin', 'wxuin'],
        'name_keys': ['name', 'nickname', 'nickName'],
        'avatar_keys': ['headImgUrl', 'avatar']
    },
    'bilibili': {
        'url': 'https://member.bilibili.com/platform/home',
        'js_extract': """() => {
            if (window.__BILI_USER_INFO__) return window.__BILI_USER_INFO__;
            if (window.__INITIAL_STATE__?.data?.info) return window.__INITIAL_STATE__.data.info;
            if (window.__INITIAL_STATE__?.user) return window.__INITIAL_STATE__.user;
            return null;
        }""",
        'user_id_keys': ['mid', 'uid', 'user_id'],
        'name_keys': ['uname', 'name', 'username'],
        'avatar_keys': ['face', 'avatar']
    }
}


async def validate_and_extract_info(
    platform: str,
    cookie_file: Path
) -> Optional[Dict]:
    """
    使用 Cookie 访问平台页面，提取真实的用户信息

    Returns:
        {'status': 'valid'|'expired', 'user_id': '...', 'name': '...', 'avatar': '...'}
    """
    try:
        config = PLATFORM_CONFIGS.get(platform.lower())
        if not config:
            logger.error(f"不支持的平台: {platform}")
            return None

        logger.info(f"正在验证 {platform} Cookie: {cookie_file.name}")

        # 读取 Cookie 文件
        with open(cookie_file, 'r', encoding='utf-8') as f:
            cookie_data = json.load(f)

        # 首先尝试从 user_info 字段读取（新登录保存的）
        if 'user_info' in cookie_data:
            user_info = cookie_data['user_info']
            if user_info.get('user_id'):
                logger.success(f"从 user_info 字段获取到用户信息")
                return {
                    'status': 'valid',
                    'user_id': user_info.get('user_id'),
                    'name': user_info.get('name'),
                    'avatar': user_info.get('avatar')
                }

        # 尝试从 localStorage 中的 USER_INFO_FOR_BIZ 读取（小红书）
        if platform.lower() == 'xiaohongshu' and 'origins' in cookie_data:
            for origin in cookie_data.get('origins', []):
                for item in origin.get('localStorage', []):
                    if item.get('name') == 'USER_INFO_FOR_BIZ':
                        try:
                            user_info_str = item.get('value', '')
                            user_info_data = json.loads(user_info_str)
                            logger.success(f"从 localStorage USER_INFO_FOR_BIZ 获取到用户信息")
                            return {
                                'status': 'valid',
                                'user_id': user_info_data.get('redId'),
                                'name': user_info_data.get('userName'),
                                'avatar': user_info_data.get('userAvatar')
                            }
                        except Exception as e:
                            logger.warning(f"解析 USER_INFO_FOR_BIZ 失败: {e}")

        # 转换为 Playwright storage_state 格式
        if 'cookies' in cookie_data:
            cookies = cookie_data['cookies']

            # 如果是字典格式，转换为数组
            if isinstance(cookies, dict):
                cookie_list = []
                domain_map = {
                    'kuaishou': '.kuaishou.com',
                    'douyin': '.douyin.com',
                    'xiaohongshu': '.xiaohongshu.com',
                    'channels': '.qq.com',
                    'bilibili': '.bilibili.com'
                }
                for name, value in cookies.items():
                    cookie_list.append({
                        'name': name,
                        'value': str(value),
                        'domain': domain_map.get(platform, '.example.com'),
                        'path': '/'
                    })
                storage_state = {'cookies': cookie_list, 'origins': []}
            else:
                # 已经是数组格式
                storage_state = cookie_data
        else:
            logger.error("Cookie 文件格式错误")
            return None

        # 启动浏览器并访问页面
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            try:
                context = await browser.new_context(storage_state=storage_state)
                page = await context.new_page()

                logger.info(f"访问页面: {config['url']}")
                await page.goto(config['url'], wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(3000)  # 等待页面加载

                # 检查是否跳转到登录页
                current_url = page.url
                if 'login' in current_url.lower() or 'passport' in current_url.lower():
                    logger.warning(f"Cookie 已过期，跳转到登录页: {current_url}")
                    return {'status': 'expired', 'user_id': None, 'name': None, 'avatar': None}

                # 从页面 JS 变量中提取用户信息
                user_data = None
                try:
                    user_data = await page.evaluate(config['js_extract'])
                    if user_data:
                        logger.success(f"成功从页面提取到用户数据")
                        logger.info(f"提取的数据: {user_data}")  # 添加调试信息
                    else:
                        logger.warning(f"JS 提取返回 None")
                except Exception as e:
                    logger.warning(f"无法从 JS 提取用户数据: {e}")

                # 解析用户信息
                result = {'status': 'valid', 'user_id': None, 'name': None, 'avatar': None}

                if user_data and isinstance(user_data, dict):
                    # 提取 user_id
                    for key in config['user_id_keys']:
                        if user_data.get(key):
                            result['user_id'] = str(user_data[key])
                            break

                    # 提取 name
                    for key in config['name_keys']:
                        if user_data.get(key):
                            result['name'] = str(user_data[key])
                            break

                    # 提取 avatar
                    for key in config['avatar_keys']:
                        if user_data.get(key):
                            result['avatar'] = str(user_data[key])
                            break

                    if result['user_id']:
                        logger.success(f"✅ 提取成功: {result['name']} (ID: {result['user_id']})")
                        if result['avatar']:
                            logger.info(f"   Avatar: {result['avatar'][:80]}...")
                    else:
                        logger.warning(f"⚠️  未能提取到 user_id")
                        result['status'] = 'expired'
                else:
                    logger.warning(f"⚠️  页面中未找到用户数据")
                    result['status'] = 'expired'

                return result

            finally:
                await browser.close()

    except PlaywrightTimeout as e:
        logger.error(f"❌ 页面访问超时: {e}")
        return {'status': 'error', 'user_id': None, 'name': None, 'avatar': None}
    except Exception as e:
        logger.error(f"❌ 验证失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


async def batch_validate_all_accounts():
    """批量验证所有账号"""
    accounts = cookie_manager.list_flat_accounts()

    stats = {
        'total': len(accounts),
        'valid': 0,
        'expired': 0,
        'error': 0,
        'no_file': 0
    }

    logger.info(f"\n{'='*60}")
    logger.info(f"开始批量验证 {stats['total']} 个账号")
    logger.info(f"{'='*60}\n")

    for i, account in enumerate(accounts, 1):
        account_id = account['account_id']
        platform = account['platform']
        cookie_file = account.get('cookie_file')

        logger.info(f"\n[{i}/{stats['total']}] 处理账号: {account_id} ({platform})")
        logger.info("-" * 60)

        if not cookie_file:
            logger.warning("跳过：无 Cookie 文件")
            stats['no_file'] += 1
            continue

        cookie_path = Path(__file__).parent / 'cookiesFile' / cookie_file
        if not cookie_path.exists():
            logger.warning(f"跳过：文件不存在 - {cookie_file}")
            stats['no_file'] += 1
            continue

        # 验证并提取信息
        result = await validate_and_extract_info(platform, cookie_path)

        if result:
            if result['status'] == 'valid' and result['user_id']:
                stats['valid'] += 1

                # 更新数据库
                updates = {
                    'user_id': result['user_id'],
                    'status': 'valid'
                }
                if result['name']:
                    updates['name'] = result['name']
                if result['avatar']:
                    updates['avatar'] = result['avatar']

                success = cookie_manager.update_account(account_id, **updates)
                if success:
                    logger.success(f"✅ 数据库更新成功")
                else:
                    logger.error(f"❌ 数据库更新失败")

            elif result['status'] == 'expired':
                stats['expired'] += 1
                # 标记为过期
                cookie_manager.update_account(account_id, status='expired')
                logger.warning(f"⚠️  已标记为过期")
            else:
                stats['error'] += 1
        else:
            stats['error'] += 1

        # 延迟避免请求过快
        await asyncio.sleep(2)

    # 打印统计
    logger.info(f"\n{'='*60}")
    logger.info(f"验证完成！")
    logger.info(f"{'='*60}")
    logger.info(f"总数:   {stats['total']}")
    logger.info(f"✅ 有效: {stats['valid']}")
    logger.info(f"❌ 过期: {stats['expired']}")
    logger.info(f"⚠️  错误: {stats['error']}")
    logger.info(f"⏭️  跳过: {stats['no_file']}")
    logger.info(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(batch_validate_all_accounts())
