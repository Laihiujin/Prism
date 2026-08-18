"""
修复账号 cookie_file 为 NULL 的问题
检查并更新数据库中缺失的 cookie_file 路径
"""
import sqlite3
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))
from myUtils.cookie_manager import cookie_manager

DB_PATH = str(cookie_manager.db_path)
COOKIE_DIR = cookie_manager.cookies_dir


def diagnose_accounts():
    """诊断账号状态"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 查询所有账号
        cursor.execute("""
            SELECT account_id, platform, name, status, cookie_file, user_id
            FROM cookie_accounts
            ORDER BY platform, name
        """)

        accounts = cursor.fetchall()

        print(f"\n[INFO] Account Diagnostic Report")
        print(f"=" * 80)
        print(f"Total Accounts: {len(accounts)}\n")

        null_cookie_file = []
        valid_accounts = []
        missing_files = []

        for acc in accounts:
            acc_dict = dict(acc)
            account_id = acc_dict['account_id']
            cookie_file = acc_dict['cookie_file']

            if not cookie_file:
                null_cookie_file.append(acc_dict)
                print(f"[X] [{acc_dict['platform']}] {acc_dict['name']} ({account_id})")
                print(f"   Status: {acc_dict['status']}")
                print(f"   Cookie File: NULL")
                print()
            else:
                file_path = COOKIE_DIR / cookie_file
                if not file_path.exists():
                    missing_files.append(acc_dict)
                    print(f"[!] [{acc_dict['platform']}] {acc_dict['name']} ({account_id})")
                    print(f"   Cookie File: {cookie_file} (File Not Found)")
                    print()
                else:
                    valid_accounts.append(acc_dict)

        print(f"\nStatistics:")
        print(f"- [OK] Valid Accounts: {len(valid_accounts)}")
        print(f"- [X]  NULL Cookie File: {len(null_cookie_file)}")
        print(f"- [!]  Missing Files: {len(missing_files)}")

        return null_cookie_file, missing_files


def fix_null_cookie_files(null_accounts):
    """尝试修复 cookie_file 为 NULL 的账号"""
    print(f"\n[REPAIR] Starting repair process...")

    # 获取所有 JSON 文件
    json_files = list(COOKIE_DIR.glob("*.json"))
    print(f"Found {len(json_files)} Cookie files")

    fixed = 0

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        for acc in null_accounts:
            account_id = acc['account_id']

            # 尝试找到匹配的文件
            # 1. 尝试 account_id.json
            possible_file = COOKIE_DIR / f"{account_id}.json"

            if possible_file.exists():
                filename = possible_file.name
                cursor.execute(
                    "UPDATE cookie_accounts SET cookie_file = ? WHERE account_id = ?",
                    (filename, account_id)
                )
                print(f"[OK] Fixed: {acc['name']} -> {filename}")
                fixed += 1
            else:
                print(f"[X] Cannot fix: {acc['name']} (File not found)")

        conn.commit()

    print(f"\n[OK] Repair completed: {fixed}/{len(null_accounts)}")
    return fixed


def main():
    print("=" * 80)
    print("Account Cookie File Diagnostic & Repair Tool")
    print("=" * 80)

    # 诊断
    null_accounts, missing_files = diagnose_accounts()

    # 如果有 NULL 的账号，尝试修复
    if null_accounts:
        print(f"\nFound {len(null_accounts)} accounts with NULL cookie_file")
        choice = input("Attempt auto-repair? (y/n): ").strip().lower()

        if choice == 'y':
            fix_null_cookie_files(null_accounts)

            # 重新诊断
            print("\n" + "=" * 80)
            print("Re-diagnostic after repair:")
            print("=" * 80)
            diagnose_accounts()

    print("\n[OK] Complete!")


if __name__ == "__main__":
    main()
