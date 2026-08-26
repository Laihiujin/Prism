"""
发布模块的Pydantic Schema定义
"""
from pydantic import BaseModel, Field, field_validator, AliasChoices
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


class BatchTaskItem(BaseModel):
    """批量任务单项配置"""
    file_id: int = Field(..., description="文件ID")
    title: Optional[str] = Field(None, description="覆盖标题")
    description: Optional[str] = Field(None, description="覆盖描述")
    topics: Optional[List[str]] = Field(
        None,
        description="覆盖话题",
        validation_alias=AliasChoices("topics", "tags", "hashtag", "Hashtag"),
    )
    cover_path: Optional[str] = Field(None, description="覆盖封面路径")
    platform_titles: Optional[Dict[str, str]] = Field(
        default=None,
        description="按平台覆盖标题（key 可用平台代码/平台名）",
    )
    platform_descriptions: Optional[Dict[str, str]] = Field(
        default=None,
        description="按平台覆盖描述（key 可用平台代码/平台名）",
    )
    platform_topics: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="按平台覆盖话题（key 可用平台代码/平台名）",
    )


class BatchPublishRequest(BaseModel):
    """批量发布请求"""
    file_ids: List[int] = Field(..., min_length=1, description="文件ID列表")
    accounts: List[str] = Field(..., description="账号ID列表")
    platform: Optional[int] = Field(None, ge=1, le=7, description="平台代码（可选，不指定则支持多平台）")
    title: str = Field(..., description="统一标题（可包含变量）")
    description: Optional[str] = Field(None, description="统一描述")
    topics: Optional[List[str]] = Field(
        default_factory=list,
        description="统一话题",
        validation_alias=AliasChoices("topics", "tags", "hashtag", "Hashtag"),
    )
    cover_path: Optional[str] = Field(None, description="统一封面路径")
    scheduled_time: Optional[str] = Field(None, description="定时发布时间")
    interval_control_enabled: bool = Field(
        default=False,
        description="是否启用发布间隔控制（关闭则尽量并发提交任务）",
        validation_alias=AliasChoices("interval_control_enabled", "intervalControlEnabled", "interval_enabled", "intervalEnabled"),
    )
    interval_mode: Optional[Literal["account_first", "video_first"]] = Field(
        default=None,
        description="间隔排布方式：account_first/video_first",
        validation_alias=AliasChoices("interval_mode", "intervalMode"),
    )
    interval_seconds: Optional[int] = Field(
        default=300,
        ge=0,
        le=24 * 60 * 60,
        description="间隔秒数（默认300=5分钟）",
        validation_alias=AliasChoices("interval_seconds", "intervalSeconds"),
    )
    random_offset: Optional[int] = Field(
        default=0,
        ge=0,
        le=3600,
        description="随机偏移范围（±秒），0表示不随机，例如120表示±2分钟随机偏移",
        validation_alias=AliasChoices("random_offset", "randomOffset"),
    )

    # 🆕 NEW: Assignment strategy configuration
    assignment_strategy: Optional[Literal[
        "one_per_account",
        "all_per_account",
        "cross_platform_all",
        "per_platform_custom"
    ]] = Field(
        default="all_per_account",
        description="任务分配策略：决定创建哪些任务组合",
        validation_alias=AliasChoices("assignment_strategy", "assignmentStrategy"),
    )

    one_per_account_mode: Optional[Literal["random", "round_robin", "sequential"]] = Field(
        default="random",
        description="账号单次发布的分配方式（仅当 strategy='one_per_account' 时生效）",
        validation_alias=AliasChoices("one_per_account_mode", "onePerAccountMode"),
    )

    per_platform_overrides: Optional[Dict[str, str]] = Field(
        default=None,
        description="平台自定义策略覆盖（仅当 strategy='per_platform_custom' 时生效）",
        validation_alias=AliasChoices("per_platform_overrides", "perPlatformOverrides"),
    )

    # 🆕 NEW: Deduplication configuration
    allow_duplicate_publish: bool = Field(
        default=False,
        description="允许重复发布（即使该账号在平台上已发布过此视频）",
        validation_alias=AliasChoices("allow_duplicate_publish", "allowDuplicatePublish"),
    )

    dedup_window_days: int = Field(
        default=7,
        ge=0,
        le=365,
        description="去重时间窗口（天），0表示永久去重",
        validation_alias=AliasChoices("dedup_window_days", "dedupWindowDays"),
    )

    priority: Optional[int] = Field(5, ge=1, le=10, description="优先级 (1-10, 越小优先级越高)")
    items: Optional[List[BatchTaskItem]] = Field(None, description="差异化配置列表")

    @field_validator('file_ids')
    @classmethod
    def validate_file_ids(cls, v):
        """验证文件ID列表"""
        if not v:
            raise ValueError("文件ID列表不能为空")
        if len(v) > 100:
            raise ValueError("批量发布最多支持100个文件")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "file_ids": [1, 2, 3],
                "accounts": ["account_123", "account_456"],
                "platform": 3,
                "title": "批量发布视频",
                "topics": ["生活", "分享"],
                # Assignment strategy (NEW)
                "assignment_strategy": "all_per_account",
                "one_per_account_mode": "random",
                "allow_duplicate_publish": False,
                "dedup_window_days": 7,
                # Interval control (EXISTING)
                "interval_control_enabled": True,
                "interval_mode": "video_first",
                "interval_seconds": 300,
                "random_offset": 120,
                "priority": 5,
                "items": [
                    {
                        "file_id": 1,
                        "title": "特定视频标题",
                        "description": "特定描述"
                    }
                ]
            }
        }


class PublishPreset(BaseModel):
    """发布预设/计划"""
    name: str = Field(..., min_length=1, max_length=100, description="预设名称")
    platform: int = Field(..., ge=1, le=7, description="平台代码")
    accounts: List[str] = Field(..., description="默认账号列表")
    default_title_template: Optional[str] = Field(None, description="默认标题模板")
    default_description: Optional[str] = Field(None, description="默认描述")
    default_topics: Optional[List[str]] = Field(default_factory=list, description="默认话题")
    schedule_enabled: Optional[bool] = Field(False, description="是否启用定时")
    videos_per_day: Optional[int] = Field(1, ge=1, le=10, description="每天发布数量")
    schedule_date: Optional[str] = Field(None, description="定时日期")
    time_point: Optional[str] = Field("10:00", description="定时时间点")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "抖音日常发布",
                "platform": 3,
                "accounts": ["account_123"],
                "default_title_template": "每日分享 - {date}",
                "default_topics": ["生活", "日常"],
                "schedule_enabled": True,
                "videos_per_day": 2,
                "time_point": "18:00"
            }
        }


class PresetResponse(BaseModel):
    """预设响应"""
    id: int
    name: str
    platform: List[str] = Field(default_factory=list, description="平台列表")
    platforms: Optional[List[str]] = Field(default_factory=list, description="平台列表(别名)")
    accounts: List[str] = Field(default_factory=list, description="账号列表")
    default_title: Optional[str] = Field(None, description="默认标题")
    default_title_template: Optional[str] = Field(None, description="默认标题模板")
    default_description: Optional[str] = Field(None, description="默认描述")
    default_topics: Optional[str] = Field(None, description="默认话题")
    default_tags: Optional[str] = Field(None, description="默认标签")
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    schedule_enabled: Optional[bool] = Field(False, description="是否启用定时")
    videos_per_day: Optional[int] = Field(1, description="每天发布数量")
    schedule_date: Optional[str] = Field(None, description="定时日期")
    time_point: Optional[str] = Field("10:00", description="定时时间点")
    material_ids: Optional[List[str]] = Field(default_factory=list, description="素材ID列表")
    label: Optional[str] = Field(None, description="标签(别名)")
    title: Optional[str] = Field(None, description="标题(别名)")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    usage_count: Optional[int] = 0

    class Config:
        from_attributes = True


class PublishTaskResponse(BaseModel):
    """发布任务响应"""
    task_id: str
    status: str = Field(..., description="pending/running/success/failed")
    platform: int
    account_id: Optional[str] = None
    file_id: Optional[int] = None
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class PublishHistoryResponse(BaseModel):
    """发布历史响应"""
    task_id: int
    platform: str
    account_id: Optional[str] = None
    material_id: Optional[str] = None
    title: Optional[str] = None
    status: str
    schedule_time: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BatchPublishResponse(BaseModel):
    """批量发布响应"""
    batch_id: str = Field(..., description="批量任务ID")
    total_tasks: int = Field(..., description="总任务数")
    success_count: int = Field(0, description="成功数量")
    failed_count: int = Field(0, description="失败数量")
    pending_count: int = Field(0, description="待处理数量")
    tasks: List[PublishTaskResponse] = Field(default_factory=list, description="任务列表")

    class Config:
        json_schema_extra = {
            "example": {
                "batch_id": "batch_123456",
                "total_tasks": 10,
                "success_count": 8,
                "failed_count": 1,
                "pending_count": 1,
                "tasks": []
            }
        }


class PublishStatsResponse(BaseModel):
    """发布统计响应"""
    total_published: int = Field(0, description="总发布数")
    today_published: int = Field(0, description="今日发布数")
    pending_tasks: int = Field(0, description="待发布任务数")
    failed_tasks: int = Field(0, description="失败任务数")
    by_platform: Dict[str, int] = Field(default_factory=dict, description="按平台统计")

    class Config:
        json_schema_extra = {
            "example": {
                "total_published": 1000,
                "today_published": 50,
                "pending_tasks": 10,
                "failed_tasks": 2,
                "by_platform": {
                    "douyin": 500,
                    "xiaohongshu": 300,
                    "bilibili": 200
                }
            }
        }
