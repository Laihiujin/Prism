"""
通用响应Schema
"""
from typing import Generic, TypeVar, Optional, List, Any
from pydantic import BaseModel, Field


T = TypeVar('T')


class Response(BaseModel, Generic[T]):
    """统一响应模型"""
    success: bool = True
    message: Optional[str] = None
    data: Optional[T] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "操作成功",
                "data": {}
            }
        }


class ErrorResponse(BaseModel):
    """错误响应模型"""
    success: bool = False
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "资源未找到",
                "detail": "账号ID不存在",
                "code": "NOT_FOUND"
            }
        }


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应模型"""
    success: bool = True
    total: int = Field(..., description="总记录数")
    page: int = Field(1, description="当前页码")
    page_size: int = Field(20, description="每页大小")
    data: List[T] = Field(default_factory=list, description="数据列表")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "total": 100,
                "page": 1,
                "page_size": 20,
                "data": []
            }
        }


class StatusResponse(BaseModel):
    """状态响应模型"""
    success: bool
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "操作成功"
            }
        }


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "healthy"
    version: str
    timestamp: str

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "2.0.0",
                "timestamp": "2025-11-28T10:00:00"
            }
        }
