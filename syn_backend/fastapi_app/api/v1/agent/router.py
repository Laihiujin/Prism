"""
Agent API路由 - AI驱动的发布系统
"""
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional, Union, AsyncGenerator
from pydantic import BaseModel, Field
import asyncio
import json
import sqlite3
from datetime import datetime

from .models import (
    SaveScriptRequest,
    SaveScriptResponse,
    ExecuteScriptRequest,
    ExecuteScriptResponse,
    SystemContext
)
from .services import agent_service
from .config_routes import router as config_router
from ....core.logger import logger
from ....schemas.common import Response
from ....core.config import settings


router = APIRouter(prefix="/agent", tags=["AI Agent"])

# 包含配置管理路由
router.include_router(config_router, prefix="")

_manus_stream_lock = asyncio.Lock()
_manus_stop_event: Optional[asyncio.Event] = None
_manus_confirm_event: Optional[asyncio.Event] = None
_manus_confirm_approved: Optional[bool] = None




# ============================================
# OpenManus 集成
# ============================================

class ManusRunRequest(BaseModel):
    """OpenManus 运行请求"""
    goal: str = Field(..., description="自然语言目标描述")
    context: Optional[Union[Dict[str, Any], str, list]] = Field(None, description="额外上下文信息")


class ManusRunResponse(BaseModel):
    """OpenManus 运行响应"""
    success: bool
    result: str
    steps: list = Field(default_factory=list)
    error: Optional[str] = None


@router.post("/manus-run", response_model=Response[ManusRunResponse])
async def manus_run(request: ManusRunRequest):
    """
    使用 OpenManus Agent 执行复杂任务

    OpenManus 会自动调用工具完成任务：
    - save_script: 保存脚本
    - execute_script: 执行脚本
    - list_accounts: 列出账号
    - list_assets: 列出素材
    - get_system_context: 获取系统上下文

    Args:
        request: 包含目标和上下文的请求

    Returns:
        执行结果
    """
    try:
        logger.info(f"[ManusRun] 收到请求，目标: {request.goal}")

        # 导入 OpenManus agent
        from ....agent.manus_agent import run_goal

        context: Optional[Dict[str, Any]]
        if request.context is None:
            context = None
        elif isinstance(request.context, dict):
            context = request.context
        elif isinstance(request.context, str):
            # 前端可能直接传入对话历史字符串；这里做兼容转换
            context = {"conversation": request.context}
        else:
            # 兜底：允许列表等其它结构，包装进 dict 供 agent 拼接 prompt
            context = {"context": request.context}

        # 运行 OpenManus agent
        result = await run_goal(request.goal, context)

        logger.info(f"[ManusRun] 执行完成，成功: {result.get('success')}")

        return Response(
            success=True,
            data=ManusRunResponse(**result)
        )

    except Exception as e:
        logger.error(f"[ManusRun] 执行失败: {e}", exc_info=True)
        msg = str(e)
        if "BrowserConfig" in msg and "browser_use" in msg:
            msg = (
                "OpenManus 执行失败：browser_use 版本不兼容（缺少 BrowserConfig）。"
                "请升级/降级 browser_use 到与 OpenManus-worker 兼容的版本，"
                "或暂时禁用 browser_use 工具后重试。原始错误: "
                + str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=msg,
        )


# ============================================
# OpenManus 流式执行
# ============================================

class StreamManusRequest(BaseModel):
    """OpenManus 流式运行请求"""
    goal: str = Field(..., description="自然语言目标描述")
    # 前端/旧实现可能传字符串或数组，这里宽松兼容避免 422
    context: Optional[Union[Dict[str, Any], str, list]] = Field(None, description="额外上下文信息")
    thread_id: Optional[str] = Field(None, description="AI 线程ID（用于多轮上下文与隔离）")
    require_confirmation: bool = Field(False, description="是否需要用户确认每个工具调用")


class ManusConfirmRequest(BaseModel):
    """OpenManus 工具调用确认"""
    approved: bool = Field(..., description="用户是否同意")


async def stream_manus_execution(
    goal: str,
    context: Optional[Union[Dict[str, Any], str, list]] = None,
    require_confirmation: bool = False,
    thread_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """流式执行 OpenManus Agent（SSE）"""
    global _manus_stop_event, _manus_confirm_event, _manus_confirm_approved
    try:
        # 创建停止事件
        _manus_stop_event = asyncio.Event()
        _manus_confirm_event = None
        _manus_confirm_approved = None
        from ....agent.manus_agent import get_manus_agent

        def _sse(data: Dict[str, Any]) -> str:
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        def _normalize_context(raw: Optional[Union[Dict[str, Any], str, list]]) -> Optional[Dict[str, Any]]:
            if raw is None:
                return None
            if isinstance(raw, dict):
                return raw
            if isinstance(raw, str):
                return {"conversation": raw}
            return {"context": raw}

        normalized_context = _normalize_context(context)

        async with _manus_stream_lock:
            agent_wrapper = await get_manus_agent()

            manus = getattr(agent_wrapper, "_agent", None)
            if manus is None:
                raise RuntimeError("OpenManus Agent 未初始化")

            # 防止不同请求串台：清空内存并重置状态
            from app.schema import AgentState, Memory, Message as OMMessage

            manus.memory = Memory()
            manus.current_step = 0
            manus.state = AgentState.IDLE

            yield _sse({"type": "init", "status": "starting", "message": "正在初始化 OpenManus Agent..."})

            # 发计划（给前端渲染工具列表/策略）
            available_tools = []
            try:
                if hasattr(manus, "available_tools") and hasattr(manus.available_tools, "tools"):
                    available_tools = [
                        {"name": t.name, "description": getattr(t, "description", "")}
                        for t in manus.available_tools.tools
                    ]
            except Exception:
                available_tools = []

            yield _sse({
                "type": "plan",
                "plan": {
                    "goal": goal,
                    "estimated_steps": "动态",
                    "available_tools": available_tools[:10],
                    "strategy": "基于工具调用逐步完成任务"
                }
            })

            # 多轮：如果传了 thread_id，则优先从 ai_messages 还原上下文（避免多线程串台）
            if thread_id:
                try:
                    conn = sqlite3.connect(settings.DATABASE_PATH)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT role, content
                        FROM ai_messages
                        WHERE thread_id = ?
                        ORDER BY created_at DESC
                        LIMIT 60
                        """,
                        (thread_id,),
                    )
                    rows = list(reversed(cursor.fetchall()))
                    conn.close()

                    history_msgs = []
                    for row in rows:
                        role = (row["role"] or "").lower()
                        content = row["content"] or ""
                        if not content:
                            continue
                        if role == "user":
                            history_msgs.append(OMMessage.user_message(content))
                        elif role == "assistant":
                            history_msgs.append(OMMessage.assistant_message(content))
                        elif role == "system":
                            history_msgs.append(OMMessage.system_message(content))
                        else:
                            # tool/unknown：避免注入过多噪声，先忽略
                            continue

                    if history_msgs:
                        manus.memory.add_messages(history_msgs)
                except Exception as e:
                    logger.warning(f"[ManusStream] 加载线程历史失败: thread_id={thread_id} err={e}")

            # 兜底：保证本次 goal 在 memory 里（若前端未提前写入线程库）
            last_user = ""
            try:
                last_user = next(
                    (
                        m.content
                        for m in reversed(getattr(manus.memory, "messages", []))
                        if getattr(m, "role", "") == "user" and getattr(m, "content", None)
                    ),
                    "",
                ).strip()
            except Exception:
                last_user = ""

            if goal.strip() and goal.strip() != last_user:
                full_prompt = goal
                # 如果 context 是 dict 且不是纯对话文本，则追加为结构化上下文
                if normalized_context and not ("conversation" in normalized_context and len(normalized_context) == 1):
                    context_str = "\n\n## 上下文信息:\n"
                    for key, value in normalized_context.items():
                        context_str += f"- {key}: {value}\n"
                    full_prompt = f"{goal}{context_str}"
                manus.update_memory("user", full_prompt)
            manus.state = AgentState.RUNNING

            yield _sse({"type": "thinking", "content": "开始执行任务..."})

            stream_step = 0
            max_steps = int(getattr(manus, "max_steps", 30) or 30)
            last_emitted_thought = ""
            task_confirmed = False  # 标记任务是否已确认
            consecutive_no_tool_steps = 0

            while manus.current_step < max_steps and manus.state != AgentState.FINISHED:
                # Stop check
                if _manus_stop_event and _manus_stop_event.is_set():
                    yield _sse({"type": "error", "error": "Task stopped by user"})
                    yield _sse({"type": "done"})
                    break

                manus.current_step += 1

                should_act = await manus.think()
                # Stream assistant thought to UI
                try:
                    latest_assistant = next(
                        (
                            m.content
                            for m in reversed(getattr(manus.memory, "messages", []))
                            if getattr(m, "role", "") == "assistant" and getattr(m, "content", None)
                        ),
                        "",
                    )
                    latest_assistant = (latest_assistant or "").strip()
                    if latest_assistant and latest_assistant != last_emitted_thought:
                        yield _sse({"type": "thinking", "content": latest_assistant[:4000]})
                        last_emitted_thought = latest_assistant
                except Exception:
                    pass
                tool_calls = list(getattr(manus, "tool_calls", []) or [])

                if tool_calls:
                    consecutive_no_tool_steps = 0
                else:
                    consecutive_no_tool_steps += 1
                    if consecutive_no_tool_steps == 1:
                        try:
                            manus.memory.add_message(
                                OMMessage.system_message(
                                    "连续未生成工具调用，请主动结束（terminate）以避免空转。"
                                )
                            )
                        except Exception:
                            pass
                        yield _sse({"type": "thinking", "content": "未检测到工具调用，准备结束任务..."})
                        continue
                    if consecutive_no_tool_steps >= 2:
                        yield _sse({"type": "error", "error": "连续两步未生成工具调用，任务已停止。"})
                        yield _sse({"type": "done"})
                        break


                # 仅在第一次有工具调用时请求确认（如果需要）
                # 用户确认后，后续所有步骤自动执行
                if tool_calls and require_confirmation and not task_confirmed:
                    # Build task summary
                    task_summary = {
                        "goal": goal,
                        "total_steps": "动态（根据执行情况可能增加）",
                        "tools": []
                    }

                    for tc in tool_calls:
                        name = getattr(getattr(tc, "function", None), "name", None) or "unknown"
                        args_raw = getattr(getattr(tc, "function", None), "arguments", None) or "{}"
                        try:
                            args_val: Any = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                        except Exception:
                            args_val = args_raw

                        task_summary["tools"].append({
                            "name": name,
                            "arguments": args_val
                        })

                    # Send confirmation request
                    yield _sse({
                        "type": "confirmation_required",
                        "message": "已生成执行计划，请确认后将自动执行所有步骤",
                        "task_summary": task_summary
                    })

                    _manus_confirm_event = asyncio.Event()
                    _manus_confirm_approved = None

                    wait_tasks = [asyncio.create_task(_manus_confirm_event.wait())]
                    if _manus_stop_event:
                        wait_tasks.append(asyncio.create_task(_manus_stop_event.wait()))

                    done, pending = await asyncio.wait(
                        wait_tasks,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in pending:
                        task.cancel()

                    if _manus_stop_event and _manus_stop_event.is_set():
                        yield _sse({"type": "error", "error": "Task stopped by user"})
                        yield _sse({"type": "done"})
                        break

                    approved = bool(_manus_confirm_approved)
                    yield _sse({"type": "confirmation_received", "approved": approved})
                    if not approved:
                        yield _sse({"type": "error", "error": "Task rejected by user"})
                        yield _sse({"type": "done"})
                        break

                    # 标记任务已确认，后续所有步骤自动执行，不再请求确认
                    task_confirmed = True
                    logger.info(f"[ManusStream] 任务已确认，将自动执行所有后续步骤")

                if tool_calls:
                    step_ids: list[int] = []
                    tool_names: list[str] = []
                    tool_args: list[Any] = []

                    for tc in tool_calls:
                        stream_step += 1
                        step_ids.append(stream_step)
                        name = getattr(getattr(tc, "function", None), "name", None) or "unknown"
                        args_raw = getattr(getattr(tc, "function", None), "arguments", None) or "{}"
                        try:
                            args_val: Any = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                        except Exception:
                            args_val = args_raw

                        tool_names.append(name)
                        tool_args.append(args_val)

                        yield _sse({
                            "type": "tool_call",
                            "step": stream_step,
                            "tool_name": name,
                            "arguments": args_val,
                        })

                    act_result = await manus.act()
                    parts = [p for p in (act_result or "").split("\n\n") if p.strip()]

                    for idx, sid in enumerate(step_ids):
                        result_text = parts[idx] if idx < len(parts) else (act_result or "")
                        yield _sse({
                            "type": "step_complete",
                            "step": sid,
                            "tool_name": tool_names[idx] if idx < len(tool_names) else None,
                            "result": result_text
                        })

                    continue

            # 汇总最终结果
            try:
                last_assistant = next(
                    (
                        m.content
                        for m in reversed(getattr(manus.memory, "messages", []))
                        if getattr(m, "role", "") == "assistant" and getattr(m, "content", None)
                    ),
                    "",
                )
            except Exception:
                last_assistant = ""

            steps = []
            try:
                for msg in getattr(manus.memory, "messages", []):
                    tool_calls = getattr(msg, "tool_calls", None)
                    if not tool_calls:
                        continue
                    for tc in tool_calls:
                        steps.append({
                            "tool": getattr(getattr(tc, "function", None), "name", None),
                            "arguments": getattr(getattr(tc, "function", None), "arguments", None),
                        })
            except Exception:
                steps = []

            final_payload = {
                "success": True,
                "result": last_assistant or "执行完成",
                "steps": steps,
                "error": None
            }

            yield _sse({"type": "final_result", "result": final_payload})

            # 保存任务结果到数据库（避免刷新后丢失）
            if thread_id:
                try:
                    conn = sqlite3.connect(settings.DATABASE_PATH)
                    cursor = conn.cursor()

                    # 保存 assistant 的最终回复
                    if last_assistant:
                        cursor.execute(
                            """
                            INSERT INTO ai_messages (thread_id, role, content, created_at)
                            VALUES (?, ?, ?, ?)
                            """,
                            (thread_id, "assistant", last_assistant, datetime.now().isoformat())
                        )

                    # 保存工具调用步骤（以 JSON 格式）
                    if steps:
                        steps_summary = f"执行了 {len(steps)} 个工具调用:\n" + "\n".join(
                            f"- {s.get('tool', 'unknown')}" for s in steps
                        )
                        cursor.execute(
                            """
                            INSERT INTO ai_messages (thread_id, role, content, created_at)
                            VALUES (?, ?, ?, ?)
                            """,
                            (thread_id, "tool", json.dumps(steps, ensure_ascii=False), datetime.now().isoformat())
                        )

                    conn.commit()
                    conn.close()
                    logger.info(f"已保存 OpenManus 任务结果到数据库: thread_id={thread_id}")
                except Exception as e:
                    logger.warning(f"保存 OpenManus 任务记录失败: {e}")

            yield _sse({"type": "done"})

    except Exception as e:
        logger.error(f"Stream failed: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"
    finally:
        # 清理停止事件
        _manus_stop_event = None
        _manus_confirm_event = None
        _manus_confirm_approved = None


@router.post("/manus-stream")
async def manus_stream(request: StreamManusRequest):
    """
    流式执行 OpenManus Agent

    返回 SSE 流式事件
    """
    return StreamingResponse(
        stream_manus_execution(request.goal, request.context, request.require_confirmation, request.thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/manus-stop")
async def manus_stop():
    """
    强制停止正在运行的 OpenManus 任务
    """
    global _manus_stop_event
    try:
        if _manus_stop_event:
            _manus_stop_event.set()
            logger.info("已触发 OpenManus 任务停止信号")
            return Response(
                success=True,
                data={"message": "停止信号已发送"}
            )
        else:
            return Response(
                success=False,
                data={"message": "当前没有正在运行的任务"}
            )
    except Exception as e:
        logger.error(f"停止 Manus 任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/manus-confirm")
async def manus_confirm(request: ManusConfirmRequest):
    """
    用户确认 OpenManus 工具调用
    """
    global _manus_confirm_event, _manus_confirm_approved
    try:
        if not _manus_confirm_event:
            return Response(
                success=False,
                data={"message": "当前没有待确认的任务"}
            )
        _manus_confirm_approved = bool(request.approved)
        _manus_confirm_event.set()
        return Response(
            success=True,
            data={"approved": _manus_confirm_approved}
        )
    except Exception as e:
        logger.error(f"Manus 确认失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# 原有 Agent 路由
# ============================================

@router.post("/save-script", response_model=Response[SaveScriptResponse])
async def save_script(request: SaveScriptRequest):
    """
    保存AI生成的脚本

    - 支持JSON和Python脚本
    - 自动生成script_id
    - 落盘到storage/scripts目录
    - 记录到数据库

    Args:
        request: 脚本内容和元数据

    Returns:
        {script_id, path}
    """
    try:
        result = await agent_service.save_script(request)
        return Response(
            success=True,
            data=SaveScriptResponse(
                status="success",
                script_id=result['script_id'],
                path=result['path']
            )
        )
    except Exception as e:
        logger.error(f"Save script failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/execute-script", response_model=Response[ExecuteScriptResponse])
async def execute_script(request: ExecuteScriptRequest):
    """
    执行脚本

    - execute模式: 真实创建任务并执行
    - dry-run模式: 仅验证计划不执行

    Args:
        request: 脚本ID和执行选项

    Returns:
        {task_batch_id, tasks_created, estimated_time}
    """
    try:
        result = await agent_service.execute_script(
            script_id=request.script_id,
            mode=request.mode,
            options=request.options.dict() if request.options else {}
        )

        return Response(
            success=True,
            data=ExecuteScriptResponse(
                status="accepted",
                task_batch_id=result['task_batch_id'],
                tasks_created=result['tasks_created'],
                estimated_time=result['estimated_time']
            )
        )
    except ValueError as e:
        logger.error(f"Execute script failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Execute script failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/context", response_model=Response[SystemContext])
async def get_system_context():
    """
    获取系统上下文

    供AI使用,包含:
    - 所有可用账号信息
    - 素材库视频列表
    - 已发布历史

    Returns:
        {accounts: [...], videos: [...]}
    """
    try:
        context = await agent_service.get_system_context()
        return Response(
            success=True,
            data=context
        )
    except Exception as e:
        logger.error(f"Get context failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/scripts")
async def list_scripts(skip: int = 0, limit: int = 20):
    """
    获取脚本列表

    Args:
        skip: 跳过数量
        limit: 限制数量

    Returns:
        脚本列表
    """
    try:
        import sqlite3
        from pathlib import Path

        db_path = Path(agent_service.db_path)

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT script_id, filename, script_type, plan_name,
                       description, generated_by, created_at, status
                FROM scripts
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, skip))

            scripts = [dict(row) for row in cursor.fetchall()]

            # 获取总数
            count_cursor = conn.execute("SELECT COUNT(*) FROM scripts")
            total = count_cursor.fetchone()[0]

        return Response(
            success=True,
            data={
                "total": total,
                "items": scripts
            }
        )
    except Exception as e:
        logger.error(f"List scripts failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/scripts/{script_id}")
async def get_script(script_id: str):
    """
    获取脚本详情

    Args:
        script_id: 脚本ID

    Returns:
        脚本详细信息
    """
    try:
        import sqlite3
        from pathlib import Path

        db_path = Path(agent_service.db_path)

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM scripts WHERE script_id = ?",
                (script_id,)
            )
            script = cursor.fetchone()

            if not script:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Script not found: {script_id}"
                )

            return Response(
                success=True,
                data=dict(script)
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get script failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/executions")
async def list_executions(skip: int = 0, limit: int = 20):
    """
    获取执行历史

    Args:
        skip: 跳过数量
        limit: 限制数量

    Returns:
        执行历史列表
    """
    try:
        import sqlite3
        from pathlib import Path

        db_path = Path(agent_service.db_path)

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT e.*, s.filename, s.plan_name
                FROM script_executions e
                LEFT JOIN scripts s ON e.script_id = s.script_id
                ORDER BY e.started_at DESC
                LIMIT ? OFFSET ?
            """, (limit, skip))

            executions = [dict(row) for row in cursor.fetchall()]

            # 获取总数
            count_cursor = conn.execute("SELECT COUNT(*) FROM script_executions")
            total = count_cursor.fetchone()[0]

        return Response(
            success=True,
            data={
                "total": total,
                "items": executions
            }
        )
    except Exception as e:
        logger.error(f"List executions failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
