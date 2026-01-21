"""
发布模块API路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Optional, List, Any
from pathlib import Path
import sys

from pydantic import BaseModel, Field

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from fastapi_app.db.session import get_main_db
from fastapi_app.schemas.publish import (
    BatchPublishRequest,
    PublishPreset,
    PresetResponse,
    PublishHistoryResponse,
    BatchPublishResponse,
    PublishStatsResponse
)
from fastapi_app.schemas.common import Response, StatusResponse
from fastapi_app.api.v1.publish.services import PublishService, get_publish_service
from fastapi_app.core.exceptions import NotFoundException, BadRequestException
from fastapi_app.core.logger import logger
from fastapi_app.core.config import settings
from fastapi_app.db.runtime import mysql_enabled, sa_connection
import warnings
from sqlalchemy import text


router = APIRouter(prefix="/publish", tags=["发布管理"])

# 运行指纹：用于确认"当前生效的发布入口"
PUBLISH_ROUTER_BUILD_TAG = "fastapi_app/api/v1/publish/router.py@unified-batch-only@celery-migration@2025-12-23"


# 依赖注入：获取发布服务（已迁移到 Celery，不再需要 task_manager）
def get_service() -> PublishService:
    """获取发布服务实例"""
    return get_publish_service()


@router.post(
    "/batch",
    response_model=Response[BatchPublishResponse],
    summary="批量发布（统一入口，支持单次/批量）",
    description="""
    统一的发布入口（替代旧的 /direct 和 /single 路由）。

    特性:
    - ✅ 支持单次发布（file_ids=[单个ID], accounts=[单个账号]）
    - ✅ 支持批量发布（多个素材 × 多个账号）
    - ✅ 支持单平台和多平台发布
    - ✅ 支持部分失败处理
    - ✅ 统一配置（标题、描述、话题）
    - ✅ 可设置优先级
    - ✅ 返回详细的任务状态

    多平台发布:
    - 如果不指定 platform 参数，系统会自动根据账号所属平台分组发布
    - 每个平台-账号-素材组合会创建独立的发布任务

    单次发布示例:
    ```json
    {
        "file_ids": [123],
        "accounts": ["account_xxx"],
        "title": "我的视频",
        "topics": ["测试", "抖音"]
    }
    ```
    """
)
async def publish_batch_videos(
    request: BatchPublishRequest,
    db=Depends(get_main_db),
    service: PublishService = Depends(get_service)
):
    """批量发布视频"""
    try:
        logger.info(f"[PublishRouter] {PUBLISH_ROUTER_BUILD_TAG} (file={__file__}) endpoint=/publish/batch")
        result = await service.publish_batch(
            db=db,
            file_ids=request.file_ids,
            accounts=request.accounts,
            platform=request.platform if request.platform else None,  # 允许 None
            title=request.title,
            description=request.description,
            topics=request.topics,
            cover_path=request.cover_path,
            scheduled_time=request.scheduled_time,
            interval_control_enabled=request.interval_control_enabled,
            interval_mode=request.interval_mode,
            interval_seconds=request.interval_seconds,
            random_offset=request.random_offset,
            priority=request.priority,
            items=request.items,  # 传递 items 参数，包含每个素材的独立配置
            # 🆕 NEW: Assignment strategy parameters
            assignment_strategy=request.assignment_strategy,
            one_per_account_mode=request.one_per_account_mode,
            per_platform_overrides=request.per_platform_overrides,
            # 🆕 NEW: Deduplication parameters
            allow_duplicate_publish=request.allow_duplicate_publish,
            dedup_window_days=request.dedup_window_days,
        )

        return Response(
            success=True,
            message=f"批量任务已创建: 成功 {result['success_count']}, 失败 {result['failed_count']}",
            data=result
        )

    except (NotFoundException, BadRequestException) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"批量发布失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量发布失败: {str(e)}")


@router.post(
    "/single",
    response_model=Response[BatchPublishResponse],
    summary="单次发布（向后兼容，推荐使用 /batch）",
    description="""
    单次发布接口（向后兼容）。

    ⚠️ 该接口已废弃，建议使用统一的 /batch 接口。

    功能与 /batch 完全相同，但参数会自动转换为批量格式：
    - file_ids: 单个文件ID会转换为列表
    - accounts: 单个账号ID会转换为列表
    """
)
async def publish_single_video(
    request: BatchPublishRequest,
    db=Depends(get_main_db),
    service: PublishService = Depends(get_service)
):
    """单次发布视频（向后兼容接口）"""
    try:
        logger.warning("[PublishRouter] /publish/single is deprecated, use /publish/batch instead")
        logger.info(f"[PublishRouter] Single publish request: file_ids={request.file_ids}, accounts={request.accounts}")

        # 直接使用 batch 接口处理（支持单个或多个文件/账号）
        result = await service.publish_batch(
            db=db,
            file_ids=request.file_ids,
            accounts=request.accounts,
            platform=request.platform if request.platform else None,
            title=request.title,
            description=request.description,
            topics=request.topics,
            cover_path=request.cover_path,
            scheduled_time=request.scheduled_time,
            interval_control_enabled=request.interval_control_enabled,
            interval_mode=request.interval_mode,
            interval_seconds=request.interval_seconds,
            random_offset=request.random_offset,
            priority=request.priority,
            items=request.items
        )

        return Response(
            success=True,
            message=f"任务已创建: 成功 {result['success_count']}, 失败 {result['failed_count']}",
            data=result
        )

    except (NotFoundException, BadRequestException) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"单次发布失败: {e}")
        raise HTTPException(status_code=500, detail=f"发布失败: {str(e)}")


@router.get(
    "/presets",
    response_model=Response[List[PresetResponse]],
    summary="获取发布预设列表",
    description="""
    获取所有发布预设/计划。

    预设包含:
    - 默认平台和账号
    - 标题模板
    - 话题标签
    - 定时配置
    """
)
async def list_presets(
    service: PublishService = Depends(get_service)
):
    """获取发布预设列表"""
    try:
        presets = await service.list_presets()

        return Response(
            success=True,
            message="获取预设列表成功",
            data=presets
        )

    except Exception as e:
        logger.error(f"获取预设列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.post(
    "/presets",
    response_model=Response,
    summary="创建发布预设",
    description="""
    创建新的发布预设。

    预设可用于:
    - 快速发布（一键应用配置）
    - 批量操作
    - 定时任务
    """
)
async def create_preset(
    preset: PublishPreset,
    service: PublishService = Depends(get_service)
):
    """创建发布预设"""
    try:
        # 转换为字典
        preset_data = {
            "name": preset.name,
            "platforms": [preset.platform],  # PresetManager expects platforms as list
            "accounts": preset.accounts,
            "default_title": preset.default_title_template,
            "description": preset.default_description,
            "default_tags": preset.default_topics,
            "scheduleEnabled": preset.schedule_enabled,
            "videosPerDay": preset.videos_per_day,
            "scheduleDate": preset.schedule_date,
            "timePoint": preset.time_point
        }

        result = await service.create_preset(preset_data)

        return Response(
            success=True,
            message="预设创建成功",
            data={"id": result.get("id")}
        )

    except BadRequestException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"创建预设失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.put(
    "/presets/{preset_id}",
    response_model=Response,
    summary="更新发布预设",
    description="更新现有的发布预设配置"
)
async def update_preset(
    preset_id: int,
    preset: PublishPreset,
    service: PublishService = Depends(get_service)
):
    """更新发布预设"""
    try:
        # 转换为字典
        preset_data = {
            "name": preset.name,
            "platforms": [preset.platform],
            "accounts": preset.accounts,
            "default_title": preset.default_title_template,
            "description": preset.default_description,
            "default_tags": preset.default_topics,
            "scheduleEnabled": preset.schedule_enabled,
            "videosPerDay": preset.videos_per_day,
            "scheduleDate": preset.schedule_date,
            "timePoint": preset.time_point
        }

        result = await service.update_preset(preset_id, preset_data)

        return Response(
            success=True,
            message="预设更新成功",
            data={"id": preset_id}
        )

    except (NotFoundException, BadRequestException) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"更新预设失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.delete(
    "/presets/{preset_id}",
    response_model=StatusResponse,
    summary="删除发布预设",
    description="删除指定的发布预设"
)
async def delete_preset(
    preset_id: int,
    service: PublishService = Depends(get_service)
):
    """删除发布预设"""
    try:
        await service.delete_preset(preset_id)

        return StatusResponse(
            success=True,
            message=f"预设已删除: ID {preset_id}"
        )

    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"删除预设失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.post(
    "/presets/{preset_id}/use",
    response_model=Response[BatchPublishResponse],
    summary="使用预设发布",
    description="""
    使用预设配置进行发布。

    特性:
    - 自动应用预设中的配置
    - 支持覆盖部分参数
    - 自动增加预设使用次数
    """
)
async def use_preset_to_publish(
    preset_id: int,
    file_ids: List[int] = Query(..., description="要发布的文件ID列表"),
    override_title: Optional[str] = Query(None, description="覆盖预设中的标题"),
    override_accounts: Optional[List[str]] = Query(None, description="覆盖预设中的账号"),
    db=Depends(get_main_db),
    service: PublishService = Depends(get_service)
):
    """使用预设发布"""
    try:
        # 构建覆盖参数
        override_data = {}
        if override_title:
            override_data["title"] = override_title
        if override_accounts:
            override_data["accounts"] = override_accounts

        result = await service.use_preset(
            db=db,
            preset_id=preset_id,
            file_ids=file_ids,
            override_data=override_data if override_data else None
        )

        return Response(
            success=True,
            message=f"使用预设发布成功: {result['success_count']} 个任务已创建",
            data=result
        )

    except (NotFoundException, BadRequestException) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"使用预设发布失败: {e}")
        raise HTTPException(status_code=500, detail=f"发布失败: {str(e)}")


@router.get(
    "/history",
    response_model=Response[List[PublishHistoryResponse]],
    summary="获取发布历史",
    description="""
    获取发布任务历史记录。

    支持筛选:
    - 按平台筛选
    - 按状态筛选
    - 分页查询
    """
)
async def get_publish_history(
    platform: Optional[int] = Query(None, ge=1, le=5, description="平台代码"),
    status: Optional[str] = Query(None, description="任务状态"),
    limit: int = Query(100, ge=1, le=500, description="返回数量限制"),
    db=Depends(get_main_db),
    service: PublishService = Depends(get_service)
):
    """获取发布历史"""
    try:
        history = await service.get_publish_history(
            db=db,
            platform=platform,
            status=status,
            limit=limit
        )

        return Response(
            success=True,
            message=f"获取发布历史成功: {len(history)} 条记录",
            data=history
        )

    except Exception as e:
        logger.error(f"获取发布历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.delete(
    "/history/{task_id}",
    response_model=StatusResponse,
    summary="删除发布历史记录",
    description="删除指定的发布历史任务记录（通过task_id或celery_task_id）"
)
async def delete_publish_history(
    task_id: str,
    db=Depends(get_main_db)
):
    """删除发布历史记录"""
    try:
        if mysql_enabled():
            warnings.warn("SQLite publish_tasks path is deprecated; using MySQL via DATABASE_URL", DeprecationWarning)
            with sa_connection() as conn:
                # 尝试按 task_id 或 celery_task_id 删除
                result = conn.execute(
                    text("DELETE FROM publish_tasks WHERE task_id = :task_id OR celery_task_id = :task_id"),
                    {"task_id": task_id}
                )
                conn.commit()

                if result.rowcount == 0:
                    raise HTTPException(status_code=404, detail="任务不存在")

                logger.info(f"✅ 历史任务已删除: {task_id}")
                return StatusResponse(
                    success=True,
                    message="任务已删除"
                )

        # SQLite fallback
        cursor = db.cursor()

        # 尝试按 task_id (整数) 或 celery_task_id (UUID字符串) 删除
        cursor.execute(
            "DELETE FROM publish_tasks WHERE task_id = ? OR celery_task_id = ?",
            (task_id, task_id)
        )

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="任务不存在")

        db.commit()
        logger.info(f"✅ 历史任务已删除: {task_id}")

        return StatusResponse(
            success=True,
            message="任务已删除"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除历史任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.get(
    "/stats",
    response_model=Response[PublishStatsResponse],
    summary="获取发布统计",
    description="""
    获取发布数据统计。

    包含:
    - 总发布数
    - 今日发布数
    - 待处理任务数
    - 失败任务数
    - 按平台分布
    """
)
async def get_publish_stats(
    db=Depends(get_main_db)
):
    """获取发布统计"""
    try:
        if mysql_enabled():
            warnings.warn("SQLite publish_tasks path is deprecated; using MySQL via DATABASE_URL", DeprecationWarning)
            with sa_connection() as conn:
                total_published = conn.execute(text("SELECT COUNT(*) AS c FROM publish_tasks WHERE status = 'success'")).mappings().one()["c"]
                today_published = conn.execute(text("""
                    SELECT COUNT(*) AS c FROM publish_tasks
                    WHERE status = 'success' AND date(created_at) = date(now())
                """)).mappings().one()["c"]
                pending_tasks = conn.execute(text("SELECT COUNT(*) AS c FROM publish_tasks WHERE status IN ('pending','retry')")).mappings().one()["c"]
                failed_tasks = conn.execute(text("SELECT COUNT(*) AS c FROM publish_tasks WHERE status = 'error'")).mappings().one()["c"]

                by_platform_rows = conn.execute(text("""
                    SELECT platform, COUNT(*) as count
                    FROM publish_tasks
                    WHERE status = 'success'
                    GROUP BY platform
                """)).mappings().all()

            by_platform = {}
            platform_map = {
                "1": "xiaohongshu",
                "2": "channels",
                "3": "douyin",
                "4": "kuaishou",
                "5": "bilibili"
            }
            for row in by_platform_rows:
                platform_name = platform_map.get(str(row.get("platform")), f"platform_{row.get('platform')}")
                by_platform[platform_name] = row.get("count", 0)

            stats = PublishStatsResponse(
                total_published=int(total_published),
                today_published=int(today_published),
                pending_tasks=int(pending_tasks),
                failed_tasks=int(failed_tasks),
                by_platform=by_platform
            )
            return Response(
                success=True,
                message="获取统计成功",
                data=stats
            )

        cursor = db.cursor()

        # 总发布数
        cursor.execute("SELECT COUNT(*) FROM publish_tasks WHERE status = 'success'")
        total_published = cursor.fetchone()[0]

        # 今日发布数
        cursor.execute("""
            SELECT COUNT(*) FROM publish_tasks
            WHERE status = 'success' AND date(created_at) = date('now', 'localtime')
        """)
        today_published = cursor.fetchone()[0]

        # 待处理任务数
        cursor.execute("SELECT COUNT(*) FROM publish_tasks WHERE status IN ('pending', 'retry')")
        pending_tasks = cursor.fetchone()[0]

        # 失败任务数
        cursor.execute("SELECT COUNT(*) FROM publish_tasks WHERE status = 'error'")
        failed_tasks = cursor.fetchone()[0]

        # 按平台统计
        cursor.execute("""
            SELECT platform, COUNT(*) as count
            FROM publish_tasks
            WHERE status = 'success'
            GROUP BY platform
        """)
        by_platform = {}
        platform_map = {
            "1": "xiaohongshu",
            "2": "channels",
            "3": "douyin",
            "4": "kuaishou",
            "5": "bilibili"
        }
        for row in cursor.fetchall():
            platform_name = platform_map.get(str(row[0]), f"platform_{row[0]}")
            by_platform[platform_name] = row[1]

        stats = PublishStatsResponse(
            total_published=total_published,
            today_published=today_published,
            pending_tasks=pending_tasks,
            failed_tasks=failed_tasks,
            by_platform=by_platform
        )

        return Response(
            success=True,
            message="获取统计成功",
            data=stats
        )

    except Exception as e:
        logger.error(f"获取统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"统计失败: {str(e)}")


class SeleniumDebugCaptureRequest(BaseModel):
    url: str = Field(..., description="要打开的页面 URL（仅在 ENABLE_SELENIUM_DEBUG=true 时可用）")
    prefix: str = Field(default="publish_debug", description="输出文件前缀")
    headless: bool = Field(default=False, description="是否无头运行")
    run_ocr: bool = Field(default=True, description="是否对截图做 OCR（需要配置 SILICONFLOW_API_KEY）")
    user_data_dir: Optional[str] = Field(default=None, description="Chrome user-data-dir（可选）")
    dismiss_popups: bool = Field(default=True, description="是否尝试关闭常见弹窗")


@router.post("/debug/capture", summary="Selenium+OCR 调试抓取（辅助发布定位）")
async def selenium_debug_capture(req: SeleniumDebugCaptureRequest):
    if not (settings.ENABLE_SELENIUM_DEBUG or settings.DEBUG):
        raise HTTPException(status_code=404, detail="selenium debug is disabled")

    try:
        from automation.selenium_dom import new_chrome_driver, dismiss_common_popups, capture_debug_bundle

        driver = new_chrome_driver(headless=req.headless, user_data_dir=req.user_data_dir)
        try:
            driver.get(req.url)
            if req.dismiss_popups:
                dismiss_common_popups(driver)
            result = capture_debug_bundle(
                driver,
                out_dir=str(Path(settings.BASE_DIR) / "logs"),
                prefix=req.prefix,
                run_ocr=req.run_ocr,
            )
        finally:
            try:
                driver.quit()
            except Exception:
                pass

        return {
            "success": True,
            "data": {
                "url": result.url,
                "html_path": str(result.html_path),
                "screenshot_path": str(result.screenshot_path),
                "ocr_text_path": str(result.ocr_text_path) if result.ocr_text_path else None,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"capture failed: {str(e)}")


