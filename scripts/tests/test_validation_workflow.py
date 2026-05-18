"""
综合测试：登录流程和Cookie验证器
"""
import asyncio
import sys
from pathlib import Path

# 设置标准输出为UTF-8
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent / "syn_backend"))

from myUtils.fast_cookie_validator import get_fast_validator
from myUtils.cookie_manager import cookie_manager


async def test_cookie_validation_workflow():
    """测试完整的Cookie验证工作流程"""
    print("=" * 80)
    print("Cookie验证工作流程测试")
    print("=" * 80)

    validator = get_fast_validator()

    # 获取所有账号
    accounts = cookie_manager.list_flat_accounts()

    if not accounts:
        print("\n❌ 没有找到账号，请先登录一些账号")
        return

    print(f"\n📊 找到 {len(accounts)} 个账号")

    # 按平台分组统计
    platform_stats = {}
    for acc in accounts:
        platform = acc['platform']
        platform_stats[platform] = platform_stats.get(platform, 0) + 1

    print("\n平台分布:")
    for platform, count in platform_stats.items():
        print(f"  {platform}: {count}个账号")

    # 测试批量验证
    print("\n" + "=" * 80)
    print("开始批量验证（高性能模式）")
    print("=" * 80)

    account_list = [
        {
            'account_id': acc['account_id'],
            'platform_code': acc['platform_code'],
            'cookie_file': acc['cookie_file']
        }
        for acc in accounts
    ]

    import time
    start = time.time()

    results = await validator.batch_validate(account_list, max_concurrent=20)

    elapsed = time.time() - start

    # 统计结果
    stats = {
        'valid': 0,
        'expired': 0,
        'network_error': 0,
        'error': 0
    }

    for result in results:
        status = result.get('status', 'error')
        stats[status] = stats.get(status, 0) + 1

    print(f"\n✅ 验证完成！")
    print(f"总耗时: {elapsed:.2f}秒")
    print(f"平均耗时: {elapsed/len(accounts)*1000:.0f}ms/账号")
    print(f"吞吐量: {len(accounts)/elapsed:.1f}账号/秒")

    print(f"\n📈 验证结果:")
    print(f"  ✅ 有效: {stats['valid']}")
    print(f"  ❌ 失效: {stats['expired']}")
    print(f"  🌐 网络错误: {stats['network_error']}")
    print(f"  ⚠️  其他错误: {stats['error']}")

    # 详细结果
    print(f"\n📋 详细结果:")

    # 按平台分组显示
    by_platform = {}
    for result in results:
        platform = result.get('platform', 'unknown')
        if platform not in by_platform:
            by_platform[platform] = []
        by_platform[platform].append(result)

    for platform, platform_results in by_platform.items():
        print(f"\n  【{platform}】")
        for result in platform_results:
            account_id = result['account_id'][:30]
            status = result['status']
            name = result.get('name') or 'N/A'
            user_id = result.get('user_id') or 'N/A'

            status_icon = {
                'valid': '✅',
                'expired': '❌',
                'network_error': '🌐',
                'error': '⚠️'
            }.get(status, '❓')

            print(f"    {status_icon} {account_id}... - {status}")
            if status == 'valid':
                print(f"       名称: {name}, ID: {user_id}")
            elif result.get('error'):
                print(f"       错误: {result['error']}")

    # 提供建议
    print(f"\n💡 建议:")
    if stats['expired'] > 0:
        print(f"  - 有 {stats['expired']} 个账号已失效，建议重新登录")
    if stats['network_error'] > 0:
        print(f"  - 有 {stats['network_error']} 个账号出现网络错误，请检查网络连接")
    if stats['error'] > 0:
        print(f"  - 有 {stats['error']} 个账号验证出错，请检查Cookie文件完整性")

    print("\n" + "=" * 80)


async def test_specific_platform(platform_name):
    """测试特定平台的验证"""
    print(f"\n测试 {platform_name} 平台验证")
    print("-" * 40)

    validator = get_fast_validator()
    accounts = cookie_manager.list_flat_accounts()

    # 筛选指定平台的账号
    platform_accounts = [acc for acc in accounts if acc['platform'] == platform_name]

    if not platform_accounts:
        print(f"❌ 没有找到 {platform_name} 平台的账号")
        return

    print(f"找到 {len(platform_accounts)} 个 {platform_name} 账号")

    account_list = [
        {
            'account_id': acc['account_id'],
            'platform_code': acc['platform_code'],
            'cookie_file': acc['cookie_file']
        }
        for acc in platform_accounts
    ]

    import time
    start = time.time()
    results = await validator.batch_validate(account_list, max_concurrent=10)
    elapsed = time.time() - start

    print(f"\n验证完成: {elapsed:.2f}秒, 平均 {elapsed/len(platform_accounts)*1000:.0f}ms/账号")

    for result in results:
        account_id = result['account_id'][:30]
        status = result['status']
        print(f"  {account_id}... - {status}")


async def main():
    """主测试函数"""
    # 测试完整工作流程
    await test_cookie_validation_workflow()

    # 测试特定平台（如果需要）
    # await test_specific_platform('channels')  # 视频号
    # await test_specific_platform('bilibili')  # B站
    # await test_specific_platform('douyin')    # 抖音


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
