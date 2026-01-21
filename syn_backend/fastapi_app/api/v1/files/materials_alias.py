"""
Materials 路由别名
将 /api/materials 映射到 files 功能
"""

from fastapi import APIRouter, Depends
from fastapi_app.api.v1.files.router import list_files, get_file_service, get_db
from fastapi_app.schemas.file import FileListResponse
from typing import Optional
from fastapi_app.api.v1.files.services import FileService

router = APIRouter(prefix="/materials", tags=["素材管理"])

@router.get(
    "",
    response_model=FileListResponse,
    summary="获取素材列表"
)
async def list_materials_alias(
    status: Optional[str] = None,
    group: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db=Depends(get_db),
    service: FileService = Depends(get_file_service)
):
    """获取素材列表（兼容 /api/materials）"""
    return await list_files(status=status, group=group, skip=skip, limit=limit, db=db, service=service)
