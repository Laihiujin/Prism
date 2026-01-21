"""
Agent相关数据模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


class ScriptMeta(BaseModel):
    """脚本元数据"""
    generated_by: str = Field(default="AI", description="生成者")
    plan_name: str = Field(..., description="计划名称")
    description: Optional[str] = Field(None, description="计划描述")
    created_at: Optional[datetime] = Field(default_factory=datetime.now, description="创建时间")


class SaveScriptRequest(BaseModel):
    """保存脚本请求"""
    filename: str = Field(..., description="文件名")
    content: str = Field(..., description="脚本内容(JSON或Python)")
    script_type: Literal["json", "python"] = Field(default="json", description="脚本类型")
    meta: ScriptMeta = Field(..., description="元数据")


class SaveScriptResponse(BaseModel):
    """保存脚本响应"""
    status: str = "success"
    script_id: str = Field(..., description="脚本ID")
    path: str = Field(..., description="保存路径")


class ExecutionOptions(BaseModel):
    """执行选项"""
    priority: int = Field(default=5, ge=1, le=10, description="优先级(1-10)")
    validate_only: bool = Field(default=False, description="仅验证不执行")


class ExecuteScriptRequest(BaseModel):
    """执行脚本请求"""
    script_id: str = Field(..., description="脚本ID")
    mode: Literal["execute", "dry-run"] = Field(default="execute", description="执行模式")
    options: Optional[ExecutionOptions] = Field(default_factory=ExecutionOptions, description="执行选项")


class ExecuteScriptResponse(BaseModel):
    """执行脚本响应"""
    status: str = "accepted"
    task_batch_id: str = Field(..., description="任务批次ID")
    tasks_created: int = Field(..., description="创建的任务数")
    estimated_time: str = Field(..., description="预计耗时")


# SynapseAutomation DSL Schema
class TaskStrategy(BaseModel):
    """任务策略"""
    avoid_duplicate: bool = Field(default=True, description="避免重复")
    platform_unique: bool = Field(default=True, description="平台唯一")
    random_interval: bool = Field(default=True, description="随机间隔")


class PublishTask(BaseModel):
    """发布任务"""
    video_id: int = Field(..., description="视频ID")
    account_id: str = Field(..., description="账号ID")
    platform: str = Field(..., description="平台")
    title: str = Field(..., description="标题")
    description: Optional[str] = Field(None, description="描述")
    tags: List[str] = Field(default_factory=list, description="标签")
    publish_at: str = Field(default="immediate", description="发布时间")
    delay_range: List[int] = Field(default=[60, 180], description="延迟范围(秒)")
    strategy: TaskStrategy = Field(default_factory=TaskStrategy, description="策略")


class PublishPlan(BaseModel):
    """发布计划"""
    plan_name: str = Field(..., description="计划名称")
    version: str = Field(default="1.0", description="版本")
    tasks: List[PublishTask] = Field(..., description="任务列表")


# AI上下文Schema
class AccountContext(BaseModel):
    """账号上下文"""
    id: str
    platform: str
    status: str
    used_videos: List[int] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class VideoContext(BaseModel):
    """视频上下文"""
    id: int
    title: str
    duration: Optional[int] = None
    used_in: List[str] = Field(default_factory=list, description="已使用的账号")
    platform_used: List[str] = Field(default_factory=list, description="已发布的平台")
    path: str
    transcript: Optional[str] = Field(None, description="语音转写文本")


class SystemContext(BaseModel):
    """系统上下文(提供给AI)"""
    accounts: List[AccountContext]
    videos: List[VideoContext]
