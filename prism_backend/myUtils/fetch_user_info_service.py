"""
用户信息抓取服务
通过访问页面抓取用户信息(name, avatar, user_id)并更新cookie文件和数据库
"""
import asyncio
import json
import os
import sys
import re
from pathlib import Path
from typing import Any
from loguru import logger

from myUtils.cookie_manager import cookie_manager
from config.conf import PLAYWRIGHT_HEADLESS

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
            'user_id_text': 'text=/抖音号[:：]?\\s*[\\w.-]+/'
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
        'url': 'https://creator.xiaohongshu.com/new/home',
        'selectors': {
            'name': ['.base .text .account-name', '.account-name', '.user-name'],
            'avatar': ['.base .avatar img', '.avatar img', 'img[alt*="头像"]'],
            'user_id_text': r'text=/小红书账号[:：]?\s*[\w_]+/'
        }
    },
    'bilibili': {
        'url': 'https://account.bilibili.com/account/home',
        'selectors': {
            'name': ['xpath=//div[@class="home-top-msg"]/span[@class="home-top-msg-name ext-highlight"]', '.home-top-msg-name'],
            'avatar': ['.home-head img', 'div.home-head img'],
            # B站的user_id从cookie的DedeUserID提取，不从页面抓取
        }
    }
}


async def fetch_user_info(platform: str, cookie_file: Path):
    """访问页面抓取用户信息（通过 Worker 进行 DOM+cookie 补全，避免在 API 进程内跑 Playwright）"""
    # 过去为了避免 uvicorn reload 与 Playwright 冲突，默认关闭过“进程内 Playwright 抓取”。
    # 现在已改为走独立 Playwright Worker，因此默认开启；仅当显式设置为 false/0/no 时才禁用。
    raw_flag = os.environ.get("ENABLE_PLAYWRIGHT_USERINFO_SYNC")
    if raw_flag is not None and raw_flag.strip().lower() in {"0", "false", "no", "off"}:
        return None

    config = PLATFORM_CONFIGS.get(platform)
    if not config:
        logger.warning(f"不支持的平台: {platform}")
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
            logger.error(f"Cookie格式错误")
            return None

        import httpx

        platform_code = (platform or "").strip().lower()
        if platform_code == "channels":
            platform_code = "tencent"

        worker_base_url = os.environ.get("PLAYWRIGHT_WORKER_URL", "http://127.0.0.1:7001").rstrip("/")

        logger.info(
            f"[UserInfoFetch] Worker enrich: platform={platform_code} headless={bool(PLAYWRIGHT_HEADLESS)} url={worker_base_url}"
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{worker_base_url}/account/enrich",
                json={"platform": platform_code, "storage_state": storage_state, "headless": bool(PLAYWRIGHT_HEADLESS)},
            )
            resp.raise_for_status()
            payload = resp.json()
            if not payload.get("success"):
                return None
            data = payload.get("data") or {}
            return {"name": data.get("name"), "avatar": data.get("avatar"), "user_id": data.get("user_id")}

    except Exception as e:
        logger.error(f"错误: {e}")
        return None


def _extract_from_cookie_file(platform: str, cookie_path: Path) -> dict | None:
    try:
        with open(cookie_path, "r", encoding="utf-8") as f:
            cookie_data = json.load(f)
    except Exception:
        return None

    # 1) 优先使用文件内已有 user_info（如果存在）
    user_info = cookie_data.get("user_info") or cookie_data.get("cookie_info", {}).get("user_info") or {}
    extracted = {"name": user_info.get("name"), "avatar": user_info.get("avatar"), "user_id": user_info.get("user_id")}

    # 2) 尝试从 cookie 结构提取（尽力而为）
    try:
        best_effort = cookie_manager._extract_user_info_from_cookie(platform, cookie_data)
    except Exception:
        best_effort = {}

    for k in ("name", "avatar", "user_id"):
        if not extracted.get(k) and best_effort.get(k):
            extracted[k] = best_effort.get(k)

    if extracted.get("name") or extracted.get("avatar") or extracted.get("user_id"):
        return extracted
    return None


async def fetch_all_user_info():
    """抓取所有账号的用户信息 - 用于API调用"""
    logger.info("="*70)
    logger.info("开始同步账号信息")
    logger.info("="*70)

    # 获取所有账号
    accounts = cookie_manager.list_flat_accounts()

    stats = {'total': len(accounts), 'updated': 0, 'failed': 0, 'skipped': 0}

    for i, account in enumerate(accounts, 1):
        account_id = account['account_id']
        platform = account['platform']
        cookie_file = account.get('cookie_file')

        logger.info(f"[{i}/{stats['total']}] {platform:12s} | {account_id}")

        if not cookie_file:
            logger.warning("跳过: 无Cookie文件")
            stats['skipped'] += 1
            continue

        # 查找cookie文件（优先使用 cookie_manager 配置的目录）
        cookie_path = cookie_manager._resolve_cookie_path(cookie_file)
        if not cookie_path.exists():
            logger.warning(f"跳过: 文件不存在 - {cookie_file}")
            stats['skipped'] += 1
            continue

        # 1) 先从 cookie 文件尽力提取（很多平台 cookie 里不含昵称/头像）
        info = _extract_from_cookie_file(platform, cookie_path) or {}

        # 2) 如任一关键字段缺失，或 name 为占位值（如与 user_id 相同），则使用 Worker（Playwright）做 DOM+cookie 补全
        #    注意：抓取失败 ≠ cookie 过期，不能因为没拿到 name/avatar 就把账号判定为 expired。
        def _is_blank(value: Any) -> bool:
            if value is None:
                return True
            if isinstance(value, str) and not value.strip():
                return True
            return False

        def _should_replace_name(current_name: Any, user_id: Any) -> bool:
            if _is_blank(current_name):
                return True
            text = str(current_name).strip()
            if text in {"-", "null"}:
                return True
            if user_id is not None and text == str(user_id).strip():
                return True
            if text.startswith("未命名账号"):
                return True
            return False

        try:
            needs_enrich = _is_blank(info.get("user_id")) or _is_blank(info.get("avatar")) or _should_replace_name(info.get("name"), info.get("user_id"))
            if needs_enrich:
                enriched = await fetch_user_info(platform, cookie_path)
                if enriched:
                    if enriched.get("user_id") and _is_blank(info.get("user_id")):
                        info["user_id"] = enriched.get("user_id")

                    # 用 enrichment 的 user_id 参与 name 判定，避免“name==旧 user_id”导致无法替换
                    effective_user_id = info.get("user_id") or enriched.get("user_id")
                    if enriched.get("name") and _should_replace_name(info.get("name"), effective_user_id):
                        info["name"] = enriched.get("name")

                    if enriched.get("avatar") and _is_blank(info.get("avatar")):
                        info["avatar"] = enriched.get("avatar")
        except Exception as e:
            logger.warning(f"Worker enrich failed (ignored): {e}")

        # B站特殊处理：如果页面抓取失败，从cookie中提取
        if platform == 'bilibili' and (not info or (not info.get('name') and not info.get('avatar'))):
            logger.info("B站页面抓取失败，尝试从cookie文件提取信息")
            try:
                with open(cookie_path, 'r', encoding='utf-8') as f:
                    cookie_data = json.load(f)

                # 从cookie文件的user_info字段提取（如果已存在）
                user_info = cookie_data.get('user_info', {}) or cookie_data.get('cookie_info', {}).get('user_info', {})
                if user_info:
                    info = {
                        'name': user_info.get('name'),
                        'avatar': user_info.get('avatar'),
                        'user_id': user_info.get('user_id') or cookie_manager._extract_user_id_from_cookie(platform, cookie_data.get('cookie_info', cookie_data))
                    }
                    logger.info(f"从cookie文件提取: name={info['name']}, user_id={info['user_id']}")
            except Exception as e:
                logger.warning(f"从cookie提取失败: {e}")

        if info and (info.get('name') or info.get('avatar') or info.get('user_id')):
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

            # 注意：同步用户信息 ≠ 验证账号有效性
            # 不应在此处修改 status，账号状态应该：
            # 1. 登录成功时设为 valid（由 add_account 处理）
            # 2. 发布失败时设为 expired（由发布流程处理）
            # 3. 手动验证时更新（由验证接口处理）

            if updates:
                cookie_manager.update_account(account_id, **updates)
                logger.info("✅ 已更新cookie文件和数据库")
                stats['updated'] += 1
        else:
            # 抓取失败不等于 cookie 过期：不要误标 expired，保留原状态。
            logger.warning("未能抓取到任何用户信息字段（不标记 expired，保留原状态）")
            stats['failed'] += 1

        # 延迟避免请求过快
        await asyncio.sleep(2)

    logger.info("="*70)
    logger.info("同步完成")
    logger.info(f"总数: {stats['total']}, 已更新: {stats['updated']}, 失败: {stats['failed']}, 跳过: {stats['skipped']}")
    logger.info("="*70)

    return stats


def fetch_all_user_info_sync():
    """
    同步版本的fetch_all_user_info
    用于定时任务调度器
    """
    return asyncio.run(fetch_all_user_info())


# 兼容原有的main函数（用于直接运行）
async def main():
    """主函数 - 用于命令行直接运行"""
    return await fetch_all_user_info()


if __name__ == "__main__":
    asyncio.run(main())
