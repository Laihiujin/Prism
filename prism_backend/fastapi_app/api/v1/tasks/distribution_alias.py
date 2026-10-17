"""QR distribution API, backed by durable assignments and the publishing queue."""
from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from datetime import datetime
from fastapi_app.db.session import get_main_db
from fastapi_app.services.qr_distribution import DistributionRequest, get_qr_distribution_service

router = APIRouter(prefix="/tasks", tags=["扫码分发"])


class PackageSchedule(BaseModel):
    schedule_type: Literal["immediate", "scheduled"] = "immediate"
    scheduled_time: datetime | None = None
    interval_seconds: int = Field(default=600, ge=60, le=86400)
    item_count: int = Field(ge=1, le=100)


class DistributionAction(BaseModel):
    action: Literal["refresh", "stop", "configure", "publish"]
    platform: str | None = None
    package_id: str | None = None
    schedule: PackageSchedule | None = None


@router.get("/distribution")
async def list_distribution_tasks():
    return {"success": True, "data": get_qr_distribution_service().list()}


@router.post("/distribution")
async def create_distribution_task(request: DistributionRequest, db=Depends(get_main_db)):
    return {"success": True, "data": get_qr_distribution_service().create(request, db)}


@router.get("/distribution/{task_id}")
async def get_distribution_task(task_id: str):
    return {"success": True, "data": get_qr_distribution_service().get(task_id)}


@router.post("/distribution/{task_id}/action")
async def distribution_action(task_id: str, request: DistributionAction):
    return {"success": True, "data": await get_qr_distribution_service().action(task_id, **request.model_dump(mode="json", exclude_none=True))}
