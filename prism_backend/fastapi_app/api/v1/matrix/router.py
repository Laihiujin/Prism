"""
矩阵发布 API 路由
提供任务生成、调度、监控接口
"""
import asyncio
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional

from fastapi_app.models.matrix_task import (
    GenerateTasksRequest,
    ReportResultRequest,
    TaskResponse,
    TaskListResponse,
    MatrixTask
)
from fastapi_app.services.matrix_scheduler import get_matrix_scheduler, MatrixScheduler
from fastapi_app.schemas.common import Response, StatusResponse
from fastapi_app.core.logger import logger
from fastapi_app.api.v1.publish.services import get_publish_service
from fastapi_app.db.session import main_db_pool


router = APIRouter(prefix="/matrix", tags=["矩阵发布调度"])


def get_scheduler() -> MatrixScheduler:
    """依赖注入：获取调度器"""
    return get_matrix_scheduler()


def _dispatch_matrix_task_sync(service, task: MatrixTask) -> dict:
    """同步提交单个矩阵任务到发布队列（用于线程执行）"""
    platform_code_map = {
        "xiaohongshu": 1,
        "channels": 2,
        "douyin": 3,
        "kuaishou": 4,
        "bilibili": 5
    }
    platform_code = platform_code_map.get(task.platform)
    if not platform_code:
        raise ValueError(f"不支持的平台类型: {task.platform}")

    try:
        file_id = int(task.material_id)
    except Exception as exc:
        raise ValueError(f"素材ID非数字: {task.material_id}") from exc

    publish_kwargs = {
        "file_ids": [file_id],
        "accounts": [task.account_id],
        "platform": platform_code,
        "title": task.title or "",
        "description": task.description or "",
        "topics": task.topics or [],
        "cover_path": task.cover_path or "",
        "interval_control_enabled": False,
        "interval_mode": None,
        "interval_seconds": 0,
        "random_offset": 0,
    }

    if task.scheduled_time:
        publish_kwargs["scheduled_time"] = task.scheduled_time.strftime("%Y-%m-%d %H:%M")

    with main_db_pool.get_connection() as db:
        result = asyncio.run(service.publish_batch(db=db, **publish_kwargs))

    failed_count = result.get("failed_count", 0)
    success_count = result.get("success_count", 0)
    publish_task_id = None
    tasks_list = result.get("tasks") or []
    if tasks_list:
        publish_task_id = tasks_list[0].get("task_id")

    if failed_count > 0 or success_count <= 0:
        return {
            "task_id": task.task_id,
            "status": "fail",
            "message": "发布任务入队失败",
            "publish_task_id": publish_task_id
        }

    return {
        "task_id": task.task_id,
        "status": "success",
        "message": "发布任务已入队",
        "publish_task_id": publish_task_id
    }


@router.post(
    "/generate_tasks",
    response_model=Response,
    summary="生成矩阵任务",
    description="""
    生成多平台、多账号、多素材的矩阵发布任务
    
    规则：
    - 按平台优先级顺序处理
    - 每个平台内账号轮询
    - 素材按账号索引分配，平台内不重复
    - 不同平台可复用同一素材
    """
)
async def generate_tasks(
    req: GenerateTasksRequest,
    scheduler: MatrixScheduler = Depends(get_scheduler)
):
    """生成矩阵任务"""
    try:
        tasks = scheduler.generate_tasks(
            platforms=req.platforms,
            accounts=req.accounts,
            materials=req.materials,
            title=req.title,
            description=req.description,
            topics=req.topics,
            cover_path=req.cover_path,
            material_configs=req.material_configs,
            batch_name=req.batch_name
        )
        
        return Response(
            success=True,
            message=f"成功生成 {len(tasks)} 个矩阵任务",
            data={
                "count": len(tasks),
                "tasks": tasks,
                "batch_id": tasks[0].batch_id if tasks else None
            }
        )
    
    except Exception as e:
        logger.error(f"生成矩阵任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成任务失败: {str(e)}")


@router.get(
    "/tasks/next",
    response_model=TaskResponse,
    summary="获取下一个任务",
    description="获取下一个待执行任务（不移除），retry 队列优先"
)
async def get_next_task(scheduler: MatrixScheduler = Depends(get_scheduler)):
    """获取下一个任务"""
    try:
        task = scheduler.get_next_task()
        
        if task:
            return TaskResponse(
                task=task,
                message="获取成功"
            )
        else:
            return TaskResponse(
                task=None,
                message="没有待执行任务"
            )
    
    except Exception as e:
        logger.error(f"获取任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/tasks/pop",
    response_model=TaskResponse,
    summary="弹出下一个任务",
    description="弹出下一个待执行任务（移除并标记为 running）"
)
async def pop_next_task(scheduler: MatrixScheduler = Depends(get_scheduler)):
    """弹出下一个任务"""
    try:
        task = scheduler.pop_next_task()
        
        if task:
            return TaskResponse(
                task=task,
                message="任务已分配"
            )
        else:
            return TaskResponse(
                task=None,
                message="没有待执行任务"
            )
    
    except Exception as e:
        logger.error(f"弹出任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/tasks/dispatch",
    response_model=Response,
    summary="并发提交矩阵任务",
    description="并发弹出并提交矩阵任务到发布队列（单次请求可批量执行）"
)
async def dispatch_tasks(
    limit: int = Query(0, ge=0, description="最大弹出任务数，0表示全部"),
    scheduler: MatrixScheduler = Depends(get_scheduler)
):
    """并发提交矩阵任务"""
    try:
        stats = scheduler.get_statistics()
        available = stats.get("pending", 0) + stats.get("retry", 0)
        if available == 0:
            return Response(
                success=True,
                message="没有待执行任务",
                data={
                    "requested": limit,
                    "dispatched": 0,
                    "success_count": 0,
                    "failed_count": 0,
                    "details": []
                }
            )

        if limit <= 0 or limit > available:
            limit = available

        tasks = scheduler.pop_next_tasks(limit)
        if not tasks:
            return Response(
                success=True,
                message="没有待执行任务",
                data={
                    "requested": limit,
                    "dispatched": 0,
                    "success_count": 0,
                    "failed_count": 0,
                    "details": []
                }
            )

        service = get_publish_service()
        results = await asyncio.gather(
            *[asyncio.to_thread(_dispatch_matrix_task_sync, service, task) for task in tasks],
            return_exceptions=True
        )

        success_count = 0
        failed_count = 0
        details = []

        for task, result in zip(tasks, results):
            if isinstance(result, Exception):
                failed_count += 1
                message = str(result)
                scheduler.report_result(task_id=task.task_id, status="fail", message=message)
                details.append({
                    "task_id": task.task_id,
                    "status": "fail",
                    "message": message
                })
                continue

            status = result.get("status", "fail")
            message = result.get("message", "")
            publish_task_id = result.get("publish_task_id")

            if status == "success":
                success_count += 1
                scheduler.report_result(task_id=task.task_id, status="success", message=message)
            else:
                failed_count += 1
                scheduler.report_result(task_id=task.task_id, status="fail", message=message)

            details.append({
                "task_id": task.task_id,
                "status": status,
                "message": message,
                "publish_task_id": publish_task_id
            })

        return Response(
            success=True,
            message="并发调度完成",
            data={
                "requested": limit,
                "dispatched": len(tasks),
                "success_count": success_count,
                "failed_count": failed_count,
                "details": details
            }
        )

    except Exception as e:
        logger.error(f"并发提交矩阵任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/tasks/report",
    response_model=Response,
    summary="上报任务结果",
    description="""
    上报任务执行结果
    
    状态：
    - success: 执行成功
    - fail: 执行失败（达到最大重试次数后进入 failed，否则进入 retry）
    - need_verification: 需要验证码（自动移至 retry 队列末尾）
    """
)
async def report_result(
    req: ReportResultRequest,
    scheduler: MatrixScheduler = Depends(get_scheduler)
):
    """上报任务结果"""
    try:
        task = scheduler.report_result(
            task_id=req.task_id,
            status=req.status,
            message=req.message,
            verification_url=req.verification_url
        )
        
        if not task:
            raise HTTPException(status_code=404, detail=f"任务不存在: {req.task_id}")
        
        return Response(
            success=True,
            message=f"任务状态已更新: {task.status}",
            data={"task": task}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上报任务结果失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/tasks/list",
    response_model=TaskListResponse,
    summary="获取所有任务",
    description="获取所有任务列表，按状态分组"
)
async def list_all_tasks(scheduler: MatrixScheduler = Depends(get_scheduler)):
    """获取所有任务"""
    try:
        all_tasks = scheduler.get_all_tasks()
        stats = scheduler.get_statistics()
        
        return TaskListResponse(
            pending=all_tasks["pending"],
            retry=all_tasks["retry"],
            running=all_tasks["running"],
            finished=all_tasks["finished"],
            failed=all_tasks["failed"],
            total=stats["total"]
        )
    
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/tasks/{task_id}",
    response_model=Response,
    summary="获取单个任务详情"
)
async def get_task_detail(
    task_id: str,
    scheduler: MatrixScheduler = Depends(get_scheduler)
):
    """获取任务详情"""
    try:
        task = scheduler.get_task_by_id(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
        
        return Response(
            success=True,
            message="获取成功",
            data={"task": task}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/stats",
    response_model=Response,
    summary="获取统计信息"
)
async def get_statistics(scheduler: MatrixScheduler = Depends(get_scheduler)):
    """获取统计信息"""
    try:
        stats = scheduler.get_statistics()
        
        return Response(
            success=True,
            message="获取成功",
            data=stats
        )
    
    except Exception as e:
        logger.error(f"获取统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/tasks/reset",
    response_model=StatusResponse,
    summary="重置任务池"
)
async def reset_tasks(scheduler: MatrixScheduler = Depends(get_scheduler)):
    """重置所有任务"""
    try:
        scheduler.reset()
        
        return StatusResponse(
            success=True,
            message="任务池已重置"
        )
    
    except Exception as e:
        logger.error(f"重置任务池失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/tasks/{task_id}",
    response_model=StatusResponse,
    summary="取消任务"
)
async def cancel_task(
    task_id: str,
    scheduler: MatrixScheduler = Depends(get_scheduler)
):
    """取消任务"""
    try:
        success = scheduler.cancel_task(task_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
        
        return StatusResponse(
            success=True,
            message=f"任务已取消: {task_id}"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
