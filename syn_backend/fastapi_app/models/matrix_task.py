"""
矩阵发布任务模型
支持多平台、多账号、多素材的调度
"""
from pydantic import BaseModel, Field
from enum import Enum
from uuid import uuid4
from typing import Optional
from datetime import datetime


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    RETRY = "retry"
    FINISHED = "finished"
    FAILED = "failed"
    NEED_VERIFICATION = "need_verification"


class MatrixTask(BaseModel):
    """矩阵发布任务"""
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    platform: str = Field(..., description="平台标识 (douyin/kuaishou/xiaohongshu/channels/bilibili)")
    account_id: str = Field(..., description="账号ID")
    material_id: str = Field(..., description="素材ID")
    material_path: Optional[str] = Field(None, description="素材路径")
    
    # 发布内容
    title: Optional[str] = Field(None, description="标题")
    description: Optional[str] = Field(None, description="描述")
    topics: list[str] = Field(default_factory=list, description="话题标签")
    cover_path: Optional[str] = Field(None, description="封面路径")
    
    # 任务状态
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    priority: int = Field(default=5, description="优先级 (1-10, 越小越高)")
    
    # 重试相关
    retry_count: int = Field(default=0, description="重试次数")
    max_retries: int = Field(default=3, description="最大重试次数")
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    scheduled_time: Optional[datetime] = Field(None, description="定时发布时间")
    
    # 错误信息
    error_message: Optional[str] = None
    verification_url: Optional[str] = Field(None, description="验证码URL")
    
    # 批次ID
    batch_id: Optional[str] = Field(None, description="批次ID")

    class Config:
        use_enum_values = True

    @staticmethod
    def create(
        platform: str,
        account_id: str,
        material_id: str,
        material_path: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        topics: Optional[list[str]] = None,
        cover_path: Optional[str] = None,
        batch_id: Optional[str] = None,
        priority: int = 5
    ) -> "MatrixTask":
        """创建新任务"""
        return MatrixTask(
            task_id=str(uuid4()),
            platform=platform,
            account_id=account_id,
            material_id=material_id,
            material_path=material_path,
            title=title,
            description=description,
            topics=topics or [],
            cover_path=cover_path,
            batch_id=batch_id,
            priority=priority,
            status=TaskStatus.PENDING,
        )


class GenerateTasksRequest(BaseModel):
    """生成矩阵任务请求"""
    platforms: list[str] = Field(..., description="平台列表")
    accounts: dict[str, list[str]] = Field(..., description="平台账号映射")
    materials: list[str] = Field(..., description="素材ID列表")
    
    # 可选的统一配置
    title: Optional[str] = Field(None, description="统一标题")
    description: Optional[str] = Field(None, description="统一描述")
    topics: Optional[list[str]] = Field(None, description="统一话题")
    cover_path: Optional[str] = Field(None, description="统一封面")
    
    # 差异化配置
    material_configs: Optional[dict[str, dict]] = Field(
        None,
        description="素材差异化配置 {material_id: {title, description, topics, cover_path}}"
    )
    
    batch_name: Optional[str] = Field(None, description="批次名称")


class ReportResultRequest(BaseModel):
    """上报任务结果请求"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="状态: success/fail/need_verification")
    message: str = Field(default="", description="附加消息")
    verification_url: Optional[str] = Field(None, description="验证码URL")


class TaskResponse(BaseModel):
    """任务响应"""
    task: Optional[MatrixTask] = None
    message: str = ""
    
    
class TaskListResponse(BaseModel):
    """任务列表响应"""
    pending: list[MatrixTask] = Field(default_factory=list)
    retry: list[MatrixTask] = Field(default_factory=list)
    running: list[MatrixTask] = Field(default_factory=list)
    finished: list[MatrixTask] = Field(default_factory=list)
    failed: list[MatrixTask] = Field(default_factory=list)
    total: int = 0
