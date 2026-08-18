"""
文件服务路由
提供视频文件的访问服务，支持 Range 请求（流式播放）
"""
import os
import mimetypes
import re
from fastapi import APIRouter, Query, Request, Header
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pathlib import Path, PureWindowsPath
from fastapi_app.core.config import settings
from fastapi_app.core.logger import logger

router = APIRouter(tags=["文件服务"])

_WINDOWS_ABS_RE = re.compile(r"^[a-zA-Z]:[\\\\/]")


def _is_windows_absolute_path(value: str) -> bool:
    return bool(_WINDOWS_ABS_RE.match(value.strip()))


def _try_map_windows_path_to_video_dir(raw: str, video_dir: Path) -> Path | None:
    """
    将 Windows 绝对路径映射到当前环境的 videoFile 目录下，解决：
    - 数据库存了旧盘符/旧项目根路径
    - Linux/WSL 下无法识别 `D:\\...` 为绝对路径
    """
    try:
        win = PureWindowsPath(raw)
    except Exception:
        return None

    lower_parts = [p.lower() for p in win.parts]
    rel_parts: tuple[str, ...] | None = None

    for anchor in ("videofile", "uploads", "covers"):
        if anchor in lower_parts:
            idx = lower_parts.index(anchor)
            rel_parts = win.parts[idx + 1 :]
            break

    # 优先使用 videofile 后的子路径，否则退化到 basename
    if rel_parts and len(rel_parts) > 0:
        candidate = (video_dir / Path(*rel_parts)).resolve()
        try:
            if str(candidate).startswith(str(video_dir.resolve())) and candidate.exists():
                return candidate
        except Exception:
            pass

    if win.name:
        possible = (video_dir / win.name).resolve()
        try:
            if str(possible).startswith(str(video_dir.resolve())) and possible.exists():
                return possible
        except Exception:
            pass

    return None

def get_range_response(file_path: Path, content_type: str, range_header: str):
    """生成支持 Range 的流式响应"""
    file_size = os.stat(file_path).st_size
    start = 0
    end = file_size - 1

    if range_header:
        try:
            h = range_header.replace("bytes=", "").split("-")
            start = int(h[0]) if h[0] != "" else 0
            end = int(h[1]) if h[1] != "" else file_size - 1
        except ValueError:
            pass

    # 修正范围
    if start > end or start < 0 or end > file_size - 1:
        start = 0
        end = file_size - 1
        
    # 计算本次响应的内容长度
    content_length = end - start + 1

    def iterfile():
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = content_length
            while remaining > 0:
                read_size = min(64 * 1024, remaining)  # 64KB chunks
                data = f.read(read_size)
                if not data:
                    break
                yield data
                remaining -= len(data)

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": content_type,
    }

    return StreamingResponse(
        iterfile(),
        status_code=206,
        headers=headers,
    )

@router.get("/getFile")
async def get_file(
    request: Request,
    filename: str = Query(..., description="文件路径或文件名"),
    range_header: str = Header(None, alias="Range")
):
    """
    获取文件内容（用于素材预览）
    支持完整路径或相对路径，支持 Range 断点续传
    """
    try:
        raw = (filename or "").strip()
        file_path = Path(raw)
        target_file = None
        
        # 1. 尝试绝对路径
        if file_path.is_absolute() and file_path.exists():
            target_file = file_path
        else:
            # 2. 尝试在 VIDEO_FILES_DIR 中查找（支持子路径，如 "covers/xxx.png"）
            video_dir = Path(settings.VIDEO_FILES_DIR)

            # 2.1 Windows 绝对路径（如 D:\...\videoFile\xxx.mp4）在 Linux/WSL 下不被识别为 absolute
            if not target_file and raw and _is_windows_absolute_path(raw):
                mapped = _try_map_windows_path_to_video_dir(raw, video_dir)
                if mapped:
                    target_file = mapped

            try:
                candidate = (video_dir / file_path).resolve()
                if str(candidate).startswith(str(video_dir.resolve())) and candidate.exists():
                    target_file = candidate
            except Exception:
                target_file = None

            # 3. 兼容旧逻辑：仅按文件名查找
            if not target_file:
                possible_file = video_dir / file_path.name
                if possible_file.exists():
                    target_file = possible_file
        
        if not target_file:
            logger.warning(f"文件不存在: {raw}")
            return JSONResponse(
                status_code=404,
                content={"error": "文件不存在", "filename": raw}
            )

        # 猜测 MIME 类型
        content_type, _ = mimetypes.guess_type(target_file)
        if not content_type:
            content_type = "application/octet-stream"

        # 如果有 Range 头，返回流式响应
        if range_header:
            return get_range_response(target_file, content_type, range_header)
        
        # 否则返回普通文件响应
        return FileResponse(
            path=str(target_file),
            media_type=content_type,
            headers={"Accept-Ranges": "bytes"}
        )

    except Exception as e:
        logger.error(f"获取文件失败: {filename}, 错误: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "获取文件失败", "detail": str(e)}
        )
