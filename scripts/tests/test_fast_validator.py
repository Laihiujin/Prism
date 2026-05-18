"""
测试高性能Cookie验证器
"""
import asyncio
import time
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "syn_backend"))

from myUtils.fast_cookie_validator import FastCookieValidator, get_fast_validator
from myUtils.cookie_manager import cookie_manager


async def test_single_validation():
    """测试单个账号验证"""
    print("\n=== 测试单个账号验证 ===")

    validator = get_fast_validator()

    # 获取一些测试账号
    accounts = cookie_manager.list_flat_accounts()
    if not accounts:
        print("没有找到账号进行测试")
        return

    # 测试第一个账号
    test_account = accounts[0]
    print(f"\n测试账号: {test_account['account_id']}")
    print(f"平台: {test_account['platform']} (code: {test_account['platform_code']})")
    print(f"Cookie文件: {test_account['cookie_file']}")

    start = time.time()
    result = await validator.validate_cookie_fast(
        test_account['platform_code'],
        test_account['cookie_file']
    )
    elapsed = (time.time() - start) * 1000

    print(f"\n验证结果: {result['status']}")
    print(f"用户ID: {result.get('user_id')}")
    print(f"用户名: {result.get('name')}")
    print(f"头像: {result.get('avatar')}")
    if result.get('error'):
        print(f"错误: {result['error']}")
    print(f"耗时: {elapsed:.0f}ms")


async def test_batch_validation():
    """测试批量验证性能"""
    print("\n\n=== 测试批量验证性能 ===")

    validator = get_fast_validator()

    # 获取所有账号
    accounts = cookie_manager.list_flat_accounts()
    if not accounts:
        print("没有找到账号进行测试")
        return

    total = len(accounts)
    print(f"\n总账号数: {total}")

    # 准备账号列表
    account_list = [
        {
            'account_id': acc['account_id'],
            'platform_code': acc['platform_code'],
            'cookie_file': acc['cookie_file']
        }
        for acc in accounts
    ]

    # 测试不同并发数
    for max_concurrent in [5, 10, 20, 50]:
        if total < max_concurrent:
            max_concurrent = total

        print(f"\n--- 并发数: {max_concurrent} ---")

        start = time.time()
        results = await validator.batch_validate(account_list, max_concurrent=max_concurrent)
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

        print(f"总耗时: {elapsed:.2f}秒")
        print(f"平均耗时: {elapsed/total*1000:.0f}ms/账号")
        print(f"有效: {stats['valid']}")
        print(f"失效: {stats['expired']}")
        print(f"网络错误: {stats['network_error']}")
        print(f"其他错误: {stats['error']}")

        # 显示前5个结果的详情
        print("\n前5个账号详情:")
        for i, result in enumerate(results[:5]):
            print(f"  {i+1}. {result['account_id']} - {result['status']} - {result.get('name', 'N/A')}")


async def test_comparison():
    """对比新旧验证器性能"""
    print("\n\n=== 性能对比测试 ===")

    # 获取测试账号
    accounts = cookie_manager.list_flat_accounts()
    if not accounts or len(accounts) < 3:
        print("需要至少3个账号进行对比测试")
        return

    # 取前3个账号
    test_accounts = accounts[:3]

    print(f"\n测试账号数: {len(test_accounts)}")

    # 测试新验证器
    print("\n--- 新验证器（fast_cookie_validator）---")
    validator = get_fast_validator()

    account_list = [
        {
            'account_id': acc['account_id'],
            'platform_code': acc['platform_code'],
            'cookie_file': acc['cookie_file']
        }
        for acc in test_accounts
    ]

    start = time.time()
    results = await validator.batch_validate(account_list, max_concurrent=10)
    fast_elapsed = time.time() - start

    print(f"总耗时: {fast_elapsed:.2f}秒")
    print(f"平均耗时: {fast_elapsed/len(test_accounts)*1000:.0f}ms/账号")

    # 显示结果
    for result in results:
        print(f"  {result['account_id']}: {result['status']}")


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("高性能Cookie验证器测试")
    print("=" * 60)

    try:
        # 测试1: 单个账号验证
        await test_single_validation()

        # 测试2: 批量验证性能
        await test_batch_validation()

        # 测试3: 性能对比
        await test_comparison()

        print("\n" + "=" * 60)
        print("所有测试完成")
        print("=" * 60)

    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
