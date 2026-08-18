"""
数据库连接管理
"""
import sqlite3
import queue
import threading
from contextlib import contextmanager
from typing import Generator
from pathlib import Path
from fastapi_app.core.config import settings
from fastapi_app.core.logger import logger


class ConnectionPool:
    """SQLite连接池"""

    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self.pool = queue.Queue(maxsize=pool_size)
        self.lock = threading.Lock()

        # 确保数据库文件目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # 初始化连接池
        for _ in range(pool_size):
            conn = self._create_connection()
            self.pool.put(conn)

        logger.info(f"数据库连接池初始化完成: {db_path} (池大小: {pool_size})")

    def _create_connection(self) -> sqlite3.Connection:
        """创建新的数据库连接"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # 支持字典访问
        return conn

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """获取数据库连接（上下文管理器）"""
        conn = self.pool.get()
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库操作错误: {e}")
            raise
        finally:
            self.pool.put(conn)

    def close_all(self):
        """关闭所有连接"""
        while not self.pool.empty():
            conn = self.pool.get()
            conn.close()
        logger.info("数据库连接池已关闭")


# 创建全局连接池实例
main_db_pool = ConnectionPool(settings.DATABASE_PATH, pool_size=17)
cookie_db_pool = ConnectionPool(settings.COOKIE_DB_PATH, pool_size=17)
ai_logs_db_pool = ConnectionPool(settings.AI_LOGS_DB_PATH, pool_size=17)


# 依赖注入函数
def get_main_db() -> Generator[sqlite3.Connection, None, None]:
    """获取主数据库连接（依赖注入）"""
    with main_db_pool.get_connection() as conn:
        yield conn


def get_cookie_db() -> Generator[sqlite3.Connection, None, None]:
    """获取Cookie数据库连接（依赖注入）"""
    with cookie_db_pool.get_connection() as conn:
        yield conn


def get_ai_logs_db() -> Generator[sqlite3.Connection, None, None]:
    """获取AI日志数据库连接（依赖注入）"""
    with ai_logs_db_pool.get_connection() as conn:
        yield conn
