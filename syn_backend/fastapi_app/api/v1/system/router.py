"""
系统维护与工具 API 路由
将原本的脚本功能通过 FastAPI 接口暴露
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

# 导入子路由
from .browser_profiles import router as browser_profiles_router

router = APIRouter(prefix="/system", tags=["系统维护"])

# 注册子路由
router.include_router(browser_profiles_router)

# 脚本路径配置
SCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / "scripts"


class SyncDatabaseRequest(BaseModel):
    """数据库同步请求"""
    force: bool = False


class ConfigCheckResponse(BaseModel):
    """配置检查响应"""
    status: str
    issues: list[str]
    recommendations: list[str]


@router.post("/sync-database", summary="同步数据库")
async def sync_database(request: SyncDatabaseRequest, background_tasks: BackgroundTasks):
    """
    执行数据库同步操作
    原脚本: syn_backend/sync_db_files.py
    """
    try:
        # 导入同步逻辑
        from myUtils.db_sync import sync_databases

        # 在后台执行同步
        background_tasks.add_task(
            sync_databases,
            force=request.force
        )

        return {
            "status": "success",
            "message": "数据库同步任务已启动",
            "task_id": "sync_db_" + str(asyncio.current_task().get_name())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.get("/check-config", response_model=ConfigCheckResponse, summary="检查系统配置")
async def check_config():
    """
    检查系统配置完整性
    原脚本: syn_backend/check_config.py
    """
    try:
        issues = []
        recommendations = []
        
        # 检查环境变量
        from fastapi_app.core.config import settings
        
        # 检查数据库文件
        db_files = [
            settings.DATABASE_PATH,
            settings.COOKIE_DB_PATH,
            settings.AI_LOGS_DB_PATH
        ]
        
        for db_file in db_files:
            if not Path(db_file).exists():
                issues.append(f"数据库文件不存在: {db_file}")
        
        # 检查必要目录
        required_dirs = [
            settings.COOKIE_FILES_DIR,
            settings.VIDEO_FILES_DIR,
            settings.UPLOAD_DIR
        ]
        
        for dir_path in required_dirs:
            if not Path(dir_path).exists():
                issues.append(f"目录不存在: {dir_path}")
                recommendations.append(f"创建目录: mkdir -p {dir_path}")
        
        # 检查 Playwright Worker（浏览器自动化已进程级解耦）
        try:
            import httpx
            resp = httpx.get("http://127.0.0.1:7001/health", timeout=3.0)
            resp.raise_for_status()
            browser_ok = resp.json().get("status") == "ok"
        except Exception:
            browser_ok = False

        if not browser_ok:
            issues.append("Playwright Worker 未运行或不可用")
            recommendations.append("运行: scripts/launchers/start_worker.bat (Windows) 或 python syn_backend/playwright_worker/worker.py")
        
        status = "healthy" if not issues else "warning"
        
        return ConfigCheckResponse(
            status=status,
            issues=issues,
            recommendations=recommendations
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置检查失败: {str(e)}")


@router.post("/manual-sync", summary="手动触发账号同步")
async def manual_sync(background_tasks: BackgroundTasks):
    """
    手动触发账号Cookie同步
    原脚本: syn_backend/manual_sync.py
    """
    try:
        from myUtils.cookie_manager import cookie_manager
        
        # 在后台执行同步
        async def sync_task():
            accounts = cookie_manager.list_flat_accounts()
            results = []
            
            for account in accounts:
                if account['status'] == 'valid':
                    try:
                        # 验证并更新Cookie
                        result = await cookie_manager.verify_account(account['account_id'])
                        results.append({
                            "account_id": account['account_id'],
                            "status": "success" if result else "failed"
                        })
                    except Exception as e:
                        results.append({
                            "account_id": account['account_id'],
                            "status": "error",
                            "error": str(e)
                        })
            
            return results
        
        background_tasks.add_task(sync_task)
        
        return {
            "status": "success",
            "message": "账号同步任务已启动"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.get("/inspect-biliup", summary="检查 Biliup 配置")
async def inspect_biliup():
    """
    检查 Biliup 上传工具配置
    原脚本: syn_backend/inspect_biliup.py
    """
    try:
        import importlib.util
        
        # 检查 biliup 是否安装
        biliup_spec = importlib.util.find_spec("biliup")
        
        if biliup_spec is None:
            return {
                "status": "not_installed",
                "message": "Biliup 未安装",
                "recommendation": "pip install biliup"
            }
        
        # 检查配置文件
        config_path = Path.home() / ".biliup" / "config.json"
        
        return {
            "status": "installed",
            "version": "检测中",
            "config_exists": config_path.exists(),
            "config_path": str(config_path)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查失败: {str(e)}")


@router.post("/cleanup-old-files", summary="清理旧文件")
async def cleanup_old_files(days: int = 30):
    """
    清理指定天数前的临时文件和日志
    """
    try:
        from datetime import datetime, timedelta
        import os
        
        cutoff_date = datetime.now() - timedelta(days=days)
        cleaned_files = []
        
        # 清理临时上传文件
        from fastapi_app.core.config import settings
        upload_dir = Path(settings.UPLOAD_DIR)
        
        if upload_dir.exists():
            for file in upload_dir.rglob("*"):
                if file.is_file():
                    file_mtime = datetime.fromtimestamp(file.stat().st_mtime)
                    if file_mtime < cutoff_date:
                        try:
                            file.unlink()
                            cleaned_files.append(str(file))
                        except Exception:
                            pass
        
        return {
            "status": "success",
            "cleaned_count": len(cleaned_files),
            "files": cleaned_files[:10]  # 只返回前10个
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")


@router.get("/health-check", summary="系统健康检查")
async def system_health_check():
    """
    全面的系统健康检查
    """
    try:
        health_status = {
            "database": "unknown",
            "browser": "unknown",
            "ai_service": "unknown",
            "disk_space": "unknown"
        }
        
        # 检查数据库连接
        try:
            from fastapi_app.db.session import main_db_pool
            with main_db_pool.get_connection() as conn:
                conn.execute("SELECT 1")
            health_status["database"] = "healthy"
        except Exception:
            health_status["database"] = "unhealthy"
        
        # 检查浏览器（通过 Playwright Worker）
        try:
            import httpx
            resp = httpx.get("http://127.0.0.1:7001/health", timeout=3.0)
            resp.raise_for_status()
            health_status["browser"] = "healthy" if resp.json().get("status") == "ok" else "unhealthy"
        except Exception:
            health_status["browser"] = "unhealthy"
        
        # 检查 AI 服务
        try:
            from ai_service import AIClient
            health_status["ai_service"] = "healthy"
        except Exception:
            health_status["ai_service"] = "not_available"
        
        # 检查磁盘空间
        try:
            import shutil
            from fastapi_app.core.config import settings
            total, used, free = shutil.disk_usage(settings.BASE_DIR)
            free_gb = free // (2**30)
            health_status["disk_space"] = f"{free_gb}GB free"
        except Exception:
            health_status["disk_space"] = "unknown"
        
        overall_status = "healthy" if all(
            v in ["healthy", "not_available"] or "GB" in str(v)
            for v in health_status.values()
        ) else "degraded"
        
        return {
            "status": overall_status,
            "components": health_status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")


@router.get("/playwright-worker/health", summary="Playwright Worker 健康信息")
async def playwright_worker_health():
    """代理 Worker 的 /health（便于在 API Docs 里一键检查）。"""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://127.0.0.1:7001/health")
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Worker health failed: {str(e) or type(e).__name__}")


@router.get("/playwright-worker/debug/playwright", summary="调试 Playwright 启动")
async def playwright_worker_debug_playwright(headless: bool = True):
    """
    代理 Worker 的 /debug/playwright（用于定位 Playwright/浏览器环境问题）。

    说明：Worker 需要已启动在 7001 端口。
    """
    try:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get("http://127.0.0.1:7001/debug/playwright", params={"headless": headless})
            if resp.status_code >= 400:
                # 尽量透传 Worker 的报错
                try:
                    payload = resp.json()
                except Exception:
                    payload = {"success": False, "error": resp.text}
                raise HTTPException(status_code=502, detail=payload)
            return resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Worker debug failed: {str(e) or type(e).__name__}")


@router.get("/build", summary="构建/导入信息（调试）")
async def build_info():
    """用于确认实际运行的代码版本与模块导入来源（排查"改了代码但没生效"）。"""
    try:
        import importlib
        import sys
        import time
        from pathlib import Path

        def file_meta(path: str):
            try:
                p = Path(path)
                stat = p.stat()
                return {
                    "path": str(p),
                    "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                    "size": stat.st_size,
                }
            except Exception:
                return {"path": path}

        auth_router = importlib.import_module("fastapi_app.api.v1.auth.router")
        worker_client = importlib.import_module("playwright_worker.client")

        return {
            "python": sys.version.split(" ")[0],
            "sys_path_0": sys.path[0] if sys.path else None,
            "system_router": file_meta(__file__),
            "auth_router": file_meta(getattr(auth_router, "__file__", "unknown")),
            "playwright_worker_client": file_meta(getattr(worker_client, "__file__", "unknown")),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"build info failed: {str(e) or type(e).__name__}")


# ========== Electron 设置页面专用端点 ==========

@router.post("/clear-materials", summary="清除素材数据")
async def clear_materials():
    """清除所有素材数据（文件与记录）"""
    try:
        from fastapi_app.core.config import settings
        import shutil

        # 清除素材文件
        materials_dir = Path(settings.VIDEO_FILES_DIR)
        if materials_dir.exists():
            shutil.rmtree(materials_dir)
            materials_dir.mkdir(parents=True, exist_ok=True)

        # 清除素材记录
        from fastapi_app.db.session import main_db_pool
        with main_db_pool.get_connection() as conn:
            conn.execute("DELETE FROM file_records")
            conn.commit()

        return {
            "status": "success",
            "message": "Materials cleared."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除失败: {str(e)}")


@router.post("/clear-accounts", summary="清除账号与 Cookies")
async def clear_accounts():
    """清除所有账号与 Cookies 数据"""
    try:
        from fastapi_app.core.config import settings
        import shutil

        # 清除 Cookie/指纹/浏览器配置目录
        cookie_dir = Path(settings.COOKIE_FILES_DIR)
        fingerprints_dir = Path(settings.FINGERPRINTS_DIR)
        profiles_dir = Path(settings.BROWSER_PROFILES_DIR)

        for target_dir in (cookie_dir, fingerprints_dir, profiles_dir):
            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)

        # 清空 Cookie 账号表
        from fastapi_app.db.session import cookie_db_pool
        with cookie_db_pool.get_connection() as cookie_conn:
            cookie_conn.execute("DELETE FROM cookie_accounts")
            cookie_conn.commit()

        return {
            "status": "success",
            "message": "Accounts and cookies cleared."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除失败: {str(e)}")


@router.post("/restart-frontend", summary="Restart frontend")
async def restart_frontend():
    """Restart the frontend service via launcher script."""
    try:
        script_path = SCRIPTS_DIR / "launchers" / "start_frontend.bat"
        if not script_path.exists():
            raise HTTPException(status_code=404, detail=f"Launcher not found: {script_path}")

        subprocess.Popen(
            ["cmd", "/c", "start", "", str(script_path)],
            cwd=str(script_path.parent)
        )

        return {
            "status": "success",
            "message": "Frontend restart triggered."
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"restart frontend failed: {str(e)}")


@router.post("/clear-browser", summary="清除浏览器数据")
async def clear_browser():
    """清除 Electron 浏览器的所有缓存、历史记录和临时数据"""
    try:
        # 这个接口返回成功，实际清理由 Electron 主进程完成
        # 因为浏览器数据存储在 Electron 的 userData 目录中

        return {
            "status": "success",
            "message": "浏览器数据清理请求已接收，需要重启应用生效"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")


@router.post("/clear-cache", summary="清除所有缓存")
async def clear_cache():
    """清除应用程序的所有缓存数据"""
    try:
        from fastapi_app.core.config import settings
        import shutil

        # 清理临时上传目录
        upload_dir = Path(settings.UPLOAD_DIR)
        if upload_dir.exists():
            for item in upload_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)

        # 清理其他缓存目录
        cache_dirs = [
            Path(settings.BASE_DIR) / "cache",
            Path(settings.BASE_DIR) / "temp",
            Path(settings.BASE_DIR) / ".cache"
        ]

        for cache_dir in cache_dirs:
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
                cache_dir.mkdir(parents=True, exist_ok=True)

        return {
            "status": "success",
            "message": "所有缓存已清理"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")


@router.post("/self-check", summary="运行系统自检")
async def run_self_check():
    """运行系统自检，验证所有组件状态"""
    try:
        issues = []

        # 检查数据库
        try:
            from fastapi_app.db.session import main_db_pool
            with main_db_pool.get_connection() as conn:
                conn.execute("SELECT 1")
        except Exception as e:
            issues.append(f"数据库连接失败: {str(e)}")

        # 检查 Playwright Worker
        try:
            import httpx
            resp = httpx.get("http://127.0.0.1:7001/health", timeout=3.0)
            if resp.status_code != 200:
                issues.append("Playwright Worker 不可用")
        except Exception:
            issues.append("Playwright Worker 未运行")

        # 检查必要目录
        from fastapi_app.core.config import settings
        required_dirs = [
            settings.COOKIE_FILES_DIR,
            settings.VIDEO_FILES_DIR,
            settings.UPLOAD_DIR
        ]

        for dir_path in required_dirs:
            if not Path(dir_path).exists():
                issues.append(f"目录不存在: {dir_path}")

        # 检查磁盘空间
        try:
            import shutil
            total, used, free = shutil.disk_usage(settings.BASE_DIR)
            free_gb = free // (2**30)
            if free_gb < 5:
                issues.append(f"磁盘空间不足: 仅剩 {free_gb}GB")
        except Exception as e:
            issues.append(f"无法检查磁盘空间: {str(e)}")

        if issues:
            return {
                "status": "warning",
                "message": "发现问题",
                "issues": issues
            }
        else:
            return {
                "status": "success",
                "message": "系统自检通过，一切正常",
                "issues": []
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"自检失败: {str(e)}")


@router.post("/export-logs", summary="导出日志")
async def export_logs():
    """导出系统日志为 ZIP 文件"""
    try:
        from fastapi_app.core.config import settings
        from fastapi.responses import FileResponse
        import zipfile
        from datetime import datetime
        import tempfile

        # 创建临时 ZIP 文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_path = Path(tempfile.gettempdir()) / f"synapse_logs_{timestamp}.zip"

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 收集日志文件
            log_dirs = [
                Path(settings.BASE_DIR) / "logs",
                Path(settings.BASE_DIR) / "playwright_worker" / "logs",
                Path(settings.BASE_DIR) / "syn_backend" / "logs"
            ]

            for log_dir in log_dirs:
                if log_dir.exists():
                    for log_file in log_dir.rglob("*.log"):
                        arcname = str(log_file.relative_to(settings.BASE_DIR))
                        zipf.write(log_file, arcname)

        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=f"synapse_logs_{timestamp}.zip"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/logs", summary="查看日志")
async def view_logs(lines: int = 100):
    """查看日志内容"""
    try:
        from fastapi_app.core.config import settings

        log_candidates = [
            Path(settings.LOG_FILE),
            Path(settings.BASE_DIR) / "logs" / "app.log",
            Path(settings.BASE_DIR) / "logs" / "backend.log",
            Path(settings.BASE_DIR) / "logs" / "fastapi_app.log",
            Path(settings.BASE_DIR).parent / "resources" / "supervisor" / "backend.log",
            Path(settings.BASE_DIR).parent / "supervisor" / "backend.log",
        ]
        log_file = next((p for p in log_candidates if p.exists()), None)

        if not log_file:
            return {
                "status": "not_found",
                "message": "No log file found.",
                "candidates": [str(p) for p in log_candidates],
            }

        # 读取最近 N 行
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        return {
            "status": "success",
            "lines": recent_lines,
            "total_lines": len(all_lines),
            "log_file": str(log_file)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取日志失败: {str(e)}")


# ========== Supervisor 进程控制 ==========

import aiohttp
import os

SUPERVISOR_API_URL = os.getenv("SUPERVISOR_API_URL", "http://127.0.0.1:7002/api")


async def call_supervisor_api(endpoint: str, method: str = "GET") -> Dict[str, Any]:
    """调用 Supervisor API"""
    url = f"{SUPERVISOR_API_URL}{endpoint}"

    try:
        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        text = await resp.text()
                        raise HTTPException(status_code=resp.status, detail=f"Supervisor API error: {text}")
            elif method == "POST":
                async with session.post(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        text = await resp.text()
                        raise HTTPException(status_code=resp.status, detail=f"Supervisor API error: {text}")
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        # 检查是否在 Electron 环境中
        is_electron = os.path.exists(os.path.join(os.path.dirname(__file__), "../../../../../app.asar"))

        if is_electron:
            # 在 Electron 环境中，返回提示信息而不是错误
            return {
                "status": "unavailable",
                "message": "在 Electron 环境中,请使用 Electron 提供的系统控制功能",
                "electron_mode": True,
                "detail": "Supervisor HTTP API 在打包版本中不可用,进程由 Electron 主进程管理"
            }
        else:
            # 在非 Electron 环境中，返回真实错误
            raise HTTPException(
                status_code=503,
                detail=f"无法连接到 Supervisor (http://127.0.0.1:7002): {str(e)}"
            )


@router.get("/supervisor/status", summary="获取 Supervisor 服务状态")
async def get_supervisor_status():
    """
    获取 Supervisor 管理的所有服务状态
    """
    result = await call_supervisor_api("/status")
    return result


@router.get("/supervisor/health", summary="Supervisor 健康检查")
async def supervisor_health():
    """
    检查 Supervisor 是否在线
    """
    result = await call_supervisor_api("/health")
    return result


@router.post("/supervisor/start", summary="启动所有服务")
async def start_all_services():
    """
    通过 Supervisor 启动所有后端服务
    """
    result = await call_supervisor_api("/start", method="POST")
    return result


@router.post("/supervisor/stop", summary="停止所有服务")
async def stop_all_services():
    """
    通过 Supervisor 停止所有后端服务
    """
    result = await call_supervisor_api("/stop", method="POST")
    return result


@router.post("/supervisor/restart", summary="重启所有服务")
async def restart_all_services():
    """
    通过 Supervisor 重启所有后端服务
    """
    result = await call_supervisor_api("/restart", method="POST")
    return result


@router.post("/supervisor/restart/{service_name}", summary="重启单个服务")
async def restart_service(service_name: str):
    """
    重启指定的服务
    可用服务: backend, playwright-worker, celery-worker
    """
    result = await call_supervisor_api(f"/restart/{service_name}", method="POST")
    return result


@router.post("/clear-video-data", summary="清除所有视频数据")
async def clear_video_data():
    """清除所有视频文件和分析数据"""
    try:
        from fastapi_app.core.config import settings
        import shutil

        # 清理视频文件目录
        video_dir = Path(settings.VIDEO_FILES_DIR)
        if video_dir.exists():
            shutil.rmtree(video_dir)
            video_dir.mkdir(parents=True, exist_ok=True)

        # 清理数据库中的视频分析数据（如果表存在）
        try:
            from fastapi_app.db.session import main_db_pool
            with main_db_pool.get_connection() as conn:
                cursor = conn.cursor()
                # 检查表是否存在再删除
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='video_analytics'")
                if cursor.fetchone():
                    conn.execute("DELETE FROM video_analytics")

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='analytics_history'")
                if cursor.fetchone():
                    conn.execute("DELETE FROM analytics_history")

                conn.commit()
        except Exception as db_error:
            # 数据库清理失败不应阻止文件清理
            logger.warning(f"数据库清理失败（可忽略）: {db_error}")

        return {
            "status": "success",
            "message": "所有视频数据已清理"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")


# ========== 账号数据一致性清理 ==========

@router.post("/cleanup-account-data", summary="手动触发账号数据清理")
async def trigger_account_cleanup():
    """
    手动触发账号数据一致性清理
    清理 cookiesFile、fingerprints、browser_profiles 中与前端账号不一致的数据
    """
    try:
        from fastapi_app.core.account_cleanup_scheduler import get_scheduler

        scheduler = get_scheduler()
        result = await scheduler.trigger_manual_cleanup()

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")


@router.get("/cleanup-scheduler/status", summary="获取清理调度器状态")
async def get_cleanup_scheduler_status():
    """
    获取账号数据清理调度器的状态信息
    包括运行状态、上次清理时间、下次清理时间等
    """
    try:
        from fastapi_app.core.account_cleanup_scheduler import get_scheduler

        scheduler = get_scheduler()
        status = scheduler.get_status()

        return {
            "status": "success",
            "data": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


# ========== 路径诊断 ==========

@router.get("/diagnostic/paths", summary="诊断数据路径")
async def diagnostic_paths():
    """
    诊断并显示所有关键数据路径
    帮助排查打包后路径找不到的问题
    """
    import os
    from fastapi_app.core.config import settings
    from myUtils.cookie_manager import cookie_manager
    from myUtils.profile_manager import _resolve_profiles_dir, _resolve_fingerprints_dir

    paths_info = {
        "environment": {
            "SYNAPSE_DATA_DIR": os.getenv("SYNAPSE_DATA_DIR"),
            "LOCALAPPDATA": os.getenv("LOCALAPPDATA"),
        },
        "settings_config": {
            "BASE_DIR": str(settings.BASE_DIR),
            "DATA_DIR": str(settings.DATA_DIR),
            "DATABASE_PATH": str(settings.DATABASE_PATH),
            "COOKIE_DB_PATH": str(settings.COOKIE_DB_PATH),
            "COOKIE_FILES_DIR": str(settings.COOKIE_FILES_DIR),
            "FINGERPRINTS_DIR": str(settings.FINGERPRINTS_DIR),
            "BROWSER_PROFILES_DIR": str(settings.BROWSER_PROFILES_DIR),
            "VIDEO_FILES_DIR": str(settings.VIDEO_FILES_DIR),
        },
        "cookie_manager_actual": {
            "db_path": str(cookie_manager.db_path),
            "cookies_dir": str(cookie_manager.cookies_dir),
            "db_exists": cookie_manager.db_path.exists(),
            "cookies_dir_exists": cookie_manager.cookies_dir.exists(),
        },
        "profile_manager_actual": {
            "profiles_dir": str(_resolve_profiles_dir()),
            "fingerprints_dir": str(_resolve_fingerprints_dir()),
            "profiles_dir_exists": _resolve_profiles_dir().exists(),
            "fingerprints_dir_exists": _resolve_fingerprints_dir().exists(),
        },
        "file_counts": {}
    }

    # 统计文件数量
    try:
        cookies_dir = Path(cookie_manager.cookies_dir)
        if cookies_dir.exists():
            paths_info["file_counts"]["cookies"] = len(list(cookies_dir.glob("*.json")))

        profiles_dir = _resolve_profiles_dir()
        if profiles_dir.exists():
            paths_info["file_counts"]["browser_profiles"] = len(list(profiles_dir.iterdir()))

        fingerprints_dir = _resolve_fingerprints_dir()
        if fingerprints_dir.exists():
            paths_info["file_counts"]["fingerprints"] = len(list(fingerprints_dir.glob("*.json")))
    except Exception as e:
        paths_info["file_counts"]["error"] = str(e)

    return {
        "status": "success",
        "data": paths_info
    }


