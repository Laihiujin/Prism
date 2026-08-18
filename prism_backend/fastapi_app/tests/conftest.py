"""
Test configuration and fixtures
"""
import pytest
import sqlite3
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from fastapi_app.main import app
from fastapi_app.db.session import ConnectionPool


@pytest.fixture
def test_db():
    """Create a temporary test database"""
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    db_path = temp_db.name
    temp_db.close()

    # Initialize database schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create file_records table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filesize REAL NOT NULL,
            file_path TEXT NOT NULL,
            upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            published_at DATETIME,
            last_platform INTEGER,
            last_accounts TEXT,
            note TEXT,
            group_name TEXT
        )
    """)

    # Create accounts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            platform_code INTEGER NOT NULL,
            name TEXT,
            status TEXT DEFAULT 'pending',
            cookie_file TEXT,
            last_checked DATETIME,
            avatar TEXT,
            original_name TEXT,
            note TEXT,
            user_id TEXT
        )
    """)

    # Insert test data
    cursor.execute("""
        INSERT INTO file_records (filename, filesize, file_path, status)
        VALUES ('test1.mp4', 10.5, 'test1.mp4', 'pending'),
               ('test2.mp4', 20.3, 'test2.mp4', 'published')
    """)

    cursor.execute("""
        INSERT INTO accounts (account_id, platform, platform_code, name, status, user_id)
        VALUES ('test-account-1', 'douyin', 3, 'Test User 1', 'valid', 'user123'),
               ('test-account-2', 'xiaohongshu', 1, 'Test User 2', 'error', 'user456')
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def test_db_pool(test_db):
    """Create test database connection pool"""
    return ConnectionPool(test_db, pool_size=2)
