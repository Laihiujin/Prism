"""
修复账号状态并验证Cookie
Fix account status and validate cookies
"""
import asyncio
import sys
from pathlib import Path

# 设置Windows控制台UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from myUtils.cookie_manager import cookie_manager
from myUtils.fast_cookie_validator import FastCookieValidator, PLATFORM_NAMES


async def fix_and_validate_accounts():
    """
    修复file_missing状态的账号并验证
    """
    print("\n" + "="*80)
    print("🔧 修复账号状态并验证Cookie")
    print("="*80)

    validator = FastCookieValidator()
    all_accounts = cookie_manager.list_flat_accounts()

    # 筛选需要修复的账号
    file_missing_accounts = [acc for acc in all_accounts if acc.get('status') == 'file_missing']

    print(f"\n📊 统计:")
    print(f"  总账号数: {len(all_accounts)}")
    print(f"  需要修复的账号: {len(file_missing_accounts)}")

    if not file_missing_accounts:
        print("\n✅ 没有需要修复的账号！")
        return

    print(f"\n开始修复和验证...\n")

    stats = {
        "valid": 0,
        "expired": 0,
        "error": 0,
        "fixed": 0
    }

    for i, account in enumerate(file_missing_accounts, 1):
        account_id = account.get('account_id')
        account_name = account.get('name', account_id)
        platform = account.get('platform')
        platform_code = account.get('platform_code')
        cookie_file = account.get('cookie_file')

        print(f"[{i}/{len(file_missing_accounts)}] 检查: {account_name} ({platform})")

        # 检查文件是否存在
        cookie_path = Path(cookie_manager.cookies_dir) / cookie_file

        if not cookie_path.exists():
            print(f"  ❌ Cookie文件不存在: {cookie_file}")
            continue

        print(f"  ✅ Cookie文件存在")

        # 验证Cookie
        try:
            result = await validator.validate_cookie_fast(platform_code, cookie_file, timeout=10)
            status = result.get("status")

            if status == "valid":
                print(f"  ✅ Cookie有效")
                print(f"     用户ID: {result.get('user_id', 'N/A')}")
                print(f"     用户名: {result.get('name', 'N/A')}")

                # 更新数据库状态
                cookie_manager.update_account_status(platform, account_id, 'valid')
                stats["valid"] += 1
                stats["fixed"] += 1
                print(f"  🔄 已更新状态: file_missing -> valid")

            elif status == "expired":
                print(f"  ❌ Cookie已失效")
                cookie_manager.update_account_status(platform, account_id, 'expired')
                stats["expired"] += 1
                stats["fixed"] += 1
                print(f"  🔄 已更新状态: file_missing -> expired")

            else:
                print(f"  ⚠️ 验证失败: {result.get('error', 'Unknown')}")
                stats["error"] += 1

        except Exception as e:
            print(f"  ❌ 验证出错: {e}")
            stats["error"] += 1

        print()

        # 短暂延迟
        await asyncio.sleep(0.5)

    # 打印汇总
    print("="*80)
    print("📈 修复汇总")
    print("="*80)
    print(f"\n✅ 有效账号: {stats['valid']}")
    print(f"❌ 失效账号: {stats['expired']}")
    print(f"⚠️ 错误/未知: {stats['error']}")
    print(f"🔧 已修复: {stats['fixed']}")

    # 显示最新状态
    print("\n" + "="*80)
    print("📊 当前所有账号状态")
    print("="*80 + "\n")

    updated_accounts = cookie_manager.list_flat_accounts()

    status_groups = {
        "valid": [],
        "expired": [],
        "file_missing": [],
        "unchecked": [],
        "other": []
    }

    for acc in updated_accounts:
        status = acc.get('status', 'unknown')
        if status in status_groups:
            status_groups[status].append(acc)
        else:
            status_groups['other'].append(acc)

    for status_name, accounts in status_groups.items():
        if accounts:
            status_icon = {
                "valid": "✅",
                "expired": "❌",
                "file_missing": "📁",
                "unchecked": "❓",
                "other": "⚠️"
            }.get(status_name, "•")

            print(f"{status_icon} {status_name.upper()}: {len(accounts)} 个")
            for acc in accounts:
                print(f"   - {acc.get('name', 'N/A')} ({acc.get('platform', 'N/A')}) - {acc.get('account_id')}")


if __name__ == "__main__":
    asyncio.run(fix_and_validate_accounts())
