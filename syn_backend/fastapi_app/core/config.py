"""
配置管理模块
使用 pydantic-settings 管理环境变量和配置
"""
from pydantic_settings import BaseSettings
import os
from typing import List
from pathlib import Path


def _is_dev_repo(base_dir: Path) -> bool:
    env = (os.getenv("SYNAPSE_ENV") or os.getenv("NODE_ENV") or "").strip().lower()
    if env in ("dev", "development", "local"):
        return True
    try:
        return (base_dir.parent / ".git").exists()
    except Exception:
        return False


def _has_data_payload(root: Path) -> bool:
    try:
        for name in ("cookiesFile", "fingerprints", "browser_profiles", "db"):
            if (root / name).exists():
                return True
    except Exception:
        return False
    return False


def _resolve_default_data_dir(base_dir: Path) -> Path:
    env_dir = os.getenv("SYNAPSE_DATA_DIR")
    if env_dir:
        return Path(env_dir)

    if _is_dev_repo(base_dir):
        return base_dir

    candidates = []
    appdata = os.getenv("APPDATA")
    localappdata = os.getenv("LOCALAPPDATA")
    if appdata:
        candidates.append(Path(appdata) / "SynapseAutomation" / "data")
    if localappdata and localappdata != appdata:
        candidates.append(Path(localappdata) / "SynapseAutomation" / "data")

    for candidate in candidates:
        if _has_data_payload(candidate):
            return candidate

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return base_dir


class Settings(BaseSettings):
    """应用配置类"""

    # 项目信息
    PROJECT_NAME: str = "SynapseAutomation"
    VERSION: str = "2.0.0"
    DESCRIPTION: str = "矩阵平台自动化发布系统"
    API_V1_PREFIX: str = "/api/v1"

    # 时区配置
    TIMEZONE: str = "Asia/Shanghai"  # 北京时间 UTC+8
    USE_BEIJING_TIME: bool = True  # 全局使用北京时间

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 7000  # FastAPI专用端口
    DEBUG: bool = False

    # CORS配置
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",  # Vite开发服务器
    ]

    # 路径配置
    BASE_DIR: Path = Path(__file__).parent.parent.parent

    # 数据库路径
    DATABASE_PATH: str = str(BASE_DIR / "db" / "database.db")
    COOKIE_DB_PATH: str = str(BASE_DIR / "db" / "cookie_store.db")
    AI_LOGS_DB_PATH: str = str(BASE_DIR / "db" / "ai_logs.db")

    # Database URL (optional): enable MySQL by setting e.g. mysql+pymysql://user:pass@localhost:3306/synapse?charset=utf8mb4
    # When empty, the app uses SQLite files above.
    DATABASE_URL: str = ""

    # Redis / Celery (optional)
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = ""  # defaults to REDIS_URL when empty
    CELERY_RESULT_BACKEND: str = ""  # defaults to REDIS_URL when empty

    # 文件存储路径
    DATA_DIR: str = str(_resolve_default_data_dir(BASE_DIR))
    COOKIE_FILES_DIR: str = str(Path(DATA_DIR) / "cookiesFile")
    FINGERPRINTS_DIR: str = str(Path(DATA_DIR) / "fingerprints")
    BROWSER_PROFILES_DIR: str = str(Path(DATA_DIR) / "browser_profiles")
    VIDEO_FILES_DIR: str = str(BASE_DIR / "videoFile")
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")

    # 任务队列配置
    TASK_QUEUE_MAX_WORKERS: int = 3  # 并发任务数（降低资源占用）
    TASK_MAX_RETRIES: int = 3

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = str(BASE_DIR / "logs" / "fastapi_app.log")

    # 安全配置（可选）
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24小时
    
    # AI 服务配置
    SILICONFLOW_API_KEY: str = ""  # 硅基流动 API Key（请通过环境变量注入）
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    DEEPSEEK_OCR_MODEL: str = "deepseek-ai/DeepSeek-OCR"
    SILICONFLOW_PROMPT_MODEL: str = "Qwen/Qwen2.5-VL-72B-Instruct"
    SILICONFLOW_IMAGE_MODEL: str = "Qwen/Qwen-Image-Edit-2509"

    # Legacy AI env fallback (when ai_model_configs is not configured)
    AI_API_KEY: str = ""
    AI_BASE_URL: str = ""
    AI_MODEL: str = ""


    # Optional: Douyin_TikTok_API integration
    DOUYIN_TIKTOK_API_ENABLED: bool = True
    DOUYIN_TIKTOK_API_PREFIX: str = "/api/v1/douyin-tiktok"


    class Config:
        # Prefer repo-root `.env` as the single source of truth.
        env_file = (str(Path(__file__).resolve().parent.parent.parent / ".env"),)
        case_sensitive = True
        extra = "ignore"  # 忽略额外的环境变量


# 创建全局配置实例
settings = Settings()


def resolved_celery_broker_url() -> str:
    return (settings.CELERY_BROKER_URL or settings.REDIS_URL).strip()


def resolved_celery_result_backend() -> str:
    return (settings.CELERY_RESULT_BACKEND or settings.REDIS_URL).strip()
