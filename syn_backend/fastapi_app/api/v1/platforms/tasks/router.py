"""
通用任务路由
提供跨平台的任务状态查询
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
import logging

from ..task_manager import task_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/platforms/tasks", tags=["platforms-tasks"])


@router.get("/{task_id}")
async def get_task_status(task_id: str):
    """
    查询任务状态（通用接口）
    
    Args:
        task_id: 任务ID
        
    Returns:
        任务状态信息
    """
    try:
        status = task_manager.get_task_status(task_id)
        
        if status is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        return {
            "success": True,
            "data": status
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TasksAPI] 查询任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", include_in_schema=True)
@router.get("", include_in_schema=False)
async def list_tasks(
    platform: Optional[str] = None,
    task_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
):
    """
    查询任务列表
    
    Args:
        platform: 平台筛选
        task_type: 任务类型筛选
        status: 状态筛选
        limit: 返回数量限制
        
    Returns:
        任务列表
    """
    try:
        tasks = []
        for task in task_manager.tasks.values():
            # 应用筛选
            if platform and task.platform != platform:
                continue
            if task_type and task.task_type != task_type:
                continue
            if status and task.status != status:
                continue
            
            tasks.append(task.to_dict())
            
            if len(tasks) >= limit:
                break
        
        return {
            "success": True,
            "data": {
                "tasks": tasks,
                "total": len(tasks)
            }
        }

    except Exception as e:
        logger.error(f"[TasksAPI] 查询任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
