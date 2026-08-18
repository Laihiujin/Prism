"""
Plans 路由别名
将 /api/plans 映射到 campaigns 功能
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
# 尝试直接导入 campaign_manager
try:
    from myUtils.campaign_manager import campaign_manager
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
    from myUtils.campaign_manager import campaign_manager

router = APIRouter(prefix="/plans", tags=["计划管理"])


# ========== Request Models ==========

class PlanCreateRequest(BaseModel):
    name: str
    platform: Optional[str] = None
    platforms: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    goal_type: str = "other"
    remark: str = ""
    created_by: str = "api"


class PlanUpdateRequest(BaseModel):
    name: Optional[str] = None
    platforms: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None
    goal_type: Optional[str] = None
    remark: Optional[str] = None


# ========== Endpoints ==========

@router.get("")
async def list_plans():
    """获取所有计划列表"""
    plans: List[Dict[str, Any]] = campaign_manager.get_all_plans()
    return {"status": "success", "result": {"success": True, "items": plans}}


@router.post("")
async def create_plan(request: PlanCreateRequest):
    """创建计划"""
    platforms = request.platforms or []
    if request.platform and request.platform not in platforms:
        platforms.append(request.platform)
    
    data = {
        "name": request.name,
        "platforms": platforms,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "goal_type": request.goal_type,
        "remark": request.remark,
        "created_by": request.created_by,
    }
    result = campaign_manager.create_plan(data)
    return {"status": "success", "result": result}


@router.get("/{plan_id}")
async def get_plan_detail(plan_id: str):
    """获取计划详情"""
    plan = campaign_manager.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return {"status": "success", "result": {"success": True, "plan": plan}}


@router.put("/{plan_id}")
async def update_plan(plan_id: str, request: PlanUpdateRequest):
    """更新计划"""
    update_data = request.dict(exclude_unset=True)
    result = campaign_manager.update_plan(plan_id, update_data)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return {"status": "success", "result": result}


@router.delete("/{plan_id}")
async def delete_plan(plan_id: str):
    """删除计划"""
    result = campaign_manager.delete_plan(plan_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return {"status": "success", "result": result}


@router.post("/{plan_id}/publish")
async def publish_plan(plan_id: str):
    """发布计划"""
    # 这里需要实现发布逻辑
    # 暂时返回成功
    return {"status": "success", "message": f"Plan {plan_id} published"}


@router.get("/{plan_id}/packages")
async def get_plan_packages(plan_id: str):
    """获取计划的素材包"""
    # 这里需要实现获取素材包的逻辑
    # 暂时返回空列表
    return {"status": "success", "result": {"success": True, "packages": []}}
