"""
登录服务版本切换配置

设置 USE_V2_LOGIN_SERVICES = True 启用新版适配器
设置为 False 使用旧版实现
"""

# 全局开关: 是否使用V2版本的登录服务
USE_V2_LOGIN_SERVICES = True

# 平台级别开关 (可以逐平台切换)
PLATFORM_V2_SWITCHES = {
    "bilibili": True,      # B站使用V2 (已验证)
    "douyin": True,        # 抖音使用V2 (复制自正确实现)
    "kuaishou": True,      # 快手使用V2 (复制自正确实现)
    "xiaohongshu": True,   # 小红书使用V2 (复制自正确实现)
    "tencent": True,       # 视频号使用V2 (复制自正确实现)
}


def should_use_v2_service(platform: str) -> bool:
    """
    判断是否应该使用V2服务

    Args:
        platform: 平台名称 (bilibili/douyin/kuaishou/xiaohongshu/tencent)

    Returns:
        bool: True使用V2, False使用旧版
    """
    if not USE_V2_LOGIN_SERVICES:
        return False

    return PLATFORM_V2_SWITCHES.get(platform.lower(), False)
