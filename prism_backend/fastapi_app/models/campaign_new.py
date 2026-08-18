from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
from uuid import uuid4

class ScheduleType(str, Enum):
    IMMEDIATE = "immediate"
    DAILY = "daily"
    RANGE = "range"

class IntervalMode(str, Enum):
    ACCOUNT_VIDEO = "account_video"  # 按账号&视频间隔发布
    VIDEO = "video"  # 按视频间隔发布

class CampaignStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"

class Campaign(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    platforms: List[str]
    account_ids: List[str]
    material_ids: List[str]
    schedule_type: ScheduleType
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    goals: List[str] = Field(default_factory=list)
    remark: str = ""
    task_count: int = 0
    status: CampaignStatus = CampaignStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # 矩阵节奏设置
    interval_enabled: bool = False  # 是否启用间隔方式（默认关闭）
    interval_mode: IntervalMode = IntervalMode.ACCOUNT_VIDEO
    interval_minutes: int = 30  # 间隔时长（分钟）
    
    # 关联的任务ID列表
    task_ids: List[str] = Field(default_factory=list)

class CreateCampaignRequest(BaseModel):
    name: str
    platforms: List[str]
    account_ids: List[str]
    material_ids: List[str]
    schedule_type: ScheduleType = ScheduleType.IMMEDIATE
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    interval_enabled: bool = False
    interval_mode: IntervalMode = IntervalMode.ACCOUNT_VIDEO
    interval_minutes: int = 30
    goals: List[str] = Field(default_factory=list)
    remark: str = ""
    execute_now: bool = True

class CampaignResponse(BaseModel):
    campaign: Campaign
    tasks_created: int
