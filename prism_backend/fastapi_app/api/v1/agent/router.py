"""
Agent API routes.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional, Union, AsyncGenerator
from pydantic import BaseModel, Field
import asyncio
import json

from .models import (
    SaveScriptRequest,
    SaveScriptResponse,
    ExecuteScriptRequest,
    ExecuteScriptResponse,
    SystemContext,
)
from .services import agent_service
from .config_routes import router as config_router
from ....core.logger import logger
from ....schemas.common import Response


router = APIRouter(prefix="/agent", tags=["AI Agent"])
router.include_router(config_router, prefix="")

_agent_stream_lock = asyncio.Lock()
_agent_stop_event: Optional[asyncio.Event] = None
_agent_confirm_event: Optional[asyncio.Event] = None
_agent_confirm_approved: Optional[bool] = None


class AgentRunRequest(BaseModel):
    goal: str = Field(..., description="自然语言目标描述")
    context: Optional[Union[Dict[str, Any], str, list]] = Field(None, description="额外上下文信息")


class AgentRunResponse(BaseModel):
    success: bool
    result: str
    steps: list = Field(default_factory=list)
    error: Optional[str] = None


class StreamAgentRequest(BaseModel):
    goal: str = Field(..., description="自然语言目标描述")
    context: Optional[Union[Dict[str, Any], str, list]] = Field(None, description="额外上下文信息")
    thread_id: Optional[str] = Field(None, description="线程 ID，当前仅用于接口兼容")
    require_confirmation: bool = Field(False, description="是否需要用户确认")


class AgentConfirmRequest(BaseModel):
    approved: bool = Field(..., description="用户是否同意执行")


def _normalize_agent_context(
    raw: Optional[Union[Dict[str, Any], str, list]]
) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return {"conversation": raw}
    return {"context": raw}


def _format_sse(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _run_agent_once(request: AgentRunRequest):
    from ....agent.hermes_agent import run_hermes_goal

    try:
        result = await run_hermes_goal(
            goal=request.goal,
            context=_normalize_agent_context(request.context),
        )
        return Response(success=True, data=AgentRunResponse(**result))
    except Exception as e:
        logger.error(f"[HermesRun] failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/hermes-run", response_model=Response[AgentRunResponse])
async def hermes_run(request: AgentRunRequest):
    return await _run_agent_once(request)


@router.post("/openclaw-run", response_model=Response[AgentRunResponse])
async def openclaw_run(request: AgentRunRequest):
    return await hermes_run(request)


async def hermes_stream_execution(
    goal: str,
    context: Optional[Union[Dict[str, Any], str, list]] = None,
    require_confirmation: bool = False,
    thread_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    del thread_id
    global _agent_stop_event, _agent_confirm_event, _agent_confirm_approved

    from ....agent.hermes_agent import run_hermes_goal

    _agent_stop_event = asyncio.Event()
    _agent_confirm_event = None
    _agent_confirm_approved = None

    async def on_event(event: Dict[str, Any], queue: "asyncio.Queue[Optional[Dict[str, Any]]]") -> None:
        mapped = event
        if event["type"] == "assistant_message":
            mapped = {"type": "thinking", "content": event.get("content", "")}
        elif event["type"] == "tool_call":
            mapped = {
                "type": "tool_call",
                "tool_name": event.get("tool_name"),
                "arguments": event.get("arguments"),
            }
        elif event["type"] == "tool_result":
            mapped = {
                "type": "step_complete",
                "tool_name": event.get("tool_name"),
                "result": event.get("result"),
            }
        await queue.put(mapped)

    try:
        async with _agent_stream_lock:
            normalized_context = _normalize_agent_context(context)
            queue: "asyncio.Queue[Optional[Dict[str, Any]]]" = asyncio.Queue()
            step_counter = 0

            yield _format_sse(
                {
                    "type": "init",
                    "status": "starting",
                    "message": "Hermes Agent 正在准备运行环境。",
                }
            )
            yield _format_sse(
                {
                    "type": "plan",
                    "plan": {
                        "goal": goal,
                        "context": normalized_context or {},
                        "mode": "hermes-agent",
                    },
                }
            )

            if require_confirmation:
                _agent_confirm_event = asyncio.Event()
                yield _format_sse(
                    {
                        "type": "confirmation_required",
                        "message": "请确认是否执行这个 Hermes Agent 任务。",
                        "task_summary": {"goal": goal, "context": normalized_context or {}},
                    }
                )

                wait_tasks = [asyncio.create_task(_agent_confirm_event.wait())]
                if _agent_stop_event:
                    wait_tasks.append(asyncio.create_task(_agent_stop_event.wait()))
                done, pending = await asyncio.wait(wait_tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                for task in done:
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

                if _agent_stop_event and _agent_stop_event.is_set():
                    yield _format_sse({"type": "error", "error": "Task stopped by user"})
                    yield _format_sse({"type": "done"})
                    return

                approved = bool(_agent_confirm_approved)
                yield _format_sse({"type": "confirmation_received", "approved": approved})
                if not approved:
                    yield _format_sse({"type": "error", "error": "Task rejected by user"})
                    yield _format_sse({"type": "done"})
                    return

            async def worker() -> None:
                try:
                    result = await run_hermes_goal(
                        goal=goal,
                        context=normalized_context,
                        event_handler=lambda event: on_event(event, queue),
                        should_stop=lambda: bool(_agent_stop_event and _agent_stop_event.is_set()),
                    )
                    await queue.put({"type": "final_result", "result": result})
                except Exception as exc:
                    await queue.put({"type": "error", "error": str(exc)})
                finally:
                    await queue.put({"type": "done"})
                    await queue.put(None)

            task = asyncio.create_task(worker())

            while True:
                event = await queue.get()
                if event is None:
                    break
                if event.get("type") == "tool_call":
                    step_counter += 1
                    event["step"] = step_counter
                elif event.get("type") == "step_complete":
                    event["step"] = step_counter
                yield _format_sse(event)
                if event.get("type") == "done":
                    break

            await task
    except Exception as e:
        logger.error(f"[HermesStream] failed: {e}", exc_info=True)
        yield _format_sse({"type": "error", "error": str(e)})
    finally:
        _agent_stop_event = None
        _agent_confirm_event = None
        _agent_confirm_approved = None


@router.post("/hermes-stream")
async def hermes_stream(request: StreamAgentRequest):
    return StreamingResponse(
        hermes_stream_execution(
            request.goal,
            request.context,
            request.require_confirmation,
            request.thread_id,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/openclaw-stream")
async def openclaw_stream(request: StreamAgentRequest):
    return await hermes_stream(request)


@router.post("/hermes-stop")
async def hermes_stop():
    global _agent_stop_event
    if _agent_stop_event:
        _agent_stop_event.set()
        return Response(success=True, data={"message": "已发送 Hermes 停止信号。"})
    return Response(success=False, data={"message": "当前没有正在运行的 Hermes 任务。"})


@router.post("/openclaw-stop")
async def openclaw_stop():
    return await hermes_stop()


@router.post("/hermes-confirm")
async def hermes_confirm(request: AgentConfirmRequest):
    global _agent_confirm_event, _agent_confirm_approved
    if not _agent_confirm_event:
        return Response(success=False, data={"message": "当前没有待确认的 Hermes 任务。"})
    _agent_confirm_approved = bool(request.approved)
    _agent_confirm_event.set()
    return Response(success=True, data={"approved": _agent_confirm_approved})


@router.post("/openclaw-confirm")
async def openclaw_confirm(request: AgentConfirmRequest):
    return await hermes_confirm(request)


@router.post("/save-script", response_model=Response[SaveScriptResponse])
async def save_script(request: SaveScriptRequest):
    """
    淇濆瓨AI鐢熸垚鐨勮剼鏈?

    - 鏀寔JSON鍜孭ython鑴氭湰
    - 鑷姩鐢熸垚script_id
    - 钀界洏鍒皊torage/scripts鐩綍
    - 璁板綍鍒版暟鎹簱

    Args:
        request: 鑴氭湰鍐呭鍜屽厓鏁版嵁

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
    鎵ц鑴氭湰

    - execute妯″紡: 鐪熷疄鍒涘缓浠诲姟骞舵墽琛?
    - dry-run妯″紡: 浠呴獙璇佽鍒掍笉鎵ц

    Args:
        request: 鑴氭湰ID鍜屾墽琛岄€夐」

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
    鑾峰彇绯荤粺涓婁笅鏂?

    渚汚I浣跨敤,鍖呭惈:
    - 鎵€鏈夊彲鐢ㄨ处鍙蜂俊鎭?
    - 绱犳潗搴撹棰戝垪琛?
    - 宸插彂甯冨巻鍙?

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
    鑾峰彇鑴氭湰鍒楄〃

    Args:
        skip: 璺宠繃鏁伴噺
        limit: 闄愬埗鏁伴噺

    Returns:
        鑴氭湰鍒楄〃
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

            # 鑾峰彇鎬绘暟
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
    鑾峰彇鑴氭湰璇︽儏

    Args:
        script_id: 鑴氭湰ID

    Returns:
        鑴氭湰璇︾粏淇℃伅
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
    鑾峰彇鎵ц鍘嗗彶

    Args:
        skip: 璺宠繃鏁伴噺
        limit: 闄愬埗鏁伴噺

    Returns:
        鎵ц鍘嗗彶鍒楄〃
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

            # 鑾峰彇鎬绘暟
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
