"""
时区工具模块 - 统一处理所有时间相关操作
确保系统所有时间都使用北京时间（UTC+8）
"""
from datetime import datetime, timezone, timedelta
from typing import Optional
import pytz

# 北京时区
BEIJING_TZ = pytz.timezone('Asia/Shanghai')
UTC_TZ = pytz.UTC


def now_beijing() -> datetime:
    """
    获取当前北京时间（带时区信息）

    Returns:
        datetime: 当前北京时间

    Example:
        >>> dt = now_beijing()
        >>> print(dt)  # 2025-01-15 10:30:00+08:00
    """
    return datetime.now(BEIJING_TZ)


def now_beijing_naive() -> datetime:
    """
    获取当前北京时间（不带时区信息，用于与数据库兼容）

    Returns:
        datetime: 当前北京时间（naive）

    Example:
        >>> dt = now_beijing_naive()
        >>> print(dt)  # 2025-01-15 10:30:00
    """
    return datetime.now(BEIJING_TZ).replace(tzinfo=None)


def to_beijing(dt: datetime) -> datetime:
    """
    将任意时区的时间转换为北京时间

    Args:
        dt: 原始时间（可以是 naive 或 aware）

    Returns:
        datetime: 北京时间

    Example:
        >>> utc_time = datetime.now(timezone.utc)
        >>> beijing_time = to_beijing(utc_time)
    """
    if dt is None:
        return None

    # 如果是 naive datetime，假设它是 UTC 时间
    if dt.tzinfo is None:
        dt = UTC_TZ.localize(dt)

    # 转换到北京时区
    return dt.astimezone(BEIJING_TZ)


def to_utc(dt: datetime) -> datetime:
    """
    将北京时间转换为 UTC 时间

    Args:
        dt: 北京时间

    Returns:
        datetime: UTC 时间
    """
    if dt is None:
        return None

    # 如果是 naive datetime，假设它是北京时间
    if dt.tzinfo is None:
        dt = BEIJING_TZ.localize(dt)

    # 转换到 UTC
    return dt.astimezone(UTC_TZ)


def format_beijing_time(dt: Optional[datetime], fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化北京时间为字符串

    Args:
        dt: 时间对象
        fmt: 格式字符串

    Returns:
        str: 格式化后的时间字符串

    Example:
        >>> dt = now_beijing()
        >>> format_beijing_time(dt)
        '2025-01-15 10:30:00'
    """
    if dt is None:
        return ""

    # 确保时间是北京时区
    beijing_dt = to_beijing(dt)
    return beijing_dt.strftime(fmt)


def parse_datetime_to_beijing(dt_str: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """
    解析字符串为北京时间

    Args:
        dt_str: 时间字符串
        fmt: 格式字符串

    Returns:
        datetime: 北京时间（带时区）

    Example:
        >>> dt = parse_datetime_to_beijing("2025-01-15 10:30:00")
        >>> print(dt)  # 2025-01-15 10:30:00+08:00
    """
    naive_dt = datetime.strptime(dt_str, fmt)
    return BEIJING_TZ.localize(naive_dt)


def get_date_range_beijing(days_ago: int = 0) -> tuple[datetime, datetime]:
    """
    获取北京时间的日期范围（用于查询）

    Args:
        days_ago: 多少天前（0 = 今天）

    Returns:
        tuple: (开始时间, 结束时间)

    Example:
        >>> start, end = get_date_range_beijing(1)  # 昨天的范围
        >>> print(start)  # 2025-01-14 00:00:00+08:00
        >>> print(end)    # 2025-01-14 23:59:59+08:00
    """
    now = now_beijing()
    target_date = now - timedelta(days=days_ago)

    start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    return start, end


# 兼容性函数：替代 datetime.now() 和 datetime.utcnow()
def datetime_now():
    """
    替代 datetime.now()，返回北京时间（naive）
    用于快速替换现有代码
    """
    return now_beijing_naive()


def datetime_utcnow():
    """
    替代 datetime.utcnow()，返回北京时间（naive）
    避免使用 UTC 时间，统一使用北京时间
    """
    return now_beijing_naive()


# ISO 格式时间处理
def now_beijing_iso() -> str:
    """
    获取当前北京时间的 ISO 格式字符串

    Returns:
        str: ISO 格式时间字符串

    Example:
        >>> now_beijing_iso()
        '2025-01-15T10:30:00+08:00'
    """
    return now_beijing().isoformat()


def from_timestamp_beijing(timestamp: float) -> datetime:
    """
    从 Unix 时间戳创建北京时间

    Args:
        timestamp: Unix 时间戳（秒）

    Returns:
        datetime: 北京时间
    """
    utc_dt = datetime.fromtimestamp(timestamp, tz=UTC_TZ)
    return utc_dt.astimezone(BEIJING_TZ)


# 常用时间格式
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"
DATETIME_FORMAT_CN = "%Y年%m月%d日 %H:%M:%S"
