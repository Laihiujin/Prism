"""
账号管理相关的Pydantic Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ===== 基础Schema =====
class AccountBase(BaseModel):
    """账号基础信息"""
    name: str = Field(..., min_length=1, max_length=100, description="账号名称")
    platform: str = Field(..., description="平台名称（xiaohongshu/channels/douyin/kuaishou/bilibili）")
    platform_code: int = Field(..., ge=1, le=5, description="平台编码(1-5)")
    note: Optional[str] = Field(None, max_length=500, description="账号备注")


class AccountCreate(BaseModel):
    """创建账号请求"""
    account_id: str = Field(..., description="账号ID")
    name: str
    platform: str
    platform_code: int = Field(..., ge=1, le=5)
    cookie: Dict[str, Any] = Field(..., description="Cookie数据(JSON)")
    user_id: Optional[str] = Field(None, description="平台用户ID")
    avatar: Optional[str] = None
    original_name: Optional[str] = None
    note: Optional[str] = None
    status: str = Field(default="valid", description="账号状态")


class AccountUpdate(BaseModel):
    """更新账号请求"""
    name: Optional[str] = None
    note: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(valid|expired|error|file_missing)$")
    avatar: Optional[str] = None
    original_name: Optional[str] = None


class AccountResponse(BaseModel):
    """账号响应模型"""
    id: str = Field(..., alias="account_id", description="账号ID")
    platform: str
    platform_code: int
    name: str
    status: str
    filePath: str = Field(..., alias="cookie_file")
    last_checked: Optional[str] = None
    avatar: Optional[str] = None
    original_name: Optional[str] = None
    note: Optional[str] = None
    user_id: Optional[str] = None
    login_status: Optional[str] = Field(None, description="登录状态(logged_in/session_expired/unknown)")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "account_12345",
                "platform": "douyin",
                "platform_code": 3,
                "name": "测试账号",
                "status": "valid",
                "filePath": "account_12345.json",
                "user_id": "1234567890",
                "login_status": "logged_in"
            }
        }


class AccountListResponse(BaseModel):
    """账号列表响应"""
    success: bool = True
    total: int
    items: List[AccountResponse]


class AccountVerifyRequest(BaseModel):
    """验证账号请求"""
    account_id: str


class AccountVerifyResponse(BaseModel):
    """验证账号响应"""
    success: bool
    status: str = Field(..., description="验证结果状态(valid/expired/error)")
    user_id: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


class BatchVerifyResponse(BaseModel):
    """批量验证响应"""
    success: bool
    total: int
    valid: int
    expired: int
    error: int
    details: List[Dict[str, Any]]
    message: str


class AccountStatsResponse(BaseModel):
    """账号统计响应"""
    total: int
    valid: int
    expired: int
    error: int
    file_missing: int
    by_platform: Dict[str, int]


class DeepSyncResponse(BaseModel):
    """深度同步响应"""
    success: bool
    added: int = Field(..., description="新增账号数")
    marked_missing: int = Field(..., description="标记文件丢失数")
    total_files: int
    backed_up: int
    cleaned_up: int
    message: str


class AccountFilterRequest(BaseModel):
    """高级筛选请求"""
    platform: Optional[str] = None
    status: Optional[str] = None
    note_keyword: Optional[str] = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=1000)


class FrontendAccountItem(BaseModel):
    account_id: str = Field(..., description="账号ID")
    platform: str = Field(..., description="平台")
    user_id: Optional[str] = Field(None, description="平台用户ID")


class FrontendAccountSnapshotRequest(BaseModel):
    """Frontend account list snapshot for pruning."""
    accounts: List[FrontendAccountItem]
