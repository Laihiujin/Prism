"""
修复账号数据库记录与实际文件不匹配的问题
"""
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
import sqlite3


def fix_cookie_file_mismatch():
    """
    修复cookie_file字段与实际文件名不匹配的问题
    """
    print("\n" + "="*80)
    print("🔧 修复Cookie文件名不匹配问题")
    print("="*80 + "\n")

    # 获取所有磁盘文件
    disk_files = {f.name: f for f in cookie_manager.cookies_dir.glob("*.json")}
    print(f"📁 磁盘文件数: {len(disk_files)}")

    # 获取所有账号
    accounts = cookie_manager.list_flat_accounts()
    print(f"📊 数据库账号数: {len(accounts)}\n")

    fixed_count = 0

    for account in accounts:
        account_id = account['account_id']
        cookie_file = account.get('cookie_file')
        platform = account['platform']

        if not cookie_file:
            print(f"⚠️ {account_id} - 缺少cookie_file字段")
            continue

        # 检查文件是否存在
        if cookie_file in disk_files:
            continue  # 文件匹配，跳过

        # 文件不存在，尝试查找可能的匹配
        possible_files = [
            f"{account_id}.json",  # 标准格式
            f"{platform}_{account_id}.json",  # 带平台前缀
        ]

        found_file = None
        for possible in possible_files:
            if possible in disk_files:
                found_file = possible
                break

        if found_file:
            print(f"🔍 找到匹配: {account['name']} ({platform})")
            print(f"   数据库: {cookie_file}")
            print(f"   实际:   {found_file}")

            # 更新数据库
            with sqlite3.connect(cookie_manager.db_path) as conn:
                conn.execute(
                    "UPDATE cookie_accounts SET cookie_file = ? WHERE account_id = ?",
                    (found_file, account_id)
                )
                print(f"   ✅ 已更新")
                fixed_count += 1

                # 如果状态是file_missing，更新为unchecked
                if account['status'] == 'file_missing':
                    conn.execute(
                        "UPDATE cookie_accounts SET status = ? WHERE account_id = ?",
                        ('unchecked', account_id)
                    )
                    print(f"   🔄 状态更新: file_missing -> unchecked")

            print()
        else:
            print(f"❌ 未找到文件: {account['name']} ({platform}) - {cookie_file}\n")

    print("="*80)
    print(f"✅ 修复完成: {fixed_count} 个账号")
    print("="*80)


if __name__ == "__main__":
    fix_cookie_file_mismatch()
