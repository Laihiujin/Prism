"""
登录认证相关的数据模型
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum


class PlatformType(str, Enum):
    """支持的平台类型"""
    BILIBILI = "bilibili"
    XIAOHONGSHU = "xiaohongshu"
    DOUYIN = "douyin"
    KUAISHOU = "kuaishou"
    TENCENT = "tencent"
    YOUTUBE = "youtube"


class LoginMethod(str, Enum):
    """登录方式"""
    QRCODE = "qrcode"
    SMS = "sms"
    PASSWORD = "password"


class QRCodeResponse(BaseModel):
    """二维码响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    qr_id: str = Field(..., description="二维码唯一标识")
    qr_image: str = Field(..., description="二维码图片（base64或URL）")
    expires_in: Optional[int] = Field(default=300, description="过期时间（秒）")


class LoginStatusResponse(BaseModel):
    """登录状态响应"""
    success: bool = Field(..., description="是否成功")
    status: Literal["waiting", "scanned", "confirmed", "expired", "failed"] = Field(..., description="登录状态")
    message: str = Field(default="", description="状态描述")
    data: Optional[dict] = Field(default=None, description="额外数据")


class LoginRequest(BaseModel):
    """登录请求"""
    platform: PlatformType = Field(..., description="平台类型")
    account_id: str = Field(..., description="账号ID（用于保存cookie）")
    method: LoginMethod = Field(default=LoginMethod.QRCODE, description="登录方式")


class VerificationCodeRequest(BaseModel):
    """验证码提交请求"""
    session_id: str = Field(..., description="登录会话ID")
    code: str = Field(..., description="验证码")


class CookieInfo(BaseModel):
    """Cookie信息"""
    platform: str = Field(..., description="平台名称")
    account_id: str = Field(..., description="账号ID")
    user_id: Optional[str] = Field(default=None, description="用户UID")
    username: Optional[str] = Field(default=None, description="用户昵称")
    avatar: Optional[str] = Field(default=None, description="头像URL")
    status: Literal["valid", "expired", "invalid"] = Field(..., description="Cookie状态")
    created_at: Optional[str] = Field(default=None, description="创建时间")
    expires_at: Optional[str] = Field(default=None, description="过期时间")


class LoginResult(BaseModel):
    """登录结果"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    cookie_info: Optional[CookieInfo] = Field(default=None, description="Cookie信息")
