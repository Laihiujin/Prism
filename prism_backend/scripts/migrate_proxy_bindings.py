"""
迁移脚本：把 ip_pool.json 的 bound_account_ids 同步到 cookie_accounts.proxy_id。

权威绑定来源 = accounts.proxy_id（sticky）。
此脚本用于把旧的 JSON 反向索引绑定迁移到账号表，做一次性回填。

用法：
    cd prism_backend && python3 scripts/migrate_proxy_bindings.py
"""
import json
import sqlite3
import sys
from pathlib import Path

# 让 prism_backend 内的包可被导入
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    ip_pool_file = ROOT / "data" / "ip_pool.json"
    db_path = ROOT / "db" / "cookie_store.db"

    if not ip_pool_file.exists():
        print(f"[skip] 未找到 {ip_pool_file}（无代理数据需迁移）")
        return 0

    with open(ip_pool_file, "r", encoding="utf-8") as f:
        proxies = json.load(f)

    if not db_path.exists():
        print(f"[skip] 未找到 {db_path}")
        return 0

    # 确保列存在（幂等）
    conn = sqlite3.connect(db_path)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(cookie_accounts)").fetchall()]
    for col, decl in [
        ("proxy_id", "TEXT"),
        ("persona_profile_id", "TEXT"),
        ("browser_backend", "TEXT DEFAULT 'patchright'"),
    ]:
        if col not in cols:
            conn.execute(f"ALTER TABLE cookie_accounts ADD COLUMN {col} {decl}")
    conn.commit()

    migrated = 0
    for proxy in proxies:
        proxy_id = proxy.get("id")
        bound = proxy.get("bound_account_ids") or []
        if not proxy_id or not bound:
            continue
        for account_id in bound:
            cur = conn.execute(
                "UPDATE cookie_accounts SET proxy_id = ? WHERE account_id = ? AND (proxy_id IS NULL OR proxy_id = '')",
                (proxy_id, account_id),
            )
            if cur.rowcount:
                migrated += 1
                print(f"  绑定 {account_id} → proxy {proxy_id}")
    conn.commit()
    conn.close()
    print(f"[done] 迁移完成，回填 {migrated} 条 sticky 绑定")
    return 0


if __name__ == "__main__":
    sys.exit(main())
