"""
投放计划模块路由 (Refactored for Matrix System)
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional

from fastapi_app.models.campaign_new import CreateCampaignRequest, Campaign
from fastapi_app.services.campaign_service import get_campaign_service, CampaignService

router = APIRouter(prefix="/campaigns", tags=["投放计划"])

@router.post("/create")
async def create_campaign(
    request: CreateCampaignRequest,
    service: CampaignService = Depends(get_campaign_service)
):
    """创建新的矩阵投放计划"""
    campaign = await service.create_campaign(request)
    return {
        "status": "success",
        "result": {
            "success": True,
            "campaign_id": campaign.id,
            "tasks_created": campaign.task_count
        }
    }

@router.get("/list")
async def list_campaigns(
    service: CampaignService = Depends(get_campaign_service)
):
    """获取所有投放计划列表"""
    campaigns = service.list_campaigns()
    return {
        "status": "success",
        "result": {
            "success": True,
            "items": campaigns
        }
    }

@router.get("/{campaign_id}")
async def get_campaign_detail(
    campaign_id: str,
    service: CampaignService = Depends(get_campaign_service)
):
    """获取投放计划详情"""
    campaign = service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
    return {
        "status": "success",
        "result": {
            "success": True,
            "plan": campaign
        }
    }

@router.get("/{campaign_id}/tasks")
async def get_campaign_tasks(
    campaign_id: str,
    service: CampaignService = Depends(get_campaign_service)
):
    """获取计划关联的任务清单"""
    tasks = service.get_campaign_tasks(campaign_id)
    return {
        "status": "success",
        "result": {
            "success": True,
            "items": tasks
        }
    }

@router.post("/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: str,
    service: CampaignService = Depends(get_campaign_service)
):
    """暂停投放计划"""
    service.pause_campaign(campaign_id)
    return {"status": "success", "result": {"success": True}}

@router.post("/{campaign_id}/resume")
async def resume_campaign(
    campaign_id: str,
    service: CampaignService = Depends(get_campaign_service)
):
    """恢复投放计划"""
    service.resume_campaign(campaign_id)
    return {"status": "success", "result": {"success": True}}


@router.post("/{campaign_id}/execute")
async def execute_campaign(
    campaign_id: str,
    service: CampaignService = Depends(get_campaign_service)
):
    campaign = await service.execute_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
    return {
        "status": "success",
        "result": {
            "success": True,
            "campaign_id": campaign.id,
            "tasks_created": campaign.task_count
        }
    }

@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    service: CampaignService = Depends(get_campaign_service)
):
    """删除投放计划"""
    service.delete_campaign(campaign_id)
    return {"status": "success", "result": {"success": True}}
