"""
AI 日志记录器
记录 AI 调用日志、监控成功率
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List


class AILogger:
    """AI 调用日志记录器"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else Path(__file__).parent.parent / "db" / "ai_logs.db"
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    instruction TEXT,
                    status TEXT NOT NULL,
                    response TEXT,
                    error TEXT,
                    tokens_used INTEGER,
                    execution_time REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    script_called TEXT,
                    script_result TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_health_check (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def log_call(
        self,
        provider: str,
        model_id: str,
        instruction: Optional[str],
        status: str,
        response: Optional[str] = None,
        error: Optional[str] = None,
        tokens_used: Optional[int] = None,
        execution_time: Optional[float] = None,
        script_called: Optional[str] = None,
        script_result: Optional[str] = None,
    ):
        """记录 AI 调用"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO ai_calls (
                        provider, model_id, instruction, status, response, error,
                        tokens_used, execution_time, script_called, script_result
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    provider, model_id, instruction, status, response, error,
                    tokens_used, execution_time, script_called, script_result
                ))
                conn.commit()
        except Exception as e:
            print(f"Failed to log call: {e}")

    def log_health_check(self, provider: str, status: str, error: Optional[str] = None):
        """记录健康检查"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO ai_health_check (provider, status, error)
                    VALUES (?, ?, ?)
                """, (provider, status, error))
                conn.commit()
        except Exception as e:
            print(f"Failed to log health check: {e}")

    def get_statistics(
        self,
        provider: Optional[str] = None,
        model_id: Optional[str] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 构建查询条件
                where_clause = f"timestamp > datetime('now', '-{hours} hours')"
                params = []
                
                if provider:
                    where_clause += " AND provider = ?"
                    params.append(provider)
                if model_id:
                    where_clause += " AND model_id = ?"
                    params.append(model_id)
                
                # 获取统计数据
                cursor.execute(f"""
                    SELECT 
                        COUNT(*) as total_calls,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_calls,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_calls,
                        AVG(execution_time) as avg_execution_time,
                        SUM(tokens_used) as total_tokens
                    FROM ai_calls
                    WHERE {where_clause}
                """, params)
                
                result = cursor.fetchone()
                if result:
                    total, success, failed, avg_time, total_tokens = result
                    total = total or 0
                    success = success or 0
                    failed = failed or 0
                    
                    return {
                        "total_calls": total,
                        "success_calls": success,
                        "failed_calls": failed,
                        "success_rate": (success / total * 100) if total > 0 else 0,
                        "avg_execution_time": avg_time or 0,
                        "total_tokens": total_tokens or 0,
                    }
                
                return {
                    "total_calls": 0,
                    "success_calls": 0,
                    "failed_calls": 0,
                    "success_rate": 0,
                    "avg_execution_time": 0,
                    "total_tokens": 0,
                }
        except Exception as e:
            print(f"Failed to get statistics: {e}")
            return {}

    def get_recent_calls(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近的调用记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        id, provider, model_id, instruction, status, response, error,
                        tokens_used, execution_time, timestamp, script_called, script_result
                    FROM ai_calls
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
                
                columns = [d[0] for d in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Failed to get recent calls: {e}")
            return []

    def get_provider_health(self, provider: str, hours: int = 24) -> Dict[str, Any]:
        """获取提供商健康状态"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 获取最近的健康检查
                cursor.execute("""
                    SELECT status, error, timestamp
                    FROM ai_health_check
                    WHERE provider = ? AND timestamp > datetime('now', '-{} hours')
                    ORDER BY timestamp DESC
                    LIMIT 1
                """.format(hours), (provider,))
                
                result = cursor.fetchone()
                if result:
                    status, error, timestamp = result
                    return {
                        "provider": provider,
                        "status": status,
                        "error": error,
                        "timestamp": timestamp,
                    }
                
                return {
                    "provider": provider,
                    "status": "unknown",
                    "error": None,
                    "timestamp": None,
                }
        except Exception as e:
            print(f"Failed to get provider health: {e}")
            return {}
