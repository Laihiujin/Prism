"""
SQLAlchemy table definitions (minimal set for migration/bootstrapping).

These are intentionally conservative (TEXT over JSON, nullable where unsure),
so they can be created in MySQL and used for data migration from SQLite.
"""

from __future__ import annotations

from sqlalchemy import (
    MetaData,
    Table,
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
)
from sqlalchemy.sql import func

metadata = MetaData()


file_records = Table(
    "file_records",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("filename", Text),
    Column("filesize", Float),
    Column("file_path", Text),
    Column("upload_time", DateTime),
    Column("status", String(32), server_default="pending"),
    Column("published_at", DateTime),
    Column("last_platform", Integer),
    Column("last_accounts", Text),
    Column("note", Text),
    Column("group_name", Text),
    Column("title", Text),
    Column("description", Text),
    Column("tags", Text),
    Column("cover_image", Text),
    Column("duration", Float),
    Column("ai_title", Text),
    Column("ai_description", Text),
    Column("ai_tags", Text),
    Column("ai_generated_at", DateTime),
)


publish_presets = Table(
    "publish_presets",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("label", Text, nullable=False),
    Column("platform", Text, nullable=False),
    Column("accounts", Text, nullable=False),
    Column("material_ids", Text),
    Column("title", Text),
    Column("description", Text),
    Column("tags", Text),
    Column("schedule_enabled", Integer, server_default="0"),
    Column("videos_per_day", Integer, server_default="1"),
    Column("schedule_date", Text),
    Column("time_point", Text, server_default="10:00"),
    Column("usage_count", Integer, server_default="0"),
    Column("created_at", DateTime, server_default=func.now()),
    Column("updated_at", DateTime, server_default=func.now(), onupdate=func.now()),
)


publish_tasks = Table(
    "publish_tasks",
    metadata,
    Column("task_id", Integer, primary_key=True, autoincrement=True),
    Column("plan_id", Integer),
    Column("package_id", Integer),
    Column("platform", Text),
    Column("account_id", Text),
    Column("material_id", Text),
    Column("title", Text),
    Column("tags", Text),
    Column("cover", Text),
    Column("schedule_time", DateTime),
    Column("publish_mode", Text),
    Column("status", Text),
    Column("external_user_id", Text),
    Column("external_account_id", Text),
    Column("result_metrics", Text),
    Column("error_message", Text),
    Column("created_at", DateTime, server_default=func.now()),
    Column("updated_at", DateTime, server_default=func.now(), onupdate=func.now()),
    Column("published_at", DateTime),
    Column("completed_at", DateTime),
)


ai_model_configs = Table(
    "ai_model_configs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("service_type", Text, nullable=False, unique=True),
    Column("provider", Text, nullable=False),
    Column("api_key", Text, nullable=False),
    Column("base_url", Text),
    Column("model_name", Text),
    Column("extra_config", Text),
    Column("is_active", Integer, server_default="1"),
    Column("created_at", DateTime, server_default=func.now()),
    Column("updated_at", DateTime, server_default=func.now(), onupdate=func.now()),
)


ai_threads = Table(
    "ai_threads",
    metadata,
    Column("id", Text, primary_key=True),
    Column("title", Text, nullable=False),
    Column("mode", Text, server_default="chat"),
    Column("created_at", Text),
    Column("updated_at", Text),
    Column("metadata", Text),
    Column("message_count", Integer, server_default="0"),
)


ai_messages = Table(
    "ai_messages",
    metadata,
    Column("id", Text, primary_key=True),
    Column("thread_id", Text, nullable=False),
    Column("role", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("tool_calls", Text),
    Column("metadata", Text),
    Column("created_at", Text),
)
