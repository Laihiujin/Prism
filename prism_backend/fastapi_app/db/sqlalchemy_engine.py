from __future__ import annotations

from sqlalchemy import create_engine, Engine

from fastapi_app.core.config import settings


def get_database_url() -> str:
    if settings.DATABASE_URL and settings.DATABASE_URL.strip():
        return settings.DATABASE_URL.strip()
    sqlite_path = settings.DATABASE_PATH.replace("\\", "/")
    # SQLAlchemy wants three slashes for absolute Windows paths once normalized.
    if ":" in sqlite_path[:3]:
        return f"sqlite+pysqlite:///{sqlite_path}"
    return f"sqlite+pysqlite:///{sqlite_path}"


def get_engine() -> Engine:
    url = get_database_url()
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(url, pool_pre_ping=True, future=True, connect_args=connect_args)

