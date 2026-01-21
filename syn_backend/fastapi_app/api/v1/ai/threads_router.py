"""
AI 聊天线程管理 API
支持多线程对话、消息持久化和上下文管理
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import sqlite3
import json
from datetime import datetime
import uuid
from fastapi_app.core.config import settings

router = APIRouter(prefix="/threads", tags=["ai_threads"])

# 数据库路径
DB_PATH = settings.DATABASE_PATH


def init_threads_tables():
    """初始化线程相关的数据库表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 线程表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_threads (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'chat',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata TEXT,
            message_count INTEGER DEFAULT 0
        )
    """)

    # 如果表已存在但没有 mode 列，添加该列
    cursor.execute("PRAGMA table_info(ai_threads)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'mode' not in columns:
        cursor.execute("ALTER TABLE ai_threads ADD COLUMN mode TEXT NOT NULL DEFAULT 'chat'")
        print("Added 'mode' column to ai_threads table")

    # 消息表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_messages (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tool_calls TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (thread_id) REFERENCES ai_threads(id) ON DELETE CASCADE
        )
    """)

    # 创建索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_thread_id
        ON ai_messages(thread_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_created_at
        ON ai_messages(created_at)
    """)

    conn.commit()
    conn.close()


# 在模块加载时初始化表
init_threads_tables()


class CreateThreadRequest(BaseModel):
    title: Optional[str] = "新对话"
    mode: str = "chat"  # 'chat' or 'agent'
    metadata: Optional[Dict[str, Any]] = None


class UpdateThreadRequest(BaseModel):
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AddMessageRequest(BaseModel):
    role: str  # 'user', 'assistant', 'system', 'tool'
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None


class BatchAddMessagesRequest(BaseModel):
    messages: List[AddMessageRequest]


@router.post("/", summary="创建新线程")
async def create_thread(request: CreateThreadRequest):
    """创建一个新的对话线程"""
    try:
        thread_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO ai_threads (id, title, mode, created_at, updated_at, metadata, message_count)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (
            thread_id,
            request.title,
            request.mode,
            now,
            now,
            json.dumps(request.metadata) if request.metadata else None
        ))

        conn.commit()
        conn.close()

        return {
            "status": "success",
            "data": {
                "thread_id": thread_id,
                "title": request.title,
                "mode": request.mode,
                "created_at": now,
                "updated_at": now,
                "metadata": request.metadata,
                "message_count": 0
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建线程失败: {str(e)}")


@router.get("/", summary="获取线程列表", include_in_schema=True)
@router.get("", include_in_schema=False)
async def get_threads(limit: int = 50, offset: int = 0, mode: Optional[str] = None):
    """获取所有线程列表，按更新时间倒序排列，可按 mode 过滤"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 构建查询条件
        where_clause = ""
        params_count = []
        params_select = []

        if mode:
            where_clause = "WHERE mode = ?"
            params_count = [mode]
            params_select = [mode, limit, offset]
        else:
            params_select = [limit, offset]

        # 获取总数
        cursor.execute(f"SELECT COUNT(*) as total FROM ai_threads {where_clause}", params_count)
        total = cursor.fetchone()["total"]

        # 获取线程列表
        cursor.execute(f"""
            SELECT * FROM ai_threads
            {where_clause}
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """, params_select)

        threads = []
        for row in cursor.fetchall():
            thread = dict(row)
            if thread.get('metadata'):
                try:
                    thread['metadata'] = json.loads(thread['metadata'])
                except:
                    thread['metadata'] = {}
            threads.append(thread)

        conn.close()

        return {
            "status": "success",
            "data": {
                "threads": threads,
                "total": total,
                "limit": limit,
                "offset": offset
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取线程列表失败: {str(e)}")


@router.get("/{thread_id}", summary="获取线程详情")
async def get_thread(thread_id: str):
    """获取特定线程的详细信息"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM ai_threads WHERE id = ?", (thread_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="线程不存在")

        thread = dict(row)
        if thread.get('metadata'):
            try:
                thread['metadata'] = json.loads(thread['metadata'])
            except:
                thread['metadata'] = {}

        conn.close()

        return {
            "status": "success",
            "data": thread
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取线程失败: {str(e)}")


@router.patch("/{thread_id}", summary="更新线程")
async def update_thread(thread_id: str, request: UpdateThreadRequest):
    """更新线程的标题或元数据"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 检查线程是否存在
        cursor.execute("SELECT id FROM ai_threads WHERE id = ?", (thread_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="线程不存在")

        # 构建更新语句
        updates = []
        params = []

        if request.title is not None:
            updates.append("title = ?")
            params.append(request.title)

        if request.metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(request.metadata))

        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            params.append(thread_id)

            sql = f"UPDATE ai_threads SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, params)
            conn.commit()

        conn.close()

        return {
            "status": "success",
            "message": "线程已更新"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新线程失败: {str(e)}")


@router.delete("/{thread_id}", summary="删除线程")
async def delete_thread(thread_id: str):
    """删除线程及其所有消息"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 删除线程（消息会因为外键级联删除）
        cursor.execute("DELETE FROM ai_threads WHERE id = ?", (thread_id,))

        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="线程不存在")

        conn.commit()
        conn.close()

        return {
            "status": "success",
            "message": "线程已删除"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除线程失败: {str(e)}")


@router.post("/{thread_id}/messages", summary="添加消息")
async def add_message(thread_id: str, request: AddMessageRequest):
    """向线程添加一条消息"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 检查线程是否存在
        cursor.execute("SELECT id FROM ai_threads WHERE id = ?", (thread_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="线程不存在")

        message_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        # 插入消息
        cursor.execute("""
            INSERT INTO ai_messages (id, thread_id, role, content, tool_calls, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            message_id,
            thread_id,
            request.role,
            request.content,
            json.dumps(request.tool_calls) if request.tool_calls else None,
            json.dumps(request.metadata) if request.metadata else None,
            now
        ))

        # 更新线程的消息计数和更新时间
        cursor.execute("""
            UPDATE ai_threads
            SET message_count = message_count + 1,
                updated_at = ?
            WHERE id = ?
        """, (now, thread_id))

        conn.commit()
        conn.close()

        return {
            "status": "success",
            "data": {
                "message_id": message_id,
                "thread_id": thread_id,
                "role": request.role,
                "content": request.content,
                "tool_calls": request.tool_calls,
                "metadata": request.metadata,
                "created_at": now
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加消息失败: {str(e)}")


@router.post("/{thread_id}/messages/batch", summary="批量添加消息")
async def batch_add_messages(thread_id: str, request: BatchAddMessagesRequest):
    """向线程批量添加消息"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 检查线程是否存在
        cursor.execute("SELECT id FROM ai_threads WHERE id = ?", (thread_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="线程不存在")

        now = datetime.now().isoformat()
        added_messages = []

        for msg in request.messages:
            message_id = str(uuid.uuid4())

            cursor.execute("""
                INSERT INTO ai_messages (id, thread_id, role, content, tool_calls, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                message_id,
                thread_id,
                msg.role,
                msg.content,
                json.dumps(msg.tool_calls) if msg.tool_calls else None,
                json.dumps(msg.metadata) if msg.metadata else None,
                now
            ))

            added_messages.append({
                "message_id": message_id,
                "role": msg.role,
                "content": msg.content,
                "created_at": now
            })

        # 更新线程的消息计数和更新时间
        cursor.execute("""
            UPDATE ai_threads
            SET message_count = message_count + ?,
                updated_at = ?
            WHERE id = ?
        """, (len(request.messages), now, thread_id))

        conn.commit()
        conn.close()

        return {
            "status": "success",
            "data": {
                "thread_id": thread_id,
                "messages_added": len(added_messages),
                "messages": added_messages
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量添加消息失败: {str(e)}")


@router.get("/{thread_id}/messages", summary="获取线程消息")
async def get_messages(thread_id: str, limit: int = 100, offset: int = 0):
    """获取线程的所有消息"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 检查线程是否存在
        cursor.execute("SELECT id FROM ai_threads WHERE id = ?", (thread_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="线程不存在")

        # 获取消息总数
        cursor.execute("""
            SELECT COUNT(*) as total FROM ai_messages WHERE thread_id = ?
        """, (thread_id,))
        total = cursor.fetchone()["total"]

        # 获取消息列表
        cursor.execute("""
            SELECT * FROM ai_messages
            WHERE thread_id = ?
            ORDER BY created_at ASC
            LIMIT ? OFFSET ?
        """, (thread_id, limit, offset))

        messages = []
        for row in cursor.fetchall():
            message = dict(row)

            # 解析 JSON 字段
            if message.get('tool_calls'):
                try:
                    message['tool_calls'] = json.loads(message['tool_calls'])
                except:
                    message['tool_calls'] = None

            if message.get('metadata'):
                try:
                    message['metadata'] = json.loads(message['metadata'])
                except:
                    message['metadata'] = {}

            messages.append(message)

        conn.close()

        return {
            "status": "success",
            "data": {
                "thread_id": thread_id,
                "messages": messages,
                "total": total,
                "limit": limit,
                "offset": offset
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取消息失败: {str(e)}")


@router.delete("/{thread_id}/messages/{message_id}", summary="删除消息")
async def delete_message(thread_id: str, message_id: str):
    """删除特定消息"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 删除消息
        cursor.execute("""
            DELETE FROM ai_messages
            WHERE id = ? AND thread_id = ?
        """, (message_id, thread_id))

        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="消息不存在")

        # 更新线程的消息计数
        cursor.execute("""
            UPDATE ai_threads
            SET message_count = message_count - 1,
                updated_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), thread_id))

        conn.commit()
        conn.close()

        return {
            "status": "success",
            "message": "消息已删除"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除消息失败: {str(e)}")


@router.delete("/{thread_id}/messages", summary="清空线程消息")
async def clear_messages(thread_id: str):
    """清空线程的所有消息"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 检查线程是否存在
        cursor.execute("SELECT id FROM ai_threads WHERE id = ?", (thread_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="线程不存在")

        # 删除所有消息
        cursor.execute("DELETE FROM ai_messages WHERE thread_id = ?", (thread_id,))
        deleted_count = cursor.rowcount

        # 重置消息计数
        cursor.execute("""
            UPDATE ai_threads
            SET message_count = 0,
                updated_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), thread_id))

        conn.commit()
        conn.close()

        return {
            "status": "success",
            "message": f"已删除 {deleted_count} 条消息"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空消息失败: {str(e)}")
