"""
为已有账号补充user_id
从Cookie文件中提取user_id并更新到数据库
"""
import sys
import io
from pathlib import Path

# 设置UTF-8编码输出（Windows兼容）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent / "prism_backend"))

from myUtils.cookie_manager import cookie_manager

def backfill_user_ids():
    """为已有账号补充user_id"""
    print("=" * 60)
    print("开始补充账号UserID")
    print("=" * 60)

    # 获取所有账号
    all_accounts = cookie_manager.list_flat_accounts()

    updated_count = 0
    failed_count = 0

    for account in all_accounts:
        account_id = account['account_id']
        platform = account['platform']
        name = account['name']
        user_id = account.get('user_id')
        cookie_file = account.get('cookie_file')

        # 如果已经有user_id，跳过
        if user_id:
            print(f"✓ {platform} - {name}: 已有UserID ({user_id})")
            continue

        print(f"\n🔍 {platform} - {name} (ID: {account_id[:20]}...)")

        # 读取Cookie文件
        if not cookie_file:
            print(f"   ⚠️  没有Cookie文件")
            failed_count += 1
            continue

        cookie_path = Path("prism_backend/cookiesFile") / cookie_file
        if not cookie_path.exists():
            print(f"   ⚠️  Cookie文件不存在: {cookie_file}")
            failed_count += 1
            continue

        try:
            # 直接读取Cookie数据（不使用cookie_manager的方法）
            import json
            with open(cookie_path, 'r', encoding='utf-8') as f:
                cookie_data = json.load(f)

            print(f"   ✓ Cookie数据读取成功")

            # 提取user_id
            extracted_id = cookie_manager._extract_user_id_from_cookie(platform, cookie_data)

            if extracted_id:
                print(f"   ✅ 提取到UserID: {extracted_id}")

                # 更新数据库
                cookie_manager.update_account(
                    account_id,
                    user_id=extracted_id
                )

                print(f"   ✅ 已更新到数据库")
                updated_count += 1
            else:
                print(f"   ❌ 无法从Cookie中提取UserID")
                failed_count += 1

        except Exception as e:
            print(f"   ❌ 处理失败: {e}")
            failed_count += 1

    print(f"\n{'='*60}")
    print(f"补充完成")
    print(f"{'='*60}")
    print(f"成功: {updated_count} 个")
    print(f"失败: {failed_count} 个")
    print()

if __name__ == "__main__":
    backfill_user_ids()
