"""
OpenManus 流式执行 API
支持 SSE (Server-Sent Events) 实时传输 Agent 状态
"""
import asyncio
import json
from typing import AsyncGenerator, Dict, Any, Optional, Union
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ....core.logger import logger


router = APIRouter(tags=["AI Agent Streaming"])


class StreamManusRequest(BaseModel):
    """OpenManus 流式运行请求"""
    goal: str = Field(..., description="自然语言目标描述")
    context: Optional[Union[Dict[str, Any], str, list]] = Field(None, description="额外上下文信息")
    require_confirmation: bool = Field(
        False, description="是否需要用户确认每个工具调用"
    )


async def stream_manus_execution(
    goal: str,
    context: Optional[Union[Dict[str, Any], str, list]] = None,
    require_confirmation: bool = False
) -> AsyncGenerator[str, None]:
    """
    流式执行 OpenManus Agent,实时返回执行状态

    事件类型:
    - plan: Agent 规划的执行计划
    - thinking: Agent 思考过程
    - tool_call: 工具调用请求
    - tool_confirmation_required: 需要用户确认工具调用
    - tool_result: 工具执行结果
    - step_complete: 单步完成
    - final_result: 最终结果
    - error: 错误信息
    """
    try:
        # 导入 OpenManus
        from ....agent.manus_agent import get_manus_agent

        agent = await get_manus_agent()

        # 阶段 1: 发送初始化状态
        yield f"data: {json.dumps({'type': 'init', 'status': 'starting', 'message': '正在初始化 OpenManus Agent...'})}\n\n"
        await asyncio.sleep(0.1)

        # 阶段 2: 分析任务并生成计划
        yield f"data: {json.dumps({'type': 'thinking', 'content': '正在分析任务需求...'})}\n\n"

        # 构建完整的 prompt（兼容非 dict 的 context）
        full_prompt = goal
        if context:
            if isinstance(context, dict):
                context_str = "\n\n## 上下文信息:\n"
                for key, value in context.items():
                    context_str += f"- {key}: {value}\n"
                full_prompt = f"{goal}{context_str}"
            elif isinstance(context, str):
                full_prompt = f"{goal}\n\n## 上下文信息:\n- conversation: {context}\n"
            else:
                full_prompt = f"{goal}\n\n## 上下文信息:\n- context: {context}\n"

        # 为 Agent 添加 system message
        if agent._agent and hasattr(agent._agent, 'update_memory'):
            agent._agent.update_memory("user", full_prompt)

        # 生成执行计划
        yield f"data: {json.dumps({'type': 'thinking', 'content': '正在生成执行计划...'})}\n\n"

        # 模拟生成执行计划(基于可用工具)
        available_tools = []
        if agent._agent and hasattr(agent._agent, 'available_tools'):
            available_tools = [
                {"name": tool.name, "description": tool.description}
                for tool in agent._agent.available_tools.tools
            ]

        plan = {
            "goal": goal,
            "estimated_steps": "动态评估",
            "available_tools": available_tools[:5],  # 只展示前5个工具
            "strategy": "自动选择最优工具完成任务"
        }

        yield f"data: {json.dumps({'type': 'plan', 'plan': plan})}\n\n"
        await asyncio.sleep(0.2)

        # 阶段 3: 如果需要确认,等待用户确认
        if require_confirmation:
            yield f"data: {json.dumps({'type': 'confirmation_required', 'message': '请确认是否执行该计划'})}\n\n"
            # 注意:实际确认逻辑需要前端发送确认请求,这里简化为自动继续

        # 阶段 4: 执行 Agent
        yield f"data: {json.dumps({'type': 'thinking', 'content': '开始执行任务...'})}\n\n"

        # 执行并捕获步骤(通过修改后的 run 方法)
        step_count = 0
        max_dynamic_steps = 30  # 最大步数

        # 使用低级别的 step 循环替代 run()
        if agent._agent:
            from app.agent.base import AgentState

            agent._agent.current_step = 0
            agent._agent.state = AgentState.RUNNING

            while step_count < max_dynamic_steps:
                step_count += 1

                try:
                    yield f"data: {json.dumps({'type': 'thinking', 'content': f'执行第 {step_count} 步...'})}\n\n"

                    # 执行单步
                    step_result = await agent._agent.step()

                    # 检查是否有工具调用
                    if hasattr(agent._agent, 'tool_calls') and agent._agent.tool_calls:
                        last_tool_call = agent._agent.tool_calls[-1]

                        # 发送工具调用事件
                        tool_data = {
                            "type": "tool_call",
                            "step": step_count,
                            "tool_name": last_tool_call.function.name if hasattr(last_tool_call, 'function') else "unknown",
                            "arguments": str(last_tool_call.function.arguments) if hasattr(last_tool_call, 'function') else "{}",
                        }
                        yield f"data: {json.dumps(tool_data)}\n\n"
                        await asyncio.sleep(0.1)

                    # 发送步骤结果
                    yield f"data: {json.dumps({'type': 'step_complete', 'step': step_count, 'result': str(step_result)[:200]})}\n\n"

                    # 检查是否完成
                    if agent._agent.state == AgentState.FINISHED:
                        yield f"data: {json.dumps({'type': 'thinking', 'content': '任务已完成!'})}\n\n"
                        break

                    await asyncio.sleep(0.1)

                except Exception as step_error:
                    logger.error(f"Step {step_count} failed: {step_error}")
                    yield f"data: {json.dumps({'type': 'error', 'step': step_count, 'error': str(step_error)})}\n\n"
                    break

        # 阶段 5: 发送最终结果
        final_result = {
            "success": True,
            "message": f"任务执行完成,共执行 {step_count} 步",
            "steps_executed": step_count
        }

        yield f"data: {json.dumps({'type': 'final_result', 'result': final_result})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        logger.error(f"Stream Manus execution failed: {e}", exc_info=True)
        error_data = {
            "type": "error",
            "error": str(e),
            "message": "执行失败"
        }
        yield f"data: {json.dumps(error_data)}\n\n"


@router.post("/manus-stream")
async def manus_stream(request: StreamManusRequest):
    """
    流式执行 OpenManus Agent

    返回 SSE 流,包含以下事件类型:
    - init: 初始化
    - thinking: 思考过程
    - plan: 执行计划
    - confirmation_required: 需要用户确认
    - tool_call: 工具调用
    - step_complete: 步骤完成
    - final_result: 最终结果
    - error: 错误
    - done: 完成
    """
    return StreamingResponse(
        stream_manus_execution(
            request.goal,
            request.context,
            request.require_confirmation
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲
        }
    )
