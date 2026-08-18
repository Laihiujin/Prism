import json
import sys
import os

# Add the project root to the Python path to allow imports from myUtils
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from .cookie_manager import cookie_manager


def list_accounts():
    platforms = cookie_manager.get_all_accounts()
    if not platforms:
        print("No accounts stored.", file=sys.stderr)
        return
    for platform in platforms:
        print(f"[{platform['name']}]")
        for account in platform["accounts"]:
            print(
                f"  - {account['id']} | {account['name']} | status={account['status']} "
                f"| cookie_file={account.get('filePath')} | last={account.get('last_checked')}"
            )


def show_account(account_id: str):
    account = cookie_manager.get_account_by_id(account_id)
    if not account:
        print(f"Account {account_id} not found.", file=sys.stderr)
        sys.exit(1)
    payload = {
        "id": account["account_id"],
        "platform": account["platform"],
        "name": account["name"],
        "status": account["status"],
        "last_checked": account["last_checked"],
        "cookie": account.get("cookie"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def delete_account(account_id: str):
    if cookie_manager.delete_account(account_id):
        print(f"Account {account_id} deleted successfully.")
    else:
        print(f"Failed to delete account {account_id}.", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python call_cookie_manager.py [list|show|delete] [args...]", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        list_accounts()
    elif command == "show":
        if len(sys.argv) < 3:
            print("Usage: python call_cookie_manager.py show [account_id]", file=sys.stderr)
            sys.exit(1)
        show_account(sys.argv[2])
    elif command == "delete":
        if len(sys.argv) < 3:
            print("Usage: python call_cookie_manager.py delete [account_id]", file=sys.stderr)
            sys.exit(1)
        delete_account(sys.argv[2])
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"An unexpected error occurred in call_cookie_manager.py: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
