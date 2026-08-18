"""
SQLite schema bootstrap/migrations.

Goal: keep the app usable on fresh installs and older local DB files by
creating required tables and adding missing columns (best-effort).
"""

from __future__ import annotations

import sqlite3
from typing import Dict, Iterable

from fastapi_app.core.config import settings
from fastapi_app.core.logger import logger


def _existing_columns(cursor: sqlite3.Cursor, table: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _ensure_columns(
    conn: sqlite3.Connection,
    table: str,
    required: Dict[str, str],
) -> int:
    """
    Ensure columns exist on a given table using ALTER TABLE ADD COLUMN.
    Returns number of columns added.
    """
    cursor = conn.cursor()
    existing = _existing_columns(cursor, table)
    added = 0
    for column_name, alter_sql in required.items():
        if column_name in existing:
            continue
        try:
            cursor.execute(alter_sql)
            added += 1
        except sqlite3.OperationalError as e:
            # Concurrent startup / multiple workers may race to add columns.
            if "duplicate column name" in str(e).lower():
                continue
            raise
    return added


def ensure_main_db_schema(conn: sqlite3.Connection) -> None:
    """
    Ensure required tables/columns exist in settings.DATABASE_PATH.
    """
    cursor = conn.cursor()

    # --- file_records (materials) ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS file_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            filesize REAL,
            file_path TEXT,
            upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            published_at DATETIME,
            last_platform INTEGER,
            last_accounts TEXT,
            note TEXT,
            group_name TEXT,
            title TEXT,
            description TEXT,
            tags TEXT,
            cover_image TEXT,
            duration REAL,
            ai_title TEXT,
            ai_description TEXT,
            ai_tags TEXT,
            ai_generated_at TIMESTAMP
        )
        """
    )

    file_records_required: Dict[str, str] = {
        "filename": "ALTER TABLE file_records ADD COLUMN filename TEXT",
        "filesize": "ALTER TABLE file_records ADD COLUMN filesize REAL",
        "file_path": "ALTER TABLE file_records ADD COLUMN file_path TEXT",
        "upload_time": "ALTER TABLE file_records ADD COLUMN upload_time DATETIME",
        "status": "ALTER TABLE file_records ADD COLUMN status TEXT DEFAULT 'pending'",
        "published_at": "ALTER TABLE file_records ADD COLUMN published_at DATETIME",
        "last_platform": "ALTER TABLE file_records ADD COLUMN last_platform INTEGER",
        "last_accounts": "ALTER TABLE file_records ADD COLUMN last_accounts TEXT",
        "note": "ALTER TABLE file_records ADD COLUMN note TEXT",
        "group_name": "ALTER TABLE file_records ADD COLUMN group_name TEXT",
        "title": "ALTER TABLE file_records ADD COLUMN title TEXT",
        "description": "ALTER TABLE file_records ADD COLUMN description TEXT",
        "tags": "ALTER TABLE file_records ADD COLUMN tags TEXT",
        "cover_image": "ALTER TABLE file_records ADD COLUMN cover_image TEXT",
        "duration": "ALTER TABLE file_records ADD COLUMN duration REAL",
        "ai_title": "ALTER TABLE file_records ADD COLUMN ai_title TEXT",
        "ai_description": "ALTER TABLE file_records ADD COLUMN ai_description TEXT",
        "ai_tags": "ALTER TABLE file_records ADD COLUMN ai_tags TEXT",
        "ai_generated_at": "ALTER TABLE file_records ADD COLUMN ai_generated_at TIMESTAMP",
    }

    # --- publish_presets ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS publish_presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            platform TEXT NOT NULL,
            accounts TEXT NOT NULL,
            material_ids TEXT,
            title TEXT,
            description TEXT,
            schedule_enabled INTEGER DEFAULT 0,
            videos_per_day INTEGER DEFAULT 1,
            schedule_date TEXT,
            time_point TEXT DEFAULT '10:00',
            usage_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    publish_presets_required: Dict[str, str] = {
        "usage_count": "ALTER TABLE publish_presets ADD COLUMN usage_count INTEGER DEFAULT 0",
    }

    # Note: celery_task_id was added to the CREATE TABLE statement with UNIQUE constraint
    # SQLite doesn't allow adding UNIQUE constraint via ALTER TABLE, so we only add the column if it doesn't exist
    publish_tasks_required: Dict[str, str] = {
        "celery_task_id": "ALTER TABLE publish_tasks ADD COLUMN celery_task_id TEXT",
        "completed_at": "ALTER TABLE publish_tasks ADD COLUMN completed_at DATETIME",
        "task_data": "ALTER TABLE publish_tasks ADD COLUMN task_data TEXT",  # 完整的任务数据（JSON）
        "priority": "ALTER TABLE publish_tasks ADD COLUMN priority INTEGER DEFAULT 5",
    }

    # --- publish_tasks ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS publish_tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            celery_task_id TEXT UNIQUE,
            plan_id INTEGER,
            package_id INTEGER,
            platform TEXT,
            account_id TEXT,
            material_id TEXT,
            title TEXT,
            tags TEXT,
            cover TEXT,
            schedule_time DATETIME,
            publish_mode TEXT DEFAULT 'auto',
            status TEXT DEFAULT 'pending',
            external_user_id TEXT,
            external_account_id TEXT,
            result_metrics TEXT,
            error_message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            published_at DATETIME,
            completed_at DATETIME
        )
        """
    )

    # --- ai_model_configs ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_model_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_type TEXT NOT NULL UNIQUE,
            provider TEXT NOT NULL,
            api_key TEXT NOT NULL,
            base_url TEXT,
            model_name TEXT,
            extra_config TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()

    added = 0
    added += _ensure_columns(conn, "file_records", file_records_required)
    added += _ensure_columns(conn, "publish_presets", publish_presets_required)
    added += _ensure_columns(conn, "publish_tasks", publish_tasks_required)  # 添加celery_task_id字段迁移

    if added:
        conn.commit()
        logger.info(f"[DB] Schema ensured; added {added} missing column(s)")


def ensure_default_schema() -> None:
    """
    Convenience entrypoint using settings.DATABASE_PATH.
    """
    conn = sqlite3.connect(settings.DATABASE_PATH)
    try:
        ensure_main_db_schema(conn)
    finally:
        conn.close()

