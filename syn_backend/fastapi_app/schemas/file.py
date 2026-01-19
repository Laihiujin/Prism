from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class FileBase(BaseModel):
    """Base file schema"""
    filename: str
    filesize: float = Field(..., description="File size in MB")
    note: Optional[str] = None
    group_name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    cover_image: Optional[str] = None
    ai_title: Optional[str] = None
    ai_description: Optional[str] = None
    ai_tags: Optional[str] = None
    duration: Optional[float] = None
    video_width: Optional[int] = None
    video_height: Optional[int] = None
    aspect_ratio: Optional[str] = None
    orientation: Optional[str] = None


class FileCreate(FileBase):
    """Schema for creating a file record"""
    file_path: str
    upload_time: Optional[datetime] = None


class FileUpdate(BaseModel):
    """Schema for updating file metadata"""
    filename: Optional[str] = None
    note: Optional[str] = None
    group_name: Optional[str] = None
    status: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    cover_image: Optional[str] = None
    ai_title: Optional[str] = None
    ai_description: Optional[str] = None
    ai_tags: Optional[str] = None


class FileRenameRequest(BaseModel):
    """Schema for renaming file (both database and disk)"""
    new_filename: str = Field(..., description="新文件名（含扩展名）")
    update_disk_file: bool = Field(True, description="是否同步修改磁盘文件名")


class FileResponse(FileBase):
    """Schema for file response"""
    id: int
    file_path: str
    upload_time: datetime
    status: str = Field(default="pending", description="pending or published")
    published_at: Optional[datetime] = None
    last_platform: Optional[int] = None
    last_accounts: Optional[str] = None

    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    """Schema for paginated file list"""
    total: int
    items: List[FileResponse]


class FileStatsResponse(BaseModel):
    """Schema for file statistics"""
    total_files: int
    pending_files: int
    published_files: int
    total_size_mb: float
    avg_size_mb: float


class AIMetadataGenerateRequest(BaseModel):
    """AI元数据生成请求"""
    file_ids: List[int] = Field(..., description="文件ID列表")
    force_regenerate: bool = Field(False, description="强制重新生成（即使已有AI内容）")


class AIMetadataGenerateResponse(BaseModel):
    """AI元数据生成响应"""
    success_count: int
    failed_count: int
    results: List[dict]


class TranscribeAudioRequest(BaseModel):
    """语音转文字请求"""
    file_id: int = Field(..., description="视频文件ID")
    language: Optional[str] = Field("zh", description="语言代码，如zh, en")
    model: Optional[str] = Field("whisper-1", description="模型名称")


class TranscribeAudioResponse(BaseModel):
    """语音转文字响应"""
    file_id: int
    transcript: str
    language: str
    duration: float
