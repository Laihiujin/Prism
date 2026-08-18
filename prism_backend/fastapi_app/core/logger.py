"""
日志配置模块
使用 loguru 提供更好的日志体验
"""
import sys
from pathlib import Path
from loguru import logger
from .config import settings


def setup_logging():
    """配置日志系统"""

    # 移除默认的handler
    logger.remove()

    # 添加控制台输出
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        level=settings.LOG_LEVEL
    )

    # 添加文件输出
    log_path = Path(settings.LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        settings.LOG_FILE,
        rotation="100 MB",  # 日志文件达到100MB时轮转
        retention="30 days",  # 保留30天
        compression="zip",  # 压缩旧日志
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=settings.LOG_LEVEL,
        enqueue=True  # 异步写入
    )

    logger.info("日志系统初始化完成")


# 导出logger供其他模块使用
__all__ = ["logger", "setup_logging"]
