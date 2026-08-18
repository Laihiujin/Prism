"""
人工任务管理服务
处理需要人工干预的发布任务（如短信验证）
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from fastapi_app.core.logger import logger
from fastapi_app.core.timezone_utils import now_beijing_iso

DB_PATH = Path(__file__).parent.parent.parent / "db" / "task_queue.db"

class ManualTaskManager:
    """人工任务管理器"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self._ensure_table()
    def _ensure_table(self) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS manual_tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT UNIQUE NOT NULL,
                        task_type TEXT NOT NULL,
                        platform TEXT NOT NULL,
                        account_id TEXT NOT NULL,
                        account_name TEXT,
                        material_id TEXT,
                        material_name TEXT,
                        title TEXT,
                        description TEXT,
                        reason TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        retry_count INTEGER DEFAULT 0,
                        max_retries INTEGER DEFAULT 3,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_error TEXT,
                        metadata TEXT
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_manual_tasks_status
                    ON manual_tasks(status)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_manual_tasks_platform
                    ON manual_tasks(platform)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_manual_tasks_account
                    ON manual_tasks(account_id)
                """)
                conn.commit()
        except Exception as exc:
            logger.error(f"Failed to ensure manual_tasks table: {exc}")

    
    def _get_conn(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)
    
    def add_task(
        self,
        task_id: str,
        task_type: str,
        platform: str,
        account_id: str,
        reason: str,
        account_name: Optional[str] = None,
        material_id: Optional[str] = None,
        material_name: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        添加人工任务
        
        Args:
            task_id: 任务ID
            task_type: 任务类型 (publish, verification, etc.)
            platform: 平台
            account_id: 账号ID
            reason: 需要人工处理的原因
            account_name: 账号名称
            material_id: 素材ID
            material_name: 素材名称
            title: 标题
            description: 描述
            metadata: 额外元数据
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            metadata_json = json.dumps(metadata) if metadata else None
            
            cursor.execute("""
                INSERT OR REPLACE INTO manual_tasks (
                    task_id, task_type, platform, account_id, account_name,
                    material_id, material_name, title, description, reason,
                    status, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            """, (
                task_id, task_type, platform, account_id, account_name,
                material_id, material_name, title, description, reason,
                metadata_json, now_beijing_iso(), now_beijing_iso()
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ 人工任务已添加: {task_id} - {reason}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加人工任务失败: {e}")
            return False
    
    def get_pending_tasks(
        self,
        platform: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取待处理的人工任务"""
        try:
            conn = self._get_conn()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM manual_tasks 
                WHERE status = 'pending'
            """
            params = []
            
            if platform:
                query += " AND platform = ?"
                params.append(platform)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            tasks = []
            for row in rows:
                task = dict(row)
                if task.get('metadata'):
                    task['metadata'] = json.loads(task['metadata'])
                tasks.append(task)
            
            return tasks
            
        except Exception as e:
            logger.error(f"❌ 获取人工任务失败: {e}")
            return []
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取单个任务详情"""
        try:
            conn = self._get_conn()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM manual_tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                task = dict(row)
                if task.get('metadata'):
                    task['metadata'] = json.loads(task['metadata'])
                return task
            return None
            
        except Exception as e:
            logger.error(f"❌ 获取任务详情失败: {e}")
            return None
    
    def update_status(
        self,
        task_id: str,
        status: str,
        error: Optional[str] = None
    ) -> bool:
        """更新任务状态"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE manual_tasks
                SET status = ?, last_error = ?, updated_at = ?
                WHERE task_id = ?
            """, (status, error, now_beijing_iso(), task_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ 任务状态已更新: {task_id} -> {status}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 更新任务状态失败: {e}")
            return False
    
    def retry_task(self, task_id: str) -> bool:
        """重试任务"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # 检查重试次数
            cursor.execute("""
                SELECT retry_count, max_retries FROM manual_tasks 
                WHERE task_id = ?
            """, (task_id,))
            row = cursor.fetchone()
            
            if not row:
                logger.error(f"❌ 任务不存在: {task_id}")
                return False
            
            retry_count, max_retries = row
            
            if retry_count >= max_retries:
                logger.warning(f"⚠️ 任务已达最大重试次数: {task_id}")
                cursor.execute("""
                    UPDATE manual_tasks
                    SET status = 'failed', updated_at = ?
                    WHERE task_id = ?
                """, (now_beijing_iso(), task_id))
                conn.commit()
                conn.close()
                return False
            
            # 增加重试次数并重置为pending
            cursor.execute("""
                UPDATE manual_tasks
                SET status = 'pending',
                    retry_count = retry_count + 1,
                    updated_at = ?
                WHERE task_id = ?
            """, (now_beijing_iso(), task_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ 任务已重置为待处理: {task_id} (重试 {retry_count + 1}/{max_retries})")
            return True
            
        except Exception as e:
            logger.error(f"❌ 重试任务失败: {e}")
            return False
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM manual_tasks WHERE task_id = ?", (task_id,))
            conn.commit()
            conn.close()
            
            logger.info(f"✅ 任务已删除: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 删除任务失败: {e}")
            return False
    
    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM manual_tasks
            """)
            
            row = cursor.fetchone()
            conn.close()
            
            return {
                "total": row[0] or 0,
                "pending": row[1] or 0,
                "processing": row[2] or 0,
                "completed": row[3] or 0,
                "failed": row[4] or 0
            }
            
        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {e}")
            return {
                "total": 0,
                "pending": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0
            }

# 全局实例
manual_task_manager = ManualTaskManager()
