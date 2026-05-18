"""
对比测试：浏览器实际API响应 vs 现有Cookie验证结果
用于验证fast_cookie_validator的准确性
"""
import asyncio
import httpx
import json
from pathlib import Path
import sys

# 设置UTF-8输出
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent / "syn_backend"))

from myUtils.fast_cookie_validator import FAST_CHECK_URLS, PLATFORM_NAMES
from myUtils.cookie_manager import cookie_manager


async def test_api_with_browser_cookie(platform_code: int, cookie_file: str):
    """
    使用现有Cookie测试API响应，并详细显示响应内容
    """
    platform_name = PLATFORM_NAMES.get(platform_code, 'unknown')
    api_url = FAST_CHECK_URLS.get(platform_code)

    print(f"\n{'='*80}")
    print(f"测试平台: {platform_name} (code: {platform_code})")
    print(f"Cookie文件: {cookie_file}")
    print(f"API端点: {api_url}")
    print(f"{'='*80}")

    # 读取Cookie文件
    cookie_dir = Path(__file__).parent / "syn_backend" / "cookiesFile"
    cookie_path = cookie_dir / cookie_file

    if not cookie_path.exists():
        print(f"❌ Cookie文件不存在: {cookie_path}")
        return

    try:
        with open(cookie_path, 'r', encoding='utf-8') as f:
            storage_state = json.load(f)

        # 提取cookies
        cookies = {}
        for cookie in storage_state.get('cookies', []):
            cookies[cookie['name']] = cookie['value']

        print(f"\n📝 Cookie数量: {len(cookies)}")
        print(f"主要Cookie: {', '.join(list(cookies.keys())[:5])}...")

    except Exception as e:
        print(f"❌ 读取Cookie失败: {e}")
        return

    # 发送请求
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": api_url
    }

    print(f"\n🔄 发送API请求...")

    try:
        async with httpx.AsyncClient(
            headers=headers,
            cookies=cookies,
            timeout=10.0,
            follow_redirects=False  # 不跟随重定向
        ) as client:
            resp = await client.get(api_url)

            print(f"\n📊 响应信息:")
            print(f"  状态码: {resp.status_code}")
            print(f"  Content-Type: {resp.headers.get('content-type', 'N/A')}")
            print(f"  响应大小: {len(resp.content)} bytes")

            # 显示响应内容
            content_type = resp.headers.get('content-type', '')

            if 'application/json' in content_type:
                print(f"\n✅ JSON响应:")
                try:
                    data = resp.json()
                    print(json.dumps(data, ensure_ascii=False, indent=2)[:1000])

                    # 分析响应内容
                    print(f"\n🔍 响应分析:")
                    if platform_code == 5:  # B站
                        print(f"  code: {data.get('code')}")
                        print(f"  isLogin: {data.get('data', {}).get('isLogin')}")
                        if data.get('data', {}).get('mid'):
                            print(f"  用户ID: {data['data']['mid']}")
                            print(f"  用户名: {data['data'].get('uname')}")

                    elif platform_code == 4:  # 快手
                        print(f"  result: {data.get('result')}")
                        if data.get('userInfo'):
                            print(f"  用户信息: {data['userInfo']}")

                    elif platform_code == 1:  # 小红书
                        print(f"  code: {data.get('code')}")
                        if data.get('data'):
                            print(f"  用户ID: {data['data'].get('user_id')}")
                            print(f"  昵称: {data['data'].get('nickname')}")

                    elif platform_code == 3:  # 抖音
                        print(f"  status_code: {data.get('status_code')}")
                        if data.get('user'):
                            print(f"  用户ID: {data['user'].get('uid')}")
                            print(f"  昵称: {data['user'].get('nickname')}")

                    elif platform_code == 2:  # 视频号
                        print(f"  errCode: {data.get('errCode')}")
                        if data.get('data'):
                            print(f"  数据: {data.get('data')}")

                except json.JSONDecodeError as e:
                    print(f"  ⚠️ JSON解析失败: {e}")
                    print(f"  原始响应: {resp.text[:500]}")

            elif 'text/html' in content_type:
                print(f"\n⚠️ HTML响应（可能已跳转到登录页）:")
                preview = resp.text[:300]
                print(f"  {preview}...")

            else:
                print(f"\n❓ 其他类型响应:")
                print(f"  {resp.text[:300]}")

            # 判断结果
            print(f"\n🎯 验证结论:")
            if resp.status_code in [301, 302, 401, 403]:
                print(f"  ❌ Cookie失效（状态码重定向/未授权）")
            elif 'text/html' in content_type:
                print(f"  ❌ Cookie失效（返回HTML登录页）")
            elif 'application/json' in content_type:
                try:
                    data = resp.json()
                    # 平台特定判断
                    if platform_code == 5 and data.get('code') == 0 and data.get('data', {}).get('isLogin'):
                        print(f"  ✅ Cookie有效（B站）")
                    elif platform_code == 4 and data.get('result') == 1:
                        print(f"  ✅ Cookie有效（快手）")
                    elif platform_code == 1 and data.get('code') == 0:
                        print(f"  ✅ Cookie有效（小红书）")
                    elif platform_code == 3 and data.get('status_code') == 0:
                        print(f"  ✅ Cookie有效（抖音）")
                    elif platform_code == 2 and data.get('errCode') == 0:
                        print(f"  ✅ Cookie有效（视频号）")
                    else:
                        print(f"  ❌ Cookie失效（API返回失败状态）")
                except:
                    print(f"  ❓ 无法判断")
            else:
                print(f"  ❓ 无法判断")

    except httpx.TimeoutException:
        print(f"\n❌ 请求超时")
    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主测试流程"""
    print("="*80)
    print("浏览器Cookie API测试 - 对比验证")
    print("="*80)

    # 获取所有账号
    accounts = cookie_manager.list_flat_accounts()

    if not accounts:
        print("\n❌ 没有找到账号")
        return

    print(f"\n找到 {len(accounts)} 个账号\n")

    # 按平台分组
    by_platform = {}
    for acc in accounts:
        platform = acc['platform']
        if platform not in by_platform:
            by_platform[platform] = []
        by_platform[platform].append(acc)

    # 测试每个平台的第一个账号
    for platform, platform_accounts in by_platform.items():
        test_account = platform_accounts[0]
        await test_api_with_browser_cookie(
            test_account['platform_code'],
            test_account['cookie_file']
        )

        # 询问是否继续
        if len(by_platform) > 1 and platform != list(by_platform.keys())[-1]:
            print("\n" + "-"*80)
            await asyncio.sleep(1)  # 短暂暂停


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
