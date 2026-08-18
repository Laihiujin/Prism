from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional

import sqlite3
from sqlalchemy.engine import Connection

from fastapi_app.core.config import settings
from fastapi_app.db.sqlalchemy_engine import get_engine


def mysql_enabled() -> bool:
    return bool((settings.DATABASE_URL or "").strip())


@contextmanager
def sa_connection() -> Generator[Connection, None, None]:
    """
    SQLAlchemy connection (MySQL when DATABASE_URL is set; otherwise SQLite via SQLAlchemy).
    """
    engine = get_engine()
    with engine.begin() as conn:
        yield conn


@contextmanager
def sqlite_connection(path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Direct sqlite3 connection (deprecated once MySQL is enabled).
    """
    conn = sqlite3.connect(path or settings.DATABASE_PATH, check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()

