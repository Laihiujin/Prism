"""
清理重复账号脚本
根据user_id合并同一平台的重复账号
"""
import sys
import io
import os
from pathlib import Path

# 设置UTF-8编码输出（Windows兼容）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent / "syn_backend"))

from myUtils.cookie_manager import cookie_manager

def clean_duplicate_accounts():
    """清理重复账号"""
    print("=" * 60)
    print("开始清理重复账号")
    print("=" * 60)

    # 获取所有账号
    all_accounts = cookie_manager.list_flat_accounts()

    # 按平台分组
    platform_groups = {}
    for account in all_accounts:
        platform = account['platform']
        if platform not in platform_groups:
            platform_groups[platform] = []
        platform_groups[platform].append(account)

    # 统计
    total_deleted = 0

    # 处理每个平台
    for platform, accounts in platform_groups.items():
        print(f"\n{'='*60}")
        print(f"处理平台: {platform} (共 {len(accounts)} 个账号)")
        print(f"{'='*60}")

        # 按user_id分组
        user_id_groups = {}
        no_user_id_accounts = []

        for account in accounts:
            user_id = account.get('user_id')
            if user_id:
                if user_id not in user_id_groups:
                    user_id_groups[user_id] = []
                user_id_groups[user_id].append(account)
            else:
                no_user_id_accounts.append(account)

        # 处理有user_id的重复账号
        for user_id, group in user_id_groups.items():
            if len(group) > 1:
                print(f"\n⚠️  发现重复账号 (UserID: {user_id})")
                print(f"   共 {len(group)} 个账号:")

                # 显示所有重复账号
                for i, acc in enumerate(group):
                    print(f"   [{i+1}] {acc['account_id'][:20]} | {acc['name']} | Status: {acc['status']}")

                # 选择保留哪个（优先级：valid > 其他 > expired）
                # 按状态排序
                sorted_group = sorted(group, key=lambda x: (
                    0 if x['status'] == 'valid' else 1 if x['status'] == 'error' else 2,
                    x.get('last_checked', ''),  # 最近检查时间
                ))

                keep_account = sorted_group[0]
                delete_accounts = sorted_group[1:]

                print(f"\n   ✅ 保留: {keep_account['name']} (ID: {keep_account['account_id'][:20]}, Status: {keep_account['status']})")
                print(f"   ❌ 删除 {len(delete_accounts)} 个重复账号:")

                for acc in delete_accounts:
                    print(f"      - {acc['name']} (ID: {acc['account_id'][:20]})")
                    try:
                        cookie_manager.delete_account(acc['account_id'])
                        total_deleted += 1
                        print(f"        ✅ 已删除")
                    except Exception as e:
                        print(f"        ❌ 删除失败: {e}")

        # 显示没有user_id的账号
        if no_user_id_accounts:
            print(f"\n⚠️  以下账号没有UserID（无法去重）:")
            for acc in no_user_id_accounts:
                print(f"   - {acc['name']} (ID: {acc['account_id'][:20]}, Status: {acc['status']})")

    print(f"\n{'='*60}")
    print(f"清理完成")
    print(f"{'='*60}")
    print(f"总计删除: {total_deleted} 个重复账号")
    print()

if __name__ == "__main__":
    clean_duplicate_accounts()
