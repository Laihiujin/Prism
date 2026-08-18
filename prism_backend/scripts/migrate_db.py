import sqlite3
import os
import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from config.conf import BASE_DIR

db_path = Path(BASE_DIR) / "syn_backend" / "db" / "cookie_store.db"
print(f"DB Path: {db_path}")

if not db_path.exists():
    # Try without syn_backend if it's relative
    db_path = Path(BASE_DIR) / "db" / "cookie_store.db"
    print(f"Trying DB Path: {db_path}")

if not db_path.exists():
    print("DB not found!")
    sys.exit(1)

with sqlite3.connect(db_path) as conn:
    cursor = conn.execute("PRAGMA table_info(cookie_accounts)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"Columns: {columns}")
    if "avatar" not in columns:
        print("Adding avatar column...")
        conn.execute("ALTER TABLE cookie_accounts ADD COLUMN avatar TEXT")
        conn.commit()
        print("Done.")
    else:
        print("Avatar column already exists.")
