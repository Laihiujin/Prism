import os
import uuid
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from typing import Optional
from fastapi_app.db.session import main_db_pool
from fastapi_app.schemas.file import (
    FileResponse, FileListResponse, FileStatsResponse, FileUpdate, FileRenameRequest,
    AIMetadataGenerateRequest, AIMetadataGenerateResponse,
    TranscribeAudioRequest, TranscribeAudioResponse
)
from fastapi_app.schemas.common import Response
from fastapi_app.api.v1.files.services import FileService
from fastapi_app.core.exceptions import NotFoundException, BadRequestException
from fastapi_app.core.logger import logger
from fastapi_app.core.config import settings
from pydantic import BaseModel, Field


router = APIRouter(prefix="/files", tags=["文件管理"])


AI_COVER_JOBS: dict[str, dict] = {}
AI_COVER_JOBS_LOCK = asyncio.Lock()


# Dependency: Database connection
async def get_db():
    with main_db_pool.get_connection() as conn:
        yield conn


# Dependency: File service
def get_file_service():
    return FileService()


@router.get(
    "/",
    response_model=FileListResponse,
    summary="获取文件列表",
    description="""
    获取文件列表，支持过滤和分页。

    支持筛选条件:
    - status: 文件状态 (pending/published)
    - group: 分组名称
    - keyword: 搜索关键词（支持文件名、标题、描述、标签）
    - skip/limit: 分页参数（limit=0表示不限制）
    """
)
@router.get(
    "",
    response_model=FileListResponse,
    include_in_schema=False
)
async def list_files(
    status: Optional[str] = None,
    group: Optional[str] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 0,
    db=Depends(get_db),
    service: FileService = Depends(get_file_service)
):
    """获取文件列表"""
    return await service.list_files(db, status=status, group=group, keyword=keyword, skip=skip, limit=limit)


@router.get(
    "/{file_id}",
    response_model=FileResponse,
    summary="获取文件详情",
    description="根据ID获取单个文件的详细信息"
)
async def get_file(
    file_id: int,
    db=Depends(get_db),
    service: FileService = Depends(get_file_service)
):
    """获取文件详情"""
    file = await service.get_file(db, file_id)
    if not file:
        raise NotFoundException(f"文件不存在: ID {file_id}")
    return file


class FirstFrameResponse(BaseModel):
    first_frame_path: str = Field(..., description="相对路径，如 covers/first_frame_1.png")
    url: str = Field(..., description="可直接访问的 URL（/getFile 代理）")


@router.get(
    "/{file_id}/first-frame",
    response_model=Response,
    summary="生成/获取视频首帧封面",
)
async def ensure_first_frame(
    file_id: int,
    db=Depends(get_db),
    service: FileService = Depends(get_file_service),
):
    try:
        rel = await service.ensure_first_frame(db, file_id)
        return Response(
            success=True,
            data=FirstFrameResponse(
                first_frame_path=rel,
                url=f"/getFile?filename={rel}",
            ).dict(),
        )
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"生成首帧封面失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class AICoverRequest(BaseModel):
    platform_name: str = Field(default="全平台", description="平台名称，用于调性 prompt")
    aspect_ratio: str = Field(default="3:4", description="3:4 / 4：3")
    style_hint: str = Field(default="", description="额外风格补充（可选）")
    prompt: str = Field(default="", description="覆盖自动 prompt（可选）")


async def _run_ai_cover_job(
    job_id: str,
    file_id: int,
    *,
    platform_name: str,
    aspect_ratio: str,
    style_hint: str,
    prompt: str,
    ref_image_bytes: Optional[bytes],
):
    async with AI_COVER_JOBS_LOCK:
        job = AI_COVER_JOBS.get(job_id)
        if job is None:
            return
        job["status"] = "running"
        job["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        service = FileService()
        with main_db_pool.get_connection() as conn:
            data = await service.generate_ai_cover(
                conn,
                file_id,
                platform_name=platform_name,
                aspect_ratio=aspect_ratio,
                style_hint=style_hint,
                prompt_override=prompt,
                image_bytes_override=ref_image_bytes,
            )

        async with AI_COVER_JOBS_LOCK:
            job = AI_COVER_JOBS.get(job_id)
            if job is None:
                return
            job["status"] = "succeeded"
            job["cover_path"] = data.get("cover_path") or ""
            job["first_frame_path"] = data.get("first_frame_path") or ""
            job["prompt"] = data.get("prompt") or ""
            job["raw_url"] = data.get("raw_url") or ""
            job["updated_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as e:
        async with AI_COVER_JOBS_LOCK:
            job = AI_COVER_JOBS.get(job_id)
            if job is None:
                return
            job["status"] = "failed"
            job["error"] = str(e)
            job["updated_at"] = datetime.now(timezone.utc).isoformat()
        logger.error(f"AI cover job failed (job_id={job_id} file_id={file_id}): {e}", exc_info=True)


@router.post(
    "/{file_id}/ai-cover",
    response_model=Response,
    summary="基于首帧 AI 生成统一封面（硅基流动）",
)
async def generate_ai_cover(
    file_id: int,
    req: AICoverRequest,
    db=Depends(get_db),
    service: FileService = Depends(get_file_service),
):
    try:
        data = await service.generate_ai_cover(
            db,
            file_id,
            platform_name=req.platform_name,
            aspect_ratio=req.aspect_ratio,
            style_hint=req.style_hint,
            prompt_override=req.prompt,
        )
        cover_path = data.get("cover_path") or ""
        first_frame_path = data.get("first_frame_path") or ""
        return Response(
            success=True,
            data={
                **data,
                "cover_url": f"/getFile?filename={cover_path}" if cover_path else "",
                "first_frame_url": f"/getFile?filename={first_frame_path}" if first_frame_path else "",
            },
        )
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"AI 生成封面失败: {e!r}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{file_id}/ai-cover-job",
    response_model=Response,
    summary="异步 AI 生成封面（不阻塞前端）",
)
async def start_ai_cover_job(
    file_id: int,
    platform_name: str = Form("全平台"),
    aspect_ratio: str = Form("3:4"),
    style_hint: str = Form(""),
    prompt: str = Form(""),
    ref_image: Optional[UploadFile] = File(None, description="参考图（可选，用于图生图）"),
):
    ref_bytes = await ref_image.read() if ref_image else None

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async with AI_COVER_JOBS_LOCK:
        AI_COVER_JOBS[job_id] = {
            "job_id": job_id,
            "file_id": file_id,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "cover_path": "",
            "first_frame_path": "",
            "prompt": "",
            "raw_url": "",
            "error": "",
        }

    asyncio.create_task(
        _run_ai_cover_job(
            job_id,
            file_id,
            platform_name=platform_name,
            aspect_ratio=aspect_ratio,
            style_hint=style_hint,
            prompt=prompt,
            ref_image_bytes=ref_bytes,
        )
    )

    return Response(success=True, data={"job_id": job_id, "status": "pending"})


@router.get(
    "/ai-cover-jobs/{job_id}",
    response_model=Response,
    summary="查询异步 AI 封面任务状态",
)
async def get_ai_cover_job(job_id: str):
    async with AI_COVER_JOBS_LOCK:
        job = AI_COVER_JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        data = dict(job)

    cover_path = data.get("cover_path") or ""
    first_frame_path = data.get("first_frame_path") or ""
    data["cover_url"] = f"/getFile?filename={cover_path}" if cover_path else ""
    data["first_frame_url"] = f"/getFile?filename={first_frame_path}" if first_frame_path else ""
    return Response(success=True, data=data)


@router.post(
    "/upload",
    response_model=Response,
    summary="简单文件上传",
    description="""
    仅上传文件到服务器，不创建数据库记录。

    限制:
    - 最大文件大小: 160MB
    - 支持格式: mp4, mov, avi, mkv等视频格式
    """
)
async def upload_file(
    file: UploadFile = File(..., description="要上传的文件"),
    service: FileService = Depends(get_file_service)
):
    """简单文件上传"""
    try:
        # Validate file
        if not file.filename:
            raise BadRequestException("文件名不能为空")

        # Calculate file size
        content = await file.read()
        filesize_mb = len(content) / (1024 * 1024)

        # Validate size (160MB limit)
        if filesize_mb > 160:
            raise BadRequestException(f"文件过大: {filesize_mb:.2f}MB，限制160MB")

        # Validate disk space
        if not service.validate_disk_space(filesize_mb):
            raise BadRequestException("磁盘空间不足")

        # Generate unique filename
        ext = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{ext}"
        file_path = Path(settings.VIDEO_FILES_DIR) / unique_filename

        # Save file
        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"File uploaded: {file.filename} -> {file_path} ({filesize_mb:.2f}MB)")

        return Response(
            success=True,
            message="文件上传成功",
            data={
                "filename": file.filename,
                "saved_path": str(file_path),
                "size_mb": round(filesize_mb, 2)
            }
        )

    except Exception as e:
        logger.error(f"File upload error: {e}")
        if isinstance(e, (BadRequestException, NotFoundException)):
            raise
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.post(
    "/upload-save",
    response_model=Response,
    summary="上传并保存记录",
    description="""
    上传文件并在数据库中创建记录。

    支持参数:
    - file: 文件 (必需)
    - note: 备注信息 (可选)
    - group: 分组名称 (可选)
    """
)
async def upload_and_save(
    file: UploadFile = File(..., description="要上传的文件"),
    filename: Optional[str] = Form(None, description="自定义文件名（仅用于显示，不改磁盘文件名）"),
    note: Optional[str] = Form(None, description="备注信息"),
    group: Optional[str] = Form(None, description="分组名称"),
    db=Depends(get_db),
    service: FileService = Depends(get_file_service)
):
    """上传文件并保存记录"""
    try:
        # Validate file
        if not file.filename:
            raise BadRequestException("文件名不能为空")

        # Calculate file size
        content = await file.read()
        filesize_mb = len(content) / (1024 * 1024)

        # Validate size (160MB limit)
        if filesize_mb > 160:
            raise BadRequestException(f"文件过大: {filesize_mb:.2f}MB，限制160MB")

        # Validate disk space
        if not service.validate_disk_space(filesize_mb):
            raise BadRequestException("磁盘空间不足")

        # Optional display filename (sanitize, keep extension)
        display_filename = file.filename
        if filename:
            raw_custom = filename.strip()
            if raw_custom:
                safe_custom = Path(raw_custom).name  # prevent path traversal
                if not Path(safe_custom).suffix:
                    safe_custom = f"{safe_custom}{Path(file.filename).suffix}"
                display_filename = safe_custom

        # Generate unique filename
        ext = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{ext}"
        file_path = Path(settings.VIDEO_FILES_DIR) / unique_filename

        # Save file
        with open(file_path, "wb") as f:
            f.write(content)

        # Save database record - ⚠️ 只存储文件名（相对路径），便于跨机器迁移
        file_id = await service.save_file_record(
            db,
            filename=display_filename,
            file_path=unique_filename,  # 只存储文件名，如 "abc123.mp4"
            filesize_mb=filesize_mb,
            note=note,
            group_name=group
        )

        # 🆕 自动生成首帧预览图（异步，不阻塞响应）
        cover_path = None
        try:
            cover_path = await service.ensure_first_frame(db, file_id)
            logger.info(f"首帧预览图已生成: {cover_path}")
        except Exception as e:
            logger.warning(f"生成首帧预览图失败（不影响上传）: {e}")

        logger.info(
            f"File uploaded and saved: {file.filename} -> {file_path} "
            f"({filesize_mb:.2f}MB, ID: {file_id})"
        )

        return Response(
            success=True,
            message="文件上传并保存成功",
            data={
                "id": file_id,
                "filename": display_filename,
                "file_path": str(file_path),
                "size_mb": round(filesize_mb, 2),
                "note": note,
                "group_name": group,
                "cover_path": cover_path  # 🆕 返回首帧预览图路径
            }
        )

    except Exception as e:
        # Cleanup file if database save fails
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)

        logger.error(f"Upload and save error: {e}")
        if isinstance(e, (BadRequestException, NotFoundException)):
            raise
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")


@router.patch(
    "/{file_id}/rename",
    response_model=Response,
    summary="重命名文件",
    description="""
    重命名文件（同步修改数据库和磁盘文件名）

    功能：
    - 修改数据库中的 filename 和 file_path
    - 同步修改磁盘上的物理文件名
    - 支持选择是否同步修改磁盘文件
    - 自动检查文件名冲突

    参数：
    - new_filename: 新文件名（必须包含扩展名）
    - update_disk_file: 是否同步修改磁盘文件（默认 true）
    """
)
async def rename_file(
    file_id: int,
    rename_request: FileRenameRequest,
    db=Depends(get_db),
    service: FileService = Depends(get_file_service)
):
    """重命名文件（同步数据库和磁盘）"""
    try:
        success = await service.rename_file(
            db,
            file_id,
            rename_request.new_filename,
            rename_request.update_disk_file
        )

        if not success:
            raise NotFoundException(f"文件不存在: ID {file_id}")

        return Response(
            success=True,
            message="文件重命名成功",
            data={
                "id": file_id,
                "new_filename": rename_request.new_filename,
                "disk_updated": rename_request.update_disk_file
            }
        )

    except (NotFoundException, BadRequestException):
        raise
    except Exception as e:
        logger.error(f"Rename file error: {e}")
        raise HTTPException(status_code=500, detail=f"重命名失败: {str(e)}")


@router.patch(
    "/{file_id}",
    response_model=Response,
    summary="更新文件元数据",
    description="更新文件的备注、分组或状态信息"
)
async def update_file_metadata(
    file_id: int,
    update_data: FileUpdate,
    db=Depends(get_db),
    service: FileService = Depends(get_file_service)
):
    """更新文件元数据"""
    success = await service.update_file(db, file_id, update_data)
    if not success:
        raise NotFoundException(f"文件不存在: ID {file_id}")

    return Response(
        success=True,
        message="文件信息更新成功",
        data={"id": file_id}
    )


class GroupRenameRequest(BaseModel):
    from_name: str = Field(..., description="原分组名")
    to_name: str = Field(..., description="新分组名")


class GroupDeleteRequest(BaseModel):
    name: str = Field(..., description="待删除分组名")


@router.get(
    "/groups",
    response_model=Response,
    summary="获取分组列表",
)
async def list_groups(
    db=Depends(get_db),
    service: FileService = Depends(get_file_service),
):
    groups = await service.list_groups(db)
    return Response(success=True, data={"groups": groups})


@router.post(
    "/groups/rename",
    response_model=Response,
    summary="重命名分组（批量）",
)
async def rename_group(
    req: GroupRenameRequest,
    db=Depends(get_db),
    service: FileService = Depends(get_file_service),
):
    updated = await service.rename_group(db, req.from_name, req.to_name)
    return Response(success=True, message="分组重命名成功", data={"updated": updated})


@router.post(
    "/groups/delete",
    response_model=Response,
    summary="删除分组（批量）",
)
async def delete_group(
    req: GroupDeleteRequest,
    db=Depends(get_db),
    service: FileService = Depends(get_file_service),
):
    updated = await service.delete_group(db, req.name)
    return Response(success=True, message="分组已删除", data={"updated": updated})


@router.post(
    "/sync",
    response_model=Response,
    summary="同步磁盘素材到库",
    description="扫描视频目录，将缺失的文件入库。不会删除已有记录。"
)
async def sync_files(
    db=Depends(get_db),
    service: FileService = Depends(get_file_service)
):
    """
    扫描 settings.VIDEO_FILES_DIR，将未入库的文件补充到 file_records。
    返回扫描数量与新增数量。
    """
    scanned = 0
    added = 0
    dedup_deleted = 0
    normalized_paths = 0

    video_dir = Path(settings.VIDEO_FILES_DIR)
    video_dir.mkdir(parents=True, exist_ok=True)

    video_extensions = {".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv", ".webm", ".m4v"}

    cursor = db.cursor()

    cursor.execute("""
        SELECT id, filename, file_path
        FROM file_records
        WHERE file_path IS NOT NULL AND file_path != ''
        ORDER BY id ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]

    # Normalize legacy absolute `file_path` and deduplicate sync artifacts.
    for r in rows:
        file_id = r.get("id")
        stored = r.get("file_path")
        if not file_id or not stored:
            continue
        try:
            p = Path(str(stored))
            if p.is_absolute() and video_dir in p.parents and (video_dir / p.name).exists():
                cursor.execute("UPDATE file_records SET file_path = ? WHERE id = ?", (p.name, file_id))
                normalized_paths += 1
                r["file_path"] = p.name
        except Exception:
            continue

    by_key: dict[str, list[dict]] = {}
    for r in rows:
        key = Path(str(r.get("file_path") or "")).name
        if not key:
            continue
        by_key.setdefault(key, []).append(r)

    delete_ids: list[int] = []
    for key, group_rows in by_key.items():
        if len(group_rows) <= 1:
            continue
        keep = next((x for x in group_rows if (x.get("filename") or "") != key), group_rows[0])
        for x in group_rows:
            if x.get("id") != keep.get("id") and (x.get("filename") or "") == key:
                delete_ids.append(int(x["id"]))

    if normalized_paths or delete_ids:
        if delete_ids:
            cursor.executemany("DELETE FROM file_records WHERE id = ?", [(i,) for i in delete_ids])
            dedup_deleted = len(delete_ids)
        db.commit()

    existing_paths = set(by_key.keys())

    for file_path in video_dir.iterdir():
        if not file_path.is_file():
            continue
        if file_path.name.startswith("."):
            continue
        if file_path.suffix.lower() not in video_extensions:
            continue

        scanned += 1
        if file_path.name in existing_paths:
            continue

        filesize_mb = file_path.stat().st_size / (1024 * 1024)
        await service.save_file_record(
            db=db,
            filename=file_path.name,
            file_path=file_path.name,  # 只存储文件名，便于跨机器迁移
            filesize_mb=round(filesize_mb, 2),
            note=None,
            group_name=None,
        )
        added += 1
        existing_paths.add(file_path.name)

    return Response(
        success=True,
        message="同步完成",
        data={
            "scanned": scanned,
            "added": added,
            "dedup_deleted": dedup_deleted,
            "normalized_paths": normalized_paths,
        }
    )


@router.delete(
    "/{file_id}",
    response_model=Response,
    summary="删除文件",
    description="删除文件记录及磁盘文件（原子操作）"
)
async def delete_file(
    file_id: int,
    db=Depends(get_db),
    service: FileService = Depends(get_file_service)
):
    """删除文件"""
    success = await service.delete_file(db, file_id)
    if not success:
        raise NotFoundException(f"文件不存在: ID {file_id}")

    return Response(
        success=True,
        message="文件删除成功",
        data={"id": file_id}
    )


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    file_ids: list[int] = Field(..., description="要删除的文件ID列表", min_items=1)


class BatchDeleteResponse(BaseModel):
    """批量删除响应"""
    success_count: int = Field(..., description="成功删除的文件数")
    failed_count: int = Field(..., description="删除失败的文件数")
    failed_ids: list[int] = Field(default_factory=list, description="删除失败的文件ID列表")


@router.post(
    "/batch-delete",
    response_model=Response,
    summary="批量删除文件",
    description="""
    批量删除多个文件，单次请求完成所有删除操作。

    优势：
    - 单次HTTP请求，避免并发竞争
    - 批量数据库操作，性能更高
    - 批量文件删除，减少I/O阻塞
    - 支持部分成功，返回失败列表

    参数：
    - file_ids: 要删除的文件ID列表
    """
)
async def batch_delete_files(
    request: BatchDeleteRequest,
    db=Depends(get_db),
    service: FileService = Depends(get_file_service)
):
    """批量删除文件"""
    try:
        result = await service.batch_delete_files(db, request.file_ids)

        success_count = result["success_count"]
        failed_count = result["failed_count"]
        failed_ids = result["failed_ids"]

        message = f"批量删除完成: 成功{success_count}个, 失败{failed_count}个"
        if failed_count > 0:
            message += f"（失败ID: {failed_ids}）"

        return Response(
            success=True,
            message=message,
            data=BatchDeleteResponse(
                success_count=success_count,
                failed_count=failed_count,
                failed_ids=failed_ids
            ).dict()
        )

    except Exception as e:
        logger.error(f"Batch delete error: {e}")
        raise HTTPException(status_code=500, detail=f"批量删除失败: {str(e)}")


@router.get(
    "/stats/summary",
    response_model=FileStatsResponse,
    summary="文件统计信息",
    description="获取文件总数、状态分布、存储占用等统计信息"
)
async def get_file_stats(
    db=Depends(get_db),
    service: FileService = Depends(get_file_service)
):
    """获取文件统计"""
    return await service.get_stats(db)


@router.post(
    "/sync/legacy",
    response_model=Response,
    summary="同步磁盘文件",
    description="""
    扫描 videoFile 目录并将未入库的文件同步到数据库。
    
    功能:
    - 自动扫描 videoFile 目录
    - 识别视频文件 (mp4, mov, avi, mkv 等)
    - 将未入库的文件添加到数据库
    - 跳过已存在的文件
    - 返回详细的同步统计信息
    """
)
async def sync_files(
    db=Depends(get_db),
    service: FileService = Depends(get_file_service)
):
    """同步磁盘文件到数据库"""
    try:
        stats = await service.sync_files_from_disk(db)
        
        return Response(
            success=True,
            message=f"同步完成: 扫描{stats['scanned']}个文件，新增{stats['added']}个，跳过{stats['skipped']}个",
            data=stats
        )
    except Exception as e:
        logger.error(f"File sync error: {e}")
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


# ============================================
# AI内容生成和绑定
# ============================================

from pydantic import BaseModel
from typing import List

class AIContentUpdate(BaseModel):
    """AI生成内容更新请求"""
    ai_title: Optional[str] = None
    ai_description: Optional[str] = None
    ai_tags: Optional[List[str]] = None


@router.patch(
    "/{file_id}/ai-content",
    response_model=Response,
    summary="更新素材的AI生成内容",
    description="""
    更新素材的AI生成标题、描述和标签。

    AI生成的内容会永久绑定到素材，可在发布时快速使用。
    支持部分更新，未传递的字段保持原值不变。

    参数:
    - ai_title: AI生成的标题
    - ai_description: AI生成的描述
    - ai_tags: AI生成的标签列表
    """
)
async def update_ai_content(
    file_id: int,
    content: AIContentUpdate,
    db=Depends(get_db)
):
    """更新AI生成内容"""
    try:
        cursor = db.cursor()

        # 检查文件是否存在
        cursor.execute("SELECT id FROM file_records WHERE id = ?", (file_id,))
        if not cursor.fetchone():
            raise NotFoundException(f"文件不存在: ID {file_id}")

        # 检查并添加AI内容字段（如果不存在）
        cursor.execute("PRAGMA table_info(file_records)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'ai_title' not in columns:
            cursor.execute("ALTER TABLE file_records ADD COLUMN ai_title TEXT")
        if 'ai_description' not in columns:
            cursor.execute("ALTER TABLE file_records ADD COLUMN ai_description TEXT")
        if 'ai_tags' not in columns:
            cursor.execute("ALTER TABLE file_records ADD COLUMN ai_tags TEXT")
        if 'ai_generated_at' not in columns:
            cursor.execute("ALTER TABLE file_records ADD COLUMN ai_generated_at TIMESTAMP")

        # 构建更新SQL
        updates = []
        params = []

        if content.ai_title is not None:
            updates.append("ai_title = ?")
            params.append(content.ai_title)

        if content.ai_description is not None:
            updates.append("ai_description = ?")
            params.append(content.ai_description)

        if content.ai_tags is not None:
            import json
            updates.append("ai_tags = ?")
            params.append(json.dumps(content.ai_tags, ensure_ascii=False))

        if updates:
            updates.append("ai_generated_at = CURRENT_TIMESTAMP")
            params.append(file_id)

            sql = f"UPDATE file_records SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, params)
            db.commit()

            logger.info(f"AI content updated for file {file_id}")

        return Response(
            success=True,
            message="AI内容已保存",
            data={
                "id": file_id,
                "ai_title": content.ai_title,
                "ai_description": content.ai_description,
                "ai_tags": content.ai_tags
            }
        )

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Update AI content error: {e}")
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.get(
    "/{file_id}/ai-content",
    response_model=Response,
    summary="获取素材的AI生成内容",
    description="获取指定素材的AI生成标题、描述和标签"
)
async def get_ai_content(
    file_id: int,
    db=Depends(get_db)
):
    """获取AI生成内容"""
    try:
        cursor = db.cursor()

        # 检查AI内容字段是否存在
        cursor.execute("PRAGMA table_info(file_records)")
        columns = [row[1] for row in cursor.fetchall()]

        has_ai_fields = all(col in columns for col in ['ai_title', 'ai_description', 'ai_tags', 'ai_generated_at'])

        if not has_ai_fields:
            # 字段不存在，返回空内容
            return Response(
                success=True,
                message="该素材暂无AI生成内容",
                data={
                    "id": file_id,
                    "ai_title": None,
                    "ai_description": None,
                    "ai_tags": [],
                    "ai_generated_at": None
                }
            )

        # 查询AI内容
        cursor.execute("""
            SELECT ai_title, ai_description, ai_tags, ai_generated_at
            FROM file_records
            WHERE id = ?
        """, (file_id,))

        row = cursor.fetchone()
        if not row:
            raise NotFoundException(f"文件不存在: ID {file_id}")

        import json
        ai_tags = json.loads(row[2]) if row[2] else []

        return Response(
            success=True,
            message="获取AI内容成功",
            data={
                "id": file_id,
                "ai_title": row[0],
                "ai_description": row[1],
                "ai_tags": ai_tags,
                "ai_generated_at": row[3]
            }
        )

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Get AI content error: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.delete(
    "/{file_id}/ai-content",
    response_model=Response,
    summary="清除素材的AI生成内容",
    description="清除指定素材的所有AI生成内容"
)
async def clear_ai_content(
    file_id: int,
    db=Depends(get_db)
):
    """清除AI生成内容"""
    try:
        cursor = db.cursor()

        # 检查文件是否存在
        cursor.execute("SELECT id FROM file_records WHERE id = ?", (file_id,))
        if not cursor.fetchone():
            raise NotFoundException(f"文件不存在: ID {file_id}")

        # 清除AI内容
        cursor.execute("""
            UPDATE file_records
            SET ai_title = NULL,
                ai_description = NULL,
                ai_tags = NULL,
                ai_generated_at = NULL
            WHERE id = ?
        """, (file_id,))
        db.commit()

        return Response(
            success=True,
            message="AI内容已清除",
            data={"id": file_id}
        )

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Clear AI content error: {e}")
        raise HTTPException(status_code=500, detail=f"清除失败: {str(e)}")


# ============================================
# AI批量元数据生成
# ============================================

@router.post(
    "/batch-generate-metadata",
    response_model=AIMetadataGenerateResponse,
    summary="批量生成AI元数据",
    description="""
    为多个视频文件批量生成AI标题、描述和标签。

    功能：
    - 自动分析视频文件名
    - 智能生成标题、描述和标签
    - 支持强制重新生成
    - 返回详细的生成结果

    参数：
    - file_ids: 文件ID列表
    - force_regenerate: 是否强制重新生成（即使已有AI内容）
    """
)
async def batch_generate_ai_metadata(
    request: AIMetadataGenerateRequest,
    db=Depends(get_db)
):
    """批量生成AI元数据"""
    try:
        from ai_service.model_manager import get_model_manager

        cursor = db.cursor()
        results = []
        success_count = 0
        failed_count = 0

        # 获取AI模型管理器
        model_manager = get_model_manager()

        for file_id in request.file_ids:
            try:
                # 查询文件信息
                cursor.execute("""
                    SELECT id, filename, file_path, title, tags, ai_title, ai_description, ai_tags
                    FROM file_records
                    WHERE id = ?
                """, (file_id,))

                row = cursor.fetchone()
                if not row:
                    results.append({
                        "file_id": file_id,
                        "status": "failed",
                        "error": "文件不存在"
                    })
                    failed_count += 1
                    continue

                (
                    file_id_val,
                    filename,
                    file_path,
                    user_title,
                    user_tags,
                    existing_ai_title,
                    existing_ai_desc,
                    existing_ai_tags,
                ) = row

                # 检查是否已有AI内容且不强制重新生成
                if not request.force_regenerate and existing_ai_title:
                    results.append({
                        "file_id": file_id,
                        "status": "skipped",
                        "message": "已有AI内容，跳过生成"
                    })
                    continue

                # 使用AI生成元数据
                prompt = f"""请基于「文件名」以及「用户已有标题/标签」，生成适合短视频平台的 AI 标题、描述和标签，并尽量做“改编优化”而不是完全重写。

输入：
- 文件名：{filename}
- 用户标题（可为空）：{user_title or ""}
- 用户标签（可为空，可能为 JSON 数组/空格分隔/逗号分隔）：{user_tags or ""}

输出要求（严格 JSON，禁止 markdown/解释/多余文本）：
{{
  "title": "标题（<=30字，中文优先）",
  "description": "描述（50-120字，中文优先）",
  "tags": ["标签1", "标签2", "标签3"]
}}

约束：
1) 如果用户标题/标签存在：保持主题一致、保留核心意思，在其基础上润色优化即可
2) 如出现英文词：翻译为中文（专有名词可保留原文并加中文释义）
3) tags 输出 1-4 个，去重，不要带 # 符号（系统会自动加 #）
4) title/description/tags 全部用中文表达为主，不要表情符号
"""

                # 调用AI模型
                response = await model_manager.call_current_model(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=500
                )

                if response["status"] != "success":
                    raise Exception(response.get("error", "AI调用失败"))

                # 解析AI返回的JSON
                import json
                import re

                content = response["content"]
                # 尝试提取JSON
                json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
                if json_match:
                    metadata = json.loads(json_match.group())
                else:
                    metadata = json.loads(content)

                ai_title = str(metadata.get("title", "") or "").strip()
                ai_description = str(metadata.get("description", "") or "").strip()
                raw_tags = metadata.get("tags", [])
                if isinstance(raw_tags, str):
                    # tolerate accidental "tag1 tag2" output
                    raw_tags = [t for t in re.split(r"[\s,，]+", raw_tags) if t and t.strip()]
                ai_tags = []
                if isinstance(raw_tags, list):
                    for t in raw_tags:
                        s = str(t).strip()
                        if not s:
                            continue
                        s = s.lstrip("#").strip()
                        if s and s not in ai_tags:
                            ai_tags.append(s)
                ai_tags = ai_tags[:4]

                # 保存到数据库
                cursor.execute("""
                    UPDATE file_records
                    SET ai_title = ?, ai_description = ?, ai_tags = ?, ai_generated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (ai_title, ai_description, json.dumps(ai_tags, ensure_ascii=False), file_id))
                db.commit()

                results.append({
                    "file_id": file_id,
                    "status": "success",
                    "ai_title": ai_title,
                    "ai_description": ai_description,
                    "ai_tags": ai_tags
                })
                success_count += 1

                logger.info(f"AI metadata generated for file {file_id}: {ai_title}")

            except Exception as e:
                logger.error(f"Failed to generate AI metadata for file {file_id}: {e}")
                results.append({
                    "file_id": file_id,
                    "status": "failed",
                    "error": str(e)
                })
                failed_count += 1

        return AIMetadataGenerateResponse(
            success_count=success_count,
            failed_count=failed_count,
            results=results
        )

    except Exception as e:
        logger.error(f"Batch generate AI metadata error: {e}")
        raise HTTPException(status_code=500, detail=f"批量生成失败: {str(e)}")


# ============================================
# AI语音转文字 (Whisper)
# ============================================

@router.post(
    "/transcribe-audio",
    response_model=TranscribeAudioResponse,
    summary="视频语音转文字",
    description="""
    使用Whisper模型将视频中的语音转换为文字。

    功能：
    - 支持多种语言（中文、英文等）
    - 自动提取视频音频
    - 高精度语音识别
    - 保存转录文本用于生成更丰富的标题和描述

    参数：
    - file_id: 视频文件ID
    - language: 语言代码（zh, en等）
    - model: Whisper模型名称
    """
)
async def transcribe_audio(
    request: TranscribeAudioRequest,
    db=Depends(get_db)
):
    """视频语音转文字"""
    try:
        cursor = db.cursor()

        # 查询文件信息
        cursor.execute("""
            SELECT id, filename, file_path, duration
            FROM file_records
            WHERE id = ?
        """, (request.file_id,))

        row = cursor.fetchone()
        if not row:
            raise NotFoundException(f"文件不存在: ID {request.file_id}")

        file_id, filename, file_path, duration = row

        # 检查文件是否存在
        if not Path(file_path).exists():
            raise NotFoundException(f"文件不存在: {file_path}")

        # 使用OpenAI Whisper API进行转录
        # 这里需要提取音频并调用Whisper
        from ai_service.model_manager import get_model_manager
        import tempfile
        import subprocess

        # 提取音频到临时文件
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
            temp_audio_path = temp_audio.name

        try:
            # 使用ffmpeg提取音频
            logger.info(f"Extracting audio from {file_path} to {temp_audio_path}")
            subprocess.run([
                "ffmpeg", "-i", file_path,
                "-vn", "-acodec", "libmp3lame",
                "-q:a", "2", temp_audio_path,
                "-y"
            ], check=True, capture_output=True)

            # 调用Whisper API
            model_manager = get_model_manager()

            # 使用当前配置的AI提供商调用Whisper
            # 注意：需要支持Whisper的提供商（如OpenAI兼容接口）
            from openai import OpenAI

            # 获取当前配置的API密钥和基础URL
            import json
            config_file = Path(__file__).parent.parent.parent.parent / "ai_service" / "config.json"
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            current_provider = config.get("current_provider", "siliconflow")
            provider_config = config["providers"].get(current_provider, {})

            client = OpenAI(
                api_key=provider_config.get("api_key"),
                base_url=provider_config.get("base_url")
            )

            # 读取音频文件并转录
            with open(temp_audio_path, "rb") as audio_file:
                transcript_response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.audio.transcriptions.create(
                        model=request.model,
                        file=audio_file,
                        language=request.language
                    )
                )

            transcript_text = transcript_response.text

            # 保存转录文本到数据库（可以添加新字段存储）
            # 这里我们将转录文本保存到描述字段或单独的字段
            logger.info(f"Transcription completed for file {file_id}: {len(transcript_text)} characters")

            # 获取视频时长
            if not duration:
                # 使用ffprobe获取时长
                result = subprocess.run([
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    file_path
                ], capture_output=True, text=True, check=True)
                duration = float(result.stdout.strip())

                # 更新数据库
                cursor.execute("UPDATE file_records SET duration = ? WHERE id = ?", (duration, file_id))
                db.commit()

            return TranscribeAudioResponse(
                file_id=file_id,
                transcript=transcript_text,
                language=request.language,
                duration=duration or 0.0
            )

        finally:
            # 清理临时文件
            if Path(temp_audio_path).exists():
                Path(temp_audio_path).unlink()

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Transcribe audio error: {e}")
        raise HTTPException(status_code=500, detail=f"转录失败: {str(e)}")

