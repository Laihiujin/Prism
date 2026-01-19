"""
Task Packages 路由
任务包管理 API
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
# 尝试直接导入 campaign_manager，假设项目根目录已在 sys.path 中
try:
    from myUtils.campaign_manager import campaign_manager
except ImportError:
    # 如果失败，尝试添加路径（兼容性回退）
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
    from myUtils.campaign_manager import campaign_manager

router = APIRouter(prefix="/task-packages", tags=["任务包管理"])


# ========== Request Models ==========

class TaskPackageCreateRequest(BaseModel):
    plan_id: int
    name: str
    platform: str
    account_ids: List[str] = []
    material_ids: List[str] = []
    dispatch_mode: str = "random"
    time_strategy: Optional[Dict[str, Any]] = None
    created_by: str = "api"


class TaskPackageUpdateRequest(BaseModel):
    name: Optional[str] = None
    account_ids: Optional[List[str]] = None
    material_ids: Optional[List[str]] = None
    dispatch_mode: Optional[str] = None
    time_strategy: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


# ========== Endpoints ==========

@router.post("")
async def create_task_package(request: TaskPackageCreateRequest):
    """创建任务包"""
    data = {
        "plan_id": request.plan_id,
        "name": request.name,
        "platform": request.platform,
        "account_ids": request.account_ids,
        "material_ids": request.material_ids,
        "dispatch_mode": request.dispatch_mode,
        "time_strategy": request.time_strategy or {},
        "created_by": request.created_by,
    }
    result = campaign_manager.create_task_package(data)
    return {"status": "success", "result": result}


@router.get("")
async def list_task_packages(plan_id: Optional[int] = None):
    """获取任务包列表"""
    if plan_id:
        packages = campaign_manager.get_packages_by_plan(plan_id)
    else:
        # 获取所有任务包 - 暂时返回空列表
        packages = []
    return {"status": "success", "result": {"success": True, "items": packages}}


@router.get("/{package_id}")
async def get_task_package(package_id: int):
    """获取任务包详情"""
    # 暂时未实现
    return {"status": "success", "result": {"success": True, "package": None}}


@router.put("/{package_id}")
async def update_task_package(package_id: int, request: TaskPackageUpdateRequest):
    """更新任务包"""
    # 暂时未实现
    return {"status": "success", "result": {"success": True}}


@router.delete("/{package_id}")
async def delete_task_package(package_id: int):
    """删除任务包"""
    # 暂时未实现
    return {"status": "success", "result": {"success": True}}


@router.post("/{package_id}/generate-tasks")
async def generate_tasks(package_id: int):
    """从任务包生成任务"""
    result = campaign_manager.generate_tasks_from_package(package_id)
    return {"status": "success", "result": result}
