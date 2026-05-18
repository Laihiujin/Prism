"""
测试账号验证和去重系统
"""
import sys
import os
import asyncio

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "syn_backend"))

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from syn_backend.myUtils.cookie_manager import cookie_manager
from syn_backend.myUtils.auth import check_cookie
from datetime import datetime

def test_deduplication():
    """测试账号去重逻辑"""
    print("\n" + "="*60)
    print("测试 1: 账号去重逻辑")
    print("="*60)

    # 测试场景1: 添加一个普通账号
    print("\n场景1: 添加普通账号")
    test_account_1 = {
        "id": "test_001",
        "name": "测试账号1",
        "user_id": "test_user_123",
        "cookie": {"test": "cookie1"},
        "status": "valid",
        "note": "-",  # 默认备注
    }

    try:
        cookie_manager.add_account("douyin", test_account_1)
        print("[OK] Normal account added successfully")
    except Exception as e:
        print(f"[FAIL] Normal account addition failed: {e}")

    # 测试场景2: 添加同一个user_id的派发账号（应该覆盖）
    print("\n场景2: 添加同user_id的派发账号（应该覆盖）")
    test_account_2 = {
        "id": "test_002",  # 不同的ID
        "name": "测试账号2-派发",
        "user_id": "test_user_123",  # 相同的user_id
        "cookie": {"test": "cookie2"},
        "status": "valid",
        "note": "派发账号-外部用户A",
    }

    try:
        cookie_manager.add_account("douyin", test_account_2)
        print("[OK] Distribution account added successfully")
    except Exception as e:
        print(f"[FAIL] Distribution account addition failed: {e}")

    # 验证结果
    print("\n验证结果:")
    accounts = cookie_manager.list_flat_accounts()
    test_accounts = [acc for acc in accounts if acc['user_id'] == 'test_user_123']

    print(f"Found {len(test_accounts)} account(s) with test_user_123")
    for acc in test_accounts:
        print(f"  - ID: {acc['account_id']}, Name: {acc['name']}, Note: {acc['note']}")

    if len(test_accounts) == 1:
        if "派发" in test_accounts[0]['note']:
            print("[PASS] Distribution account successfully replaced normal account")
        else:
            print("[FAIL] Distribution account did not replace normal account")
    else:
        print(f"[FAIL] Should have 1 account, but found {len(test_accounts)}")

    # 测试场景3: 尝试用普通账号覆盖派发账号（应该失败）
    print("\n场景3: 尝试用普通账号覆盖派发账号（应该保留派发备注）")
    test_account_3 = {
        "id": "test_003",
        "name": "测试账号3-普通",
        "user_id": "test_user_123",
        "cookie": {"test": "cookie3"},
        "status": "valid",
        "note": "内部账号",
    }

    try:
        cookie_manager.add_account("douyin", test_account_3)
        print("[OK] Normal account added successfully")
    except Exception as e:
        print(f"[FAIL] Normal account addition failed: {e}")

    # 验证结果
    print("\n验证结果:")
    accounts = cookie_manager.list_flat_accounts()
    test_accounts = [acc for acc in accounts if acc['user_id'] == 'test_user_123']

    print(f"Found {len(test_accounts)} account(s) with test_user_123")
    for acc in test_accounts:
        print(f"  - ID: {acc['account_id']}, Name: {acc['name']}, Note: {acc['note']}")

    if len(test_accounts) == 1:
        if "派发" in test_accounts[0]['note']:
            print("[PASS] Distribution account note correctly preserved")
        else:
            print("[FAIL] Distribution account note was overwritten")

    # 清理测试数据
    print("\nCleaning up test data...")
    for acc in test_accounts:
        cookie_manager.delete_account(acc['account_id'])
    print("[OK] Test data cleaned up")

async def test_account_validation():
    """测试账号验证逻辑"""
    print("\n" + "="*60)
    print("测试 2: 账号验证逻辑")
    print("="*60)

    accounts = cookie_manager.list_flat_accounts()

    if not accounts:
        print("[WARN] No accounts in database, skipping validation test")
        return

    print(f"\nFound {len(accounts)} accounts, validating first 3...")

    for i, account in enumerate(accounts[:3]):
        print(f"\n测试账号 {i+1}/{min(3, len(accounts))}: {account['name']} ({account['platform']})")
        print(f"  当前状态: {account['status']}")

        try:
            result = await check_cookie(account['platform_code'], account['cookie_file'])

            if isinstance(result, dict):
                status = result.get("status", "unknown")
                print(f"  Validation result: {status}")
                if status == "valid":
                    print(f"  [OK] Account is valid")
                    if result.get("avatar"):
                        print(f"  Avatar: {result['avatar'][:80]}...")
                    if result.get("name"):
                        print(f"  Name: {result['name']}")
                else:
                    print(f"  [EXPIRED] Account is expired")
            else:
                print(f"  Validation result: {'valid' if result else 'expired'}")

        except Exception as e:
            print(f"  [ERROR] Validation failed: {e}")

def main():
    """主测试函数"""
    print("\n[Test] Starting account system tests\n")

    # 测试1: 去重逻辑
    test_deduplication()

    # 测试2: 账号验证
    asyncio.run(test_account_validation())

    print("\n[Test] All tests completed!\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] Test execution failed: {e}")
        import traceback
        traceback.print_exc()
