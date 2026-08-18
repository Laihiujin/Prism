"""
One-shot SQLite -> MySQL migration helper.

This does NOT refactor the app to use MySQL at runtime yet; it only copies data.
Runtime migration should be done incrementally using SQLAlchemy/Alembic.

Usage (PowerShell):
  cd syn_backend
  $env:DATABASE_URL='mysql+pymysql://synapse:synapse@localhost:3306/synapse?charset=utf8mb4'
  ..\\synenv\\Scripts\\python.exe scripts\\maintenance\\migrate_sqlite_to_mysql.py
"""

from __future__ import annotations

import argparse
import sqlite3
from typing import Iterable, Sequence

from sqlalchemy import text

from fastapi_app.core.config import settings
from fastapi_app.db.sa_models import metadata
from fastapi_app.db.sqlalchemy_engine import get_engine


TABLES: Sequence[str] = (
    "ai_model_configs",
    "ai_threads",
    "ai_messages",
    "publish_presets",
    "publish_tasks",
    "file_records",
)


def _sqlite_rows(conn: sqlite3.Connection, table: str) -> tuple[list[str], list[tuple]]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    cur.execute(f"SELECT {', '.join(cols)} FROM {table}")
    return cols, cur.fetchall()


def _table_exists_sqlite(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", default=settings.DATABASE_PATH, help="SQLite DB path")
    args = parser.parse_args()

    if not (settings.DATABASE_URL and settings.DATABASE_URL.strip()):
        raise SystemExit("DATABASE_URL is empty; set it to a MySQL URL before running this migration.")

    sqlite_conn = sqlite3.connect(args.sqlite)
    try:
        engine = get_engine()

        # Create tables in MySQL (best-effort)
        metadata.create_all(engine)

        with engine.begin() as mysql_conn:
            for table in TABLES:
                if not _table_exists_sqlite(sqlite_conn, table):
                    continue
                cols, rows = _sqlite_rows(sqlite_conn, table)
                if not rows:
                    continue

                # Clear destination table (idempotent-ish for dev)
                mysql_conn.execute(text(f"DELETE FROM {table}"))

                placeholders = ", ".join([f":{c}" for c in cols])
                insert_sql = text(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})")
                payload = [dict(zip(cols, r)) for r in rows]
                mysql_conn.execute(insert_sql, payload)

        print("✅ Migration completed.")
        return 0
    finally:
        sqlite_conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

