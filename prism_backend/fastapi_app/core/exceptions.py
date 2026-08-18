"""
自定义异常类
"""
from fastapi import HTTPException, status


class AppException(Exception):
    """应用基础异常"""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundException(AppException):
    """资源未找到异常"""
    def __init__(self, message: str = "资源未找到"):
        super().__init__(message, status_code=404)


class BadRequestException(AppException):
    """错误请求异常"""
    def __init__(self, message: str = "请求参数错误"):
        super().__init__(message, status_code=400)


class UnauthorizedException(AppException):
    """未授权异常"""
    def __init__(self, message: str = "未授权访问"):
        super().__init__(message, status_code=401)


class ForbiddenException(AppException):
    """禁止访问异常"""
    def __init__(self, message: str = "禁止访问"):
        super().__init__(message, status_code=403)


class ConflictException(AppException):
    """资源冲突异常"""
    def __init__(self, message: str = "资源冲突"):
        super().__init__(message, status_code=409)


class ValidationException(AppException):
    """数据验证异常"""
    def __init__(self, message: str = "数据验证失败"):
        super().__init__(message, status_code=422)


class InternalServerException(AppException):
    """服务器内部错误"""
    def __init__(self, message: str = "服务器内部错误"):
        super().__init__(message, status_code=500)
