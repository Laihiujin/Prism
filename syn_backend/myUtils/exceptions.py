"""
自定义异常类
"""

class CaptchaRequiredException(Exception):
    """需要验证码异常"""
    def __init__(self, message="需要人工处理验证码", account_id=None, platform=None):
        self.message = message
        self.account_id = account_id
        self.platform = platform
        super().__init__(self.message)

class AccountBlockedException(Exception):
    """账号被封禁异常"""
    def __init__(self, message="账号已被封禁", account_id=None, platform=None):
        self.message = message
        self.account_id = account_id
        self.platform = platform
        super().__init__(self.message)

class NetworkErrorException(Exception):
    """网络错误异常"""
    def __init__(self, message="网络连接失败", details=None):
        self.message = message
        self.details = details
        super().__init__(self.message)
