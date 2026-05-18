"""
测试新的cookie二次抓取验证逻辑
"""
import asyncio
import sys
import io
from pathlib import Path

# 设置UTF-8编码输出（Windows兼容）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加syn_backend到路径
sys.path.insert(0, str(Path(__file__).parent / "syn_backend"))

from myUtils.auth import check_cookie
from myUtils.cookie_manager import cookie_manager

async def test_cookie_validation():
    """测试cookie验证"""

    print("=" * 60)
    print("测试Cookie二次抓取验证逻辑")
    print("=" * 60)

    # 从数据库读取实际账号
    all_accounts = cookie_manager.list_flat_accounts()

    if not all_accounts:
        print("\n⚠️  数据库中没有账号，请先在前端添加账号")
        return

    print(f"\n找到 {len(all_accounts)} 个账号")

    # 按平台分组
    platform_map = {
        1: "xiaohongshu",
        2: "channels",
        3: "douyin",
        4: "kuaishou",
        5: "bilibili"
    }

    platform_name_map = {
        "xiaohongshu": "小红书",
        "channels": "视频号",
        "douyin": "抖音",
        "kuaishou": "快手",
        "bilibili": "B站"
    }

    results = []

    for account in all_accounts:
        platform_code = account['platform_code']
        platform_name = platform_name_map.get(account['platform'], account['platform'])
        cookie_file = account['cookie_file']
        account_name = account['name']

        print(f"\n{'='*60}")
        print(f"正在测试: {platform_name} - {account_name}")
        print(f"Cookie文件: {cookie_file}")
        print(f"{'='*60}")

        try:
            result = await check_cookie(platform_code, cookie_file)

            status_emoji = "✅" if result.get("status") == "valid" else "❌"
            print(f"\n{status_emoji} 验证结果: {result.get('status')}")

            if result.get("status") == "valid":
                print(f"   User ID: {result.get('user_id', 'N/A')}")
                print(f"   Name: {result.get('name', 'N/A')}")
                print(f"   Avatar: {result.get('avatar', 'N/A')[:80] if result.get('avatar') else 'N/A'}")

            results.append({
                "platform": platform_name,
                "account": account_name,
                "status": result.get("status"),
                "user_id": result.get("user_id")
            })

        except FileNotFoundError:
            print(f"⚠️  Cookie文件不存在: {cookie_file}")
            results.append({
                "platform": platform_name,
                "account": account_name,
                "status": "file_not_found"
            })
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "platform": platform_name,
                "account": account_name,
                "status": "error",
                "error": str(e)
            })

    # 打印汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)

    for result in results:
        status = result['status']
        emoji = "✅" if status == "valid" else "❌" if status == "expired" else "⚠️"
        print(f"{emoji} {result['platform']} ({result['account']}): {status}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(test_cookie_validation())
