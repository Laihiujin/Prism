"""
FastAPI 主应用入口
"""
import os
import asyncio
# Force Playwright to use global browsers BEFORE any imports
# os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '0'

from fastapi import FastAPI, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from datetime import datetime
from pathlib import Path
import sys
import shutil

# Windows: Ensure ProactorEventLoopPolicy for asyncio subprocess support.
# (Playwright needs subprocess to launch browser processes.)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# 添加父目录到路径以导入现有模块
sys.path.insert(0, str(Path(__file__).parent.parent))

# 添加 OpenManus-worker 到路径（必须在导入 manus_agent 之前）
OPENMANUS_PATH = Path(__file__).parent.parent / "OpenManus-worker"
if OPENMANUS_PATH.exists() and str(OPENMANUS_PATH) not in sys.path:
    sys.path.insert(0, str(OPENMANUS_PATH))

from .core import settings, logger, setup_logging, AppException
from .schemas.common import ErrorResponse, HealthResponse
from .api.v1.router import api_router
from .api.v1.ai.router import set_ai_client
# Removed: old login router - now using V2 auth router in api.v1.auth
# from .api.login import router as login_router

# AI Service Imports
try:
    from ai_service import AIClient, ModelManager, AILogger
    AI_SERVICE_AVAILABLE = True
except ImportError:
    AI_SERVICE_AVAILABLE = False
    logger.warning("AI Service modules not found")


# 初始化日志
setup_logging()

# 创建FastAPI应用
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

@app.middleware("http")
async def _normalize_duplicated_api_prefix(request: Request, call_next):
    # Next.js rewrites may accidentally turn `/api/v1/...` into `/api/v1/v1/...`.
    path = request.scope.get("path") or ""
    if path.startswith("/api/v1/v1/"):
        request.scope["path"] = path.replace("/api/v1/v1/", "/api/v1/", 1)
    return await call_next(request)


# 配置CORS - 允许所有来源（开发环境）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，避免 CORS 问题
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# 配置静态文件服务（用于访问上传的封面图片等）
from fastapi.staticfiles import StaticFiles

# 确保上传目录存在
upload_dir = Path(settings.UPLOAD_DIR)
upload_dir.mkdir(parents=True, exist_ok=True)

# 挂载静态文件目录
app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

# Optional: mount Douyin_TikTok_API under a prefix.
if settings.DOUYIN_TIKTOK_API_ENABLED:
    try:
        douyin_root = Path(settings.BASE_DIR) / "douyin_tiktok_api"
        if douyin_root.exists():
            from douyin_tiktok_api.app.main import app as douyin_tiktok_app  # type: ignore

            app.mount(settings.DOUYIN_TIKTOK_API_PREFIX, douyin_tiktok_app)
            logger.info(f"[Douyin_TikTok_API] Mounted at {settings.DOUYIN_TIKTOK_API_PREFIX}")
        else:
            logger.warning(f"[Douyin_TikTok_API] Repo not found at {douyin_root}")
    except ImportError as exc:
        logger.warning(f"[Douyin_TikTok_API] Import failed: {exc}. Check dependencies (PyWebIO, etc.)")
    except Exception as exc:
        logger.warning(f"[Douyin_TikTok_API] Mount failed: {exc}")



# 全局异常处理
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """处理自定义应用异常"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.message,
            "detail": str(exc)
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证异常"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "请求参数验证失败",
            "detail": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """处理未捕获的异常"""
    logger.error("未处理的异常: {}", str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "服务器内部错误",
            "detail": str(exc) if settings.DEBUG else "请联系管理员"
        }
    )


# 启动和关闭事件
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info(f" {settings.PROJECT_NAME} v{settings.VERSION} loading...")
    logger.info(f" API: http://{settings.HOST}:{settings.PORT}/api/docs")
    logger.info(f" 数据库: {settings.DATABASE_PATH}")

    os.environ.setdefault("SYNAPSE_DATA_DIR", str(settings.DATA_DIR))

    def _migrate_dir(label: str, old_path: Path, new_path: Path) -> None:
        try:
            if old_path.resolve() == new_path.resolve():
                new_path.mkdir(parents=True, exist_ok=True)
                return
        except Exception:
            pass

        if not old_path.exists():
            # If data was previously moved to LOCALAPPDATA, move it back when using project data dir.
            alt_root = os.getenv("LOCALAPPDATA")
            if alt_root:
                alt_path = Path(alt_root) / "SynapseAutomation" / "data" / old_path.name
                if alt_path.exists() and not new_path.exists():
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(alt_path), str(new_path))
                    logger.info(f"[Data] Restored {label}: {alt_path} -> {new_path}")
                    return
            new_path.mkdir(parents=True, exist_ok=True)
            return

        new_path.parent.mkdir(parents=True, exist_ok=True)
        if not new_path.exists():
            shutil.move(str(old_path), str(new_path))
            logger.info(f"[Data] Moved {label}: {old_path} -> {new_path}")
            return

        # Both exist: move contents if destination is empty.
        try:
            if any(new_path.iterdir()):
                logger.warning(f"[Data] {label} exists in both locations, keeping new: {new_path}")
                return
        except Exception:
            logger.warning(f"[Data] {label} exists in both locations, keeping new: {new_path}")
            return

        moved = 0
        for item in old_path.iterdir():
            shutil.move(str(item), str(new_path / item.name))
            moved += 1
        try:
            old_path.rmdir()
        except Exception:
            pass
        logger.info(f"[Data] Moved {moved} items for {label} -> {new_path}")

    try:
        _migrate_dir("cookiesFile", Path(settings.BASE_DIR) / "cookiesFile", Path(settings.COOKIE_FILES_DIR))
        _migrate_dir("fingerprints", Path(settings.BASE_DIR) / "fingerprints", Path(settings.FINGERPRINTS_DIR))
        _migrate_dir("browser_profiles", Path(settings.BASE_DIR) / "browser_profiles", Path(settings.BROWSER_PROFILES_DIR))
    except Exception as e:
        logger.warning(f"[Data] Migration failed (continuing): {e}")

    # Ensure video directory exists in packaged/runtime environments
    try:
        Path(settings.VIDEO_FILES_DIR).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning(f"[Data] Failed to ensure videoFile dir: {e}")

    # Ensure directories exist even if data was cleaned.
    for dir_path in (
        Path(settings.COOKIE_FILES_DIR),
        Path(settings.FINGERPRINTS_DIR),
        Path(settings.BROWSER_PROFILES_DIR),
        Path(settings.VIDEO_FILES_DIR),
    ):
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"[Data] Failed to ensure dir {dir_path}: {e}")


    # Ensure local SQLite schema is initialized (fresh install / older DB compatibility)
    try:
        from fastapi_app.db.schema import ensure_main_db_schema
        from fastapi_app.db.session import main_db_pool

        with main_db_pool.get_connection() as conn:
            ensure_main_db_schema(conn)
        logger.info("[DB] Schema check completed")
    except Exception as e:
        logger.warning(f"[DB] Schema check failed (continuing): {e}")

    # If MySQL is enabled, ensure minimal tables exist (migration should still be run for data copy).
    try:
        from fastapi_app.db.runtime import mysql_enabled
        if mysql_enabled():
            from fastapi_app.db.sa_models import metadata
            from fastapi_app.db.sqlalchemy_engine import get_engine
            metadata.create_all(get_engine())
            logger.info("[DB] MySQL enabled; ensured SQLAlchemy tables exist")
    except Exception as e:
        logger.warning(f"[DB] MySQL table ensure failed (continuing): {e}")

    # Initialize task queue manager (SQLite-backed)
    try:
        from myUtils.task_queue_manager import get_task_manager

        task_db_path = Path(settings.BASE_DIR) / "db" / "task_queue.db"
        app.state.task_manager = get_task_manager(
            db_path=task_db_path,
            max_workers=settings.TASK_QUEUE_MAX_WORKERS,
        )
        logger.info(
            f"[TaskQueue] Initialized: db={task_db_path} workers={settings.TASK_QUEUE_MAX_WORKERS}"
        )
    except Exception as e:
        logger.warning(f"[TaskQueue] Init failed (tasks API disabled): {e}")

    # Ensure manual_tasks table exists (SQLite task_queue.db)
    try:
        try:
            from db.create_manual_tasks_table import create_manual_tasks_table
        except Exception:
            import importlib.util
            module_path = Path(settings.BASE_DIR) / "db" / "create_manual_tasks_table.py"
            spec = importlib.util.spec_from_file_location("create_manual_tasks_table", module_path)
            if not spec or not spec.loader:
                raise
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            create_manual_tasks_table = module.create_manual_tasks_table
        create_manual_tasks_table()
        logger.info("[TaskQueue] manual_tasks table ensured")
    except Exception as e:
        logger.warning(f"[TaskQueue] manual_tasks table init failed: {e}")

    # 初始化批量发布服务（不再需要 TaskQueueManager）
    try:
        from myUtils.batch_publish_service import get_batch_publish_service
        # 初始化服务（不再依赖任务队列）
        get_batch_publish_service()
        logger.info("Celery/Redis 发布队列已加载")
    except Exception as e:
        logger.warning(f"批量发布服务初始化失败: {e}")

    # 初始化AI服务（可选）
    if AI_SERVICE_AVAILABLE:
        try:
            logger.info("Initializing AI service...")
            ai_logger = AILogger(db_path=settings.AI_LOGS_DB_PATH)

            config_path = settings.BASE_DIR / "ai_service" / "config.json"
            ai_model_manager = ModelManager(config_path=str(config_path))

            logger.info(f"AI model manager initialized with {len(ai_model_manager.providers)} providers")
            ai_client = AIClient(ai_model_manager, ai_logger)

            # Set global AI client for router
            set_ai_client(ai_client)
            logger.info("AI服务初始化成功")
        except Exception as e:
            logger.warning(f"AI服务初始化失败（可选功能）: {e}")
    else:
        logger.warning("AI服务模块未找到，跳过初始化")


    # 初始化 OpenManus Agent（应用启动时预加载）
    try:
        from fastapi_app.agent.manus_agent import get_manus_agent
        agent = await get_manus_agent()
        app.state.manus_agent = agent
        logger.info("✅ OpenManus Agent 初始化成功")
    except Exception as e:
        logger.warning(f"OpenManus Agent 初始化失败（可选功能）: {e}")

    # 启动账号数据清理调度器（每6小时清理一次）
    try:
        from fastapi_app.core.account_cleanup_scheduler import start_cleanup_scheduler
        await start_cleanup_scheduler()
        logger.info("✅ 账号数据清理调度器已启动（每6小时清理一次）")
    except Exception as e:
        logger.warning(f"账号数据清理调度器启动失败: {e}")



@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("应用正在关闭...")

    # 停止账号数据清理调度器
    try:
        from fastapi_app.core.account_cleanup_scheduler import stop_cleanup_scheduler
        await stop_cleanup_scheduler()
        logger.info("账号数据清理调度器已停止")
    except Exception as e:
        logger.warning(f"账号数据清理调度器停止失败: {e}")

    # 清理 OpenManus Agent
    try:
        if hasattr(app.state, 'manus_agent'):
            await app.state.manus_agent.cleanup()
            logger.info("OpenManus Agent 已清理")
    except Exception as e:
        logger.warning(f"OpenManus Agent 清理失败: {e}")


    # 关闭数据库连接池
    from .db.session import main_db_pool, cookie_db_pool, ai_logs_db_pool
    main_db_pool.close_all()
    cookie_db_pool.close_all()
    ai_logs_db_pool.close_all()
    logger.info("应用已关闭")


# 根路由
@app.get("/", tags=["Root"])
async def root():
    """根路由"""
    return {
        "message": f"欢迎使用 {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "docs": "/api/docs"
    }


# 健康检查
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """健康检查接口"""
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        timestamp=datetime.now().isoformat()
    )


# 注册API路由（唯一入口）
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# 注册文件服务路由（用于素材预览）
from .api.file_service import router as file_service_router
app.include_router(file_service_router, tags=["文件服务"])

# 注册登录SSE路由（已迁移到V2 auth router）
# Removed: old login router - now in /api/v1/auth
# app.include_router(login_router, prefix="/api", tags=["登录绑定"])


# 开发模式运行
if __name__ == "__main__":
    # Fix: Apply Playwright Windows Event Loop Policy for direct run
    try:
        from myUtils.playwright_windows_fix import setup_windows_playwright_policy
        setup_windows_playwright_policy()
    except ImportError:
        pass

    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
