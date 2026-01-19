"""
人工任务管理API路由
提供人工任务的查询、重试、删除等接口
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from fastapi_app.services.manual_task_manager import manual_task_manager
from fastapi_app.core.logger import logger

router = APIRouter(prefix="/manual-tasks", tags=["人工任务管理"])

class RetryTaskRequest(BaseModel):
    task_id: str

class UpdateStatusRequest(BaseModel):
    task_id: str
    status: str
    error: Optional[str] = None

@router.get("/list")
async def list_manual_tasks(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
):
    """获取人工任务列表"""
    try:
        tasks = manual_task_manager.get_pending_tasks(platform=platform, limit=limit)
        
        # 如果指定了status，进行过滤
        if status:
            tasks = [t for t in tasks if t.get('status') == status]
        
        return {
            "status": "success",
            "data": {
                "total": len(tasks),
                "items": tasks
            }
        }
    except Exception as e:
        logger.error(f"获取人工任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_manual_tasks_stats():
    """获取人工任务统计"""
    try:
        stats = manual_task_manager.get_stats()
        return {
            "status": "success",
            "data": stats
        }
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{task_id}")
async def get_manual_task(task_id: str):
    """获取单个人工任务详情"""
    try:
        task = manual_task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        return {
            "status": "success",
            "data": task
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{task_id}/retry")
async def retry_manual_task(task_id: str):
    """重试人工任务"""
    try:
        success = manual_task_manager.retry_task(task_id)
        if not success:
            raise HTTPException(status_code=400, detail="重试失败，可能已达最大重试次数")
        
        return {
            "status": "success",
            "message": "任务已重置为待处理状态"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重试任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{task_id}/status")
async def update_task_status(task_id: str, request: UpdateStatusRequest):
    """更新任务状态"""
    try:
        success = manual_task_manager.update_status(
            task_id=task_id,
            status=request.status,
            error=request.error
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="更新状态失败")
        
        return {
            "status": "success",
            "message": "状态已更新"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{task_id}")
async def delete_manual_task(task_id: str):
    """删除人工任务"""
    try:
        success = manual_task_manager.delete_task(task_id)
        if not success:
            raise HTTPException(status_code=400, detail="删除失败")
        
        return {
            "status": "success",
            "message": "任务已删除"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
