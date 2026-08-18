"""
聊天会话管理 - 数据库模型和服务
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import json

class ChatSession:
    """聊天会话"""
    def __init__(self, session_id: str, title: str, created_at: str, updated_at: str, 
                 mode: str = "chat", metadata: Optional[Dict] = None):
        self.session_id = session_id
        self.title = title
        self.created_at = created_at
        self.updated_at = updated_at
        self.mode = mode
        self.metadata = metadata or {}

class ChatMessage:
    """聊天消息"""
    def __init__(self, message_id: str, session_id: str, role: str, content: str,
                 created_at: str, metadata: Optional[Dict] = None):
        self.message_id = message_id
        self.session_id = session_id
        self.role = role
        self.content = content
        self.created_at = created_at
        self.metadata = metadata or {}

class ChatHistoryService:
    """聊天历史服务"""
    
    def __init__(self, db_path: str = "db/database.db"):
        self.db_path = Path(db_path)
        self._init_tables()
    
    def _init_tables(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            # 会话表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    mode TEXT DEFAULT 'chat',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            
            # 消息表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
                )
            """)
            
            # 创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON chat_sessions(updated_at DESC)")
            
            conn.commit()
    
    def create_session(self, title: str = "新对话", mode: str = "chat") -> ChatSession:
        """创建新会话"""
        import uuid
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO chat_sessions (session_id, title, mode, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, title, mode, now, now))
            conn.commit()
        
        return ChatSession(session_id, title, now, now, mode)
    
    def get_sessions(self, limit: int = 50, offset: int = 0) -> List[ChatSession]:
        """获取会话列表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM chat_sessions 
                ORDER BY updated_at DESC 
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            sessions = []
            for row in cursor.fetchall():
                metadata = json.loads(row['metadata']) if row['metadata'] else {}
                sessions.append(ChatSession(
                    row['session_id'], row['title'], row['created_at'],
                    row['updated_at'], row['mode'], metadata
                ))
            return sessions
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """获取单个会话"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM chat_sessions WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            if row:
                metadata = json.loads(row['metadata']) if row['metadata'] else {}
                return ChatSession(
                    row['session_id'], row['title'], row['created_at'],
                    row['updated_at'], row['mode'], metadata
                )
        return None
    
    def update_session(self, session_id: str, title: Optional[str] = None,
                      metadata: Optional[Dict] = None):
        """更新会话"""
        updates = []
        params = []
        
        if title:
            updates.append("title = ?")
            params.append(title)
        
        if metadata:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata, ensure_ascii=False))
        
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(session_id)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE chat_sessions SET {', '.join(updates)} WHERE session_id = ?",
                params
            )
            conn.commit()
    
    def delete_session(self, session_id: str):
        """删除会话及其所有消息"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
            conn.commit()
    
    def add_message(self, session_id: str, role: str, content: str,
                   metadata: Optional[Dict] = None) -> ChatMessage:
        """添加消息"""
        import uuid
        message_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO chat_messages (message_id, session_id, role, content, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (message_id, session_id, role, content, now, 
                  json.dumps(metadata, ensure_ascii=False) if metadata else None))
            
            # 更新会话的 updated_at
            conn.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id)
            )
            conn.commit()
        
        return ChatMessage(message_id, session_id, role, content, now, metadata)
    
    def get_messages(self, session_id: str, limit: int = 100) -> List[ChatMessage]:
        """获取会话的所有消息"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM chat_messages 
                WHERE session_id = ? 
                ORDER BY created_at ASC 
                LIMIT ?
            """, (session_id, limit))
            
            messages = []
            for row in cursor.fetchall():
                metadata = json.loads(row['metadata']) if row['metadata'] else {}
                messages.append(ChatMessage(
                    row['message_id'], row['session_id'], row['role'],
                    row['content'], row['created_at'], metadata
                ))
            return messages
    
    def clear_session_messages(self, session_id: str):
        """清空会话的所有消息"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
            conn.commit()
