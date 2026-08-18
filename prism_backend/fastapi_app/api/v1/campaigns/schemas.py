"""
投放计划模块 Pydantic Schema 定义

包含:
- 计划相关模型
- 任务包相关模型
- 任务相关模型
- 时间策略模型
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ========== 枚举定义 ==========

class PlanStatus(str, Enum):
    """计划状态"""
    DRAFT = "draft"           # 草稿
    READY = "ready"           # 就绪
    RUNNING = "running"       # 执行中
    PAUSED = "paused"         # 已暂停
    COMPLETED = "completed"   # 已完成
    CANCELLED = "cancelled"   # 已取消


class TimeStrategyMode(str, Enum):
    """时间策略模式"""
    ONCE = "once"              # 单次发布
    DATE_RANGE = "date_range"  # 日期范围
    DAILY = "daily"            # 每日定时
    WEEKLY = "weekly"          # 每周定时


class DispatchMode(str, Enum):
    """素材分配模式"""
    RANDOM = "random"  # 随机分配
    FIXED = "fixed"    # 固定顺序
    SMART = "smart"    # 智能匹配


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"       # 待执行
    RUNNING = "running"       # 执行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败
    CANCELLED = "cancelled"   # 已取消


# ========== 时间策略模型 ==========

class TimeStrategy(BaseModel):
    """时间策略配置"""
    mode: TimeStrategyMode
    date: Optional[str] = None  # YYYY-MM-DD 格式
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    time_points: List[str] = Field(default=["10:00", "14:00", "20:00"], description="发布时间点列表，格式HH:MM")
    per_account_per_day: int = Field(default=1, ge=1, le=10, description="每个账号每天发布次数")
    
    @validator('date', 'start_date', 'end_date')
    def validate_date_format(cls, v):
        """验证日期格式"""
        if v:
            try:
                datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                raise ValueError('日期格式必须是 YYYY-MM-DD')
        return v
    
    @validator('time_points')
    def validate_time_points(cls, v):
        """验证时间点格式"""
        for time_point in v:
            try:
                datetime.strptime(time_point, '%H:%M')
            except ValueError:
                raise ValueError(f'时间点格式必须是 HH:MM，错误值: {time_point}')
        return v
    
    class Config:
        use_enum_values = True


# ========== 投放计划模型 ==========

class PlanBase(BaseModel):
    """计划基础模型"""
    name: str = Field(..., min_length=1, max_length=100, description="计划名称")
    platforms: List[str] = Field(..., min_items=1, description="目标平台列表")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    goal_type: str = Field(default="exposure", description="目标类型：exposure,conversion,engagement")
    remark: Optional[str] = Field(None, max_length=500, description="备注")


class PlanCreate(PlanBase):
    """创建计划请求"""
    pass


class PlanUpdate(BaseModel):
    """更新计划请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    platforms: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[PlanStatus] = None
    remark: Optional[str] = None


class PlanResponse(PlanBase):
    """计划响应"""
    plan_id: int
    status: PlanStatus
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    
    # 统计信息
    total_packages: Optional[int] = None
    total_tasks: Optional[int] = None
    completed_tasks: Optional[int] = None
    
    class Config:
        from_attributes = True
        use_enum_values = True


# ========== 任务包模型 ==========

class PackageBase(BaseModel):
    """任务包基础模型"""
    name: str = Field(..., min_length=1, max_length=100, description="任务包名称")
    platform: str = Field(..., description="目标平台")
    account_ids: List[str] = Field(..., min_items=1, description="账号ID列表")
    material_ids: List[str] = Field(..., min_items=1, description="素材ID列表")
    dispatch_mode: DispatchMode = Field(default=DispatchMode.RANDOM, description="分配模式")
    time_strategy: TimeStrategy = Field(..., description="时间策略")


class PackageCreate(PackageBase):
    """创建任务包请求"""
    plan_id: int = Field(..., description="所属计划ID")


class PackageUpdate(BaseModel):
    """更新任务包请求"""
    name: Optional[str] = None
    account_ids: Optional[List[str]] = None
    material_ids: Optional[List[str]] = None
    dispatch_mode: Optional[DispatchMode] = None
    time_strategy: Optional[TimeStrategy] = None


class PackageResponse(PackageBase):
    """任务包响应"""
    package_id: int
    plan_id: int
    status: str
    generated_task_count: int = 0
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    
    class Config:
        from_attributes = True
        use_enum_values = True


# ========== 发布任务模型 ==========

class TaskBase(BaseModel):
    """任务基础模型"""
    platform: str
    account_id: str
    material_id: int
    title: Optional[str] = None
    scheduled_time: Optional[datetime] = None


class TaskCreate(TaskBase):
    """创建任务请求"""
    plan_id: int
    package_id: Optional[int] = None
    publish_mode: str = Field(default="auto", description="发布模式：auto,manual,scheduled")


class TaskResponse(TaskBase):
    """任务响应"""
    task_id: int
    plan_id: int
    package_id: Optional[int] = None
    status: TaskStatus
    publish_mode: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # 执行信息
    execution_log: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    
    class Config:
        from_attributes = True
        use_enum_values = True


class TaskStatusResponse(BaseModel):
    """任务状态详细响应"""
    task_id: int
    status: TaskStatus
    progress: Optional[float] = Field(None, ge=0, le=100, description="执行进度百分比")
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    execution_log: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    class Config:
        use_enum_values = True


# ========== 批量操作模型 ==========

class PublishPlanRequest(BaseModel):
    """发布计划请求"""
    execution_mode: str = Field(default="auto", description="执行模式：auto,scheduled,manual")
    start_immediately: bool = Field(default=True, description="是否立即开始")
    dry_run: bool = Field(default=False, description="仅生成任务不执行")
    priority: int = Field(default=5, ge=1, le=10, description="优先级")


class PublishPlanResponse(BaseModel):
    """发布计划响应"""
    success: bool
    plan_id: int
    total_tasks: int
    task_ids: Optional[List[str]] = None
    message: str
    dry_run: bool = False
    tasks_preview: Optional[List[Dict]] = None


class GenerateTasksRequest(BaseModel):
    """生成任务请求"""
    validate_only: bool = Field(default=False, description="仅验证不生成")


class GenerateTasksResponse(BaseModel):
    """生成任务响应"""
    success: bool
    package_id: int
    task_count: int
    tasks: Optional[List[Dict]] = None
    validation: Optional[Dict] = None
    message: str


# ========== 进度监控模型 ==========

class PlanProgress(BaseModel):
    """计划执行进度"""
    plan_id: int
    total_tasks: int
    status_counts: Dict[str, int]
    progress: float = Field(..., ge=0, le=100, description="整体进度百分比")
    estimated_completion: Optional[datetime] = None
    timestamp: datetime


class TaskFilter(BaseModel):
    """任务筛选条件"""
    plan_id: Optional[int] = None
    package_id: Optional[int] = None
    status: Optional[TaskStatus] = None
    platform: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    
    class Config:
        use_enum_values = True


# ========== 统计模型 ==========

class CampaignStats(BaseModel):
    """投放统计"""
    total_plans: int
    active_plans: int
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    success_rate: float = Field(..., ge=0, le=100)
    platform_distribution: Dict[str, int]
    
    class Config:
        from_attributes = True
