import os
import shutil
from datetime import datetime
from typing import List, Optional
from pathlib import Path
import json
import subprocess
import math
import warnings
import asyncio
from functools import partial

from collections.abc import Mapping
from sqlalchemy import text
from fastapi_app.core.config import settings
from fastapi_app.core.exceptions import NotFoundException, BadRequestException
from fastapi_app.schemas.file import FileResponse, FileListResponse, FileStatsResponse, FileUpdate
from fastapi_app.core.logger import logger
from fastapi_app.db.runtime import mysql_enabled, sa_connection
from fastapi_app.cache.redis_client import get_redis
from fastapi_app.core.timezone_utils import now_beijing_naive, now_beijing_iso
from utils.video_frames import extract_first_frame
from utils.video_probe import probe_video_metadata
from platforms.path_utils import resolve_video_file


# Global semaphore to limit concurrent ffmpeg processes
_FFMPEG_SEMAPHORE = asyncio.Semaphore(3)  # Max 3 concurrent ffmpeg processes


class FileService:
    """Service layer for file management operations"""

    def __init__(self):
        self.video_dir = Path(settings.VIDEO_FILES_DIR)
        self.video_dir.mkdir(parents=True, exist_ok=True)
        self.covers_dir = self.video_dir / "covers"
        self.covers_dir.mkdir(parents=True, exist_ok=True)

    def _cover_rel_path(self, filename: str) -> str:
        return str(Path("covers") / filename).replace("\\", "/")

    def _first_frame_filename(self, file_id: int) -> str:
        return f"first_frame_{file_id}.png"

    def _ai_cover_filename(self, file_id: int, platform_name: str, *, ext: str = "png") -> str:
        safe_platform = "".join([c for c in (platform_name or "all") if c.isalnum() or c in ("-", "_")])[:32] or "all"
        ts = now_beijing_naive().strftime("%Y%m%d_%H%M%S")
        safe_ext = "".join([c for c in (ext or "png").lower() if c.isalnum()])[:6] or "png"
        if safe_ext not in ("png", "jpg", "jpeg", "webp"):
            safe_ext = "png"
        if safe_ext == "jpeg":
            safe_ext = "jpg"
        return f"ai_cover_{file_id}_{safe_platform}_{ts}.{safe_ext}"

    def _row_get(self, row, key: str, default=None):
        """
        sqlite3.Row supports `row["col"]` but not `row.get("col")`.
        This helper normalizes access for dict / sqlite3.Row / SQLAlchemy RowMapping.
        """
        if row is None:
            return default
        if isinstance(row, Mapping):
            return row.get(key, default)
        try:
            return row[key]
        except Exception:
            return default

    async def _ensure_first_frame_file_async(self, video_path: str, file_id: int) -> str:
        """
        Async wrapper for first-frame extraction with concurrency control.
        Uses Redis for caching and distributed locking, falls back to semaphore if Redis unavailable.
        """
        out_name = self._first_frame_filename(file_id)
        out_path = self.covers_dir / out_name
        rel_path = self._cover_rel_path(out_name)

        # Early return if file already exists (avoid lock overhead)
        if out_path.exists():
            return rel_path

        redis = get_redis()

        # Try Redis distributed lock first
        if redis:
            cache_key = f"first_frame:path:{file_id}"
            lock_key = f"lock:first_frame:{file_id}"

            # Check cache
            try:
                cached = redis.get(cache_key)
                if cached and Path(self.video_dir / cached).exists():
                    logger.debug(f"First frame cache hit for file {file_id}")
                    return cached
            except Exception as e:
                logger.warning(f"Redis cache read error: {e}")

            # Acquire distributed lock
            lock = None
            try:
                lock = redis.lock(lock_key, timeout=60, blocking_timeout=10)
                acquired = lock.acquire(blocking=True)

                if not acquired:
                    # Another process is generating, wait and retry cache
                    await asyncio.sleep(0.5)
                    try:
                        cached = redis.get(cache_key)
                        if cached and Path(self.video_dir / cached).exists():
                            return cached
                    except Exception:
                        pass
                    # Fall through to generation if cache still empty

                # Double-check after acquiring lock
                if out_path.exists():
                    redis.setex(cache_key, 3600, rel_path)  # Cache for 1 hour
                    return rel_path

                # Generate first frame
                resolved = resolve_video_file(str(video_path))
                if not resolved or not Path(resolved).exists():
                    raise BadRequestException(f"视频文件不存在，无法生成首帧: {video_path}")

                # Use semaphore even with Redis to limit local resource usage
                async with _FFMPEG_SEMAPHORE:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        partial(extract_first_frame, resolved, str(out_path), overwrite=True)
                    )

                # Cache the result
                try:
                    redis.setex(cache_key, 3600, rel_path)  # Cache for 1 hour
                    logger.info(f"First frame generated and cached for file {file_id}")
                except Exception as e:
                    logger.warning(f"Redis cache write error: {e}")

                return rel_path

            except Exception as e:
                logger.warning(f"Redis lock error: {e}, falling back to local semaphore")
                # Fall through to semaphore-only logic
            finally:
                if lock:
                    try:
                        lock.release()
                    except Exception:
                        pass

        # Fallback: Use local semaphore only (no Redis)
        async with _FFMPEG_SEMAPHORE:
            # Double-check after acquiring semaphore
            if out_path.exists():
                return rel_path

            resolved = resolve_video_file(str(video_path))
            if not resolved or not Path(resolved).exists():
                raise BadRequestException(f"视频文件不存在，无法生成首帧: {video_path}")

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                partial(extract_first_frame, resolved, str(out_path), overwrite=True)
            )

        return rel_path

    def _ensure_first_frame_file(self, video_path: str, file_id: int) -> str:
        """Legacy sync method - kept for backward compatibility."""
        out_name = self._first_frame_filename(file_id)
        out_path = self.covers_dir / out_name
        if not out_path.exists():
            resolved = resolve_video_file(str(video_path))
            if not resolved or not Path(resolved).exists():
                raise BadRequestException(f"视频文件不存在，无法生成首帧: {video_path}")
            extract_first_frame(resolved, str(out_path), overwrite=True)
        return self._cover_rel_path(out_name)

    def _ensure_file_record_columns(self, cursor, db) -> None:
        # Ensure base table exists (dashboard may have created an older/partial schema)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                filesize REAL,
                file_path TEXT,
                upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending',
                published_at DATETIME,
                last_platform INTEGER,
                last_accounts TEXT,
                note TEXT,
                group_name TEXT
            )
        """)
        cursor.execute("PRAGMA table_info(file_records)")
        columns = {row[1] for row in cursor.fetchall()}

        # 兼容旧库：缺字段则补齐（避免 insert/query 失败）
        to_add: List[str] = []
        if "status" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN status TEXT DEFAULT 'pending'")
        if "published_at" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN published_at DATETIME")
        if "last_platform" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN last_platform INTEGER")
        if "last_accounts" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN last_accounts TEXT")
        if "note" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN note TEXT")
        if "group_name" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN group_name TEXT")
        if "upload_time" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN upload_time DATETIME")
        if "file_path" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN file_path TEXT")
        if "filesize" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN filesize REAL")
        if "filename" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN filename TEXT")

        # UI/AI metadata extra columns
        if "title" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN title TEXT")
        if "description" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN description TEXT")
        if "tags" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN tags TEXT")
        if "cover_image" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN cover_image TEXT")
        if "duration" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN duration REAL")
        if "video_width" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN video_width INTEGER")
        if "video_height" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN video_height INTEGER")
        if "aspect_ratio" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN aspect_ratio TEXT")
        if "orientation" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN orientation TEXT")
        if "ai_title" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN ai_title TEXT")
        if "ai_description" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN ai_description TEXT")
        if "ai_tags" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN ai_tags TEXT")
        if "ai_generated_at" not in columns:
            to_add.append("ALTER TABLE file_records ADD COLUMN ai_generated_at TIMESTAMP")

        for sql in to_add:
            try:
                cursor.execute(sql)
            except Exception:
                # 多进程/并发时可能已经添加过
                pass
        if to_add:
            db.commit()

    def _probe_duration_seconds(self, file_path: str) -> Optional[float]:
        """Compatibility wrapper; prefer `_probe_video_metadata` for full info."""
        resolved = self._resolve_video_path(file_path)
        if not resolved:
            return None
        return probe_video_metadata(resolved).get("duration")

    def _probe_video_metadata(self, file_path: str) -> dict:
        resolved = self._resolve_video_path(file_path)
        if not resolved:
            return {}
        return probe_video_metadata(resolved)

    def _resolve_video_path(self, file_path: str | None) -> Optional[str]:
        if not file_path:
            return None

        raw = str(file_path).strip()
        if not raw:
            return None

        try:
            resolved = resolve_video_file(raw)
            if resolved and Path(resolved).exists():
                return resolved
        except Exception:
            pass

        try:
            candidate = self.video_dir / Path(raw).name
            if candidate.exists():
                return str(candidate)
        except Exception:
            pass

        try:
            if Path(raw).exists():
                return raw
        except Exception:
            pass

        return None

    def _ensure_file_record_columns_mysql(self, conn) -> None:
        """
        Best-effort MySQL schema expansion for new metadata columns.
        Ignore failures to keep backward compatibility.
        """
        for sql in [
            "ALTER TABLE file_records ADD COLUMN video_width INT NULL",
            "ALTER TABLE file_records ADD COLUMN video_height INT NULL",
            "ALTER TABLE file_records ADD COLUMN aspect_ratio VARCHAR(32) NULL",
            "ALTER TABLE file_records ADD COLUMN orientation VARCHAR(16) NULL",
        ]:
            try:
                conn.execute(text(sql))
            except Exception:
                pass
        try:
            conn.commit()
        except Exception:
            pass

    async def ensure_first_frame(self, db, file_id: int) -> str:
        """
        Ensure a first-frame image exists on disk and return its relative path (covers/first_frame_<id>.png).

        Note: this does NOT modify `file_records.cover_image`; cover_image is reserved for user/AI covers.
        Uses async semaphore to limit concurrent ffmpeg processes.
        """
        if mysql_enabled():
            with sa_connection() as conn:
                row = conn.execute(
                    text("SELECT id, file_path FROM file_records WHERE id = :id"),
                    {"id": file_id},
                ).mappings().first()
                if not row:
                    raise NotFoundException(f"文件不存在: ID {file_id}")

                file_path = row.get("file_path")
                if not file_path:
                    raise BadRequestException("file_path 为空，无法生成首帧封面")
                rel = await self._ensure_first_frame_file_async(file_path, file_id)
                return rel

        cursor = db.cursor()
        self._ensure_file_record_columns(cursor, db)
        cursor.execute("SELECT file_path FROM file_records WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        if not row:
            raise NotFoundException(f"文件不存在: ID {file_id}")

        if isinstance(row, (tuple, list)):
            file_path = row[0] if len(row) > 0 else None
        else:
            file_path = self._row_get(row, "file_path")

        if not file_path:
            raise BadRequestException("file_path 为空，无法生成首帧封面")

        rel = await self._ensure_first_frame_file_async(str(file_path), file_id)
        return rel

    async def list_files(
        self,
        db,
        status: Optional[str] = None,
        group: Optional[str] = None,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 0
    ) -> FileListResponse:
        """List files with filtering and pagination"""
        if mysql_enabled():
            warnings.warn("SQLite file_records path is deprecated; using MySQL via DATABASE_URL", DeprecationWarning)
            where = ["1=1"]
            params: dict = {}

            if status:
                where.append("status = :status")
                params["status"] = status
            if group:
                where.append("group_name = :group_name")
                params["group_name"] = group
            if keyword:
                kw = f"%{keyword}%"
                where.append("(filename LIKE :kw OR title LIKE :kw OR description LIKE :kw OR tags LIKE :kw OR note LIKE :kw)")
                params["kw"] = kw

            where_sql = " AND ".join(where)
            order_sql = " ORDER BY upload_time DESC, id DESC"

            with sa_connection() as conn:
                total = conn.execute(
                    text(f"SELECT COUNT(*) AS cnt FROM file_records WHERE {where_sql}"),
                    params,
                ).mappings().one()["cnt"]

                sql = f"SELECT * FROM file_records WHERE {where_sql}{order_sql}"
                if limit > 0:
                    sql += " LIMIT :limit OFFSET :offset"
                    params = {**params, "limit": int(limit), "offset": int(skip)}
                rows = conn.execute(text(sql), params).mappings().all()

            items: List[FileResponse] = []
            for row in rows:
                row_dict = dict(row)
                items.append(
                    FileResponse(
                        id=row_dict["id"],
                        filename=row_dict["filename"],
                        filesize=row_dict["filesize"],
                        file_path=row_dict["file_path"],
                        upload_time=datetime.fromisoformat(row_dict["upload_time"]) if row_dict.get("upload_time") else None,
                        status=row_dict.get("status", "pending"),
                        published_at=datetime.fromisoformat(row_dict["published_at"]) if row_dict.get("published_at") else None,
                        last_platform=row_dict.get("last_platform"),
                        last_accounts=row_dict.get("last_accounts"),
                        note=row_dict.get("note"),
                        group_name=row_dict.get("group_name"),
                        title=row_dict.get("title"),
                        description=row_dict.get("description"),
                        tags=row_dict.get("tags"),
                        cover_image=row_dict.get("cover_image"),
                        ai_title=row_dict.get("ai_title"),
                        ai_description=row_dict.get("ai_description"),
                        ai_tags=row_dict.get("ai_tags"),
                        duration=row_dict.get("duration"),
                        video_width=row_dict.get("video_width"),
                        video_height=row_dict.get("video_height"),
                        aspect_ratio=row_dict.get("aspect_ratio"),
                        orientation=row_dict.get("orientation"),
                    )
                )

            return FileListResponse(total=int(total), items=items)

        cursor = db.cursor()
        self._ensure_file_record_columns(cursor, db)

        # Build query
        query = "SELECT * FROM file_records WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if group:
            query += " AND group_name = ?"
            params.append(group)

        # 添加全局搜索功能（文件名、标题、描述、标签）
        if keyword:
            keyword_like = f"%{keyword}%"
            query += """ AND (
                filename LIKE ? OR
                title LIKE ? OR
                description LIKE ? OR
                tags LIKE ? OR
                note LIKE ?
            )"""
            params.extend([keyword_like, keyword_like, keyword_like, keyword_like, keyword_like])

        # Count total
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        # Get paginated results
        query += " ORDER BY upload_time DESC"

        # 只有当limit > 0时才添加分页限制
        if limit > 0:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, skip])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        files = []
        for row in rows:
            # Convert Row to dict for easier access
            row_dict = dict(row)

            # Best-effort 修复缺失/异常的 filesize、duration（避免前端出现 NaN / 不显示时长）
            try:
                stored_path = row_dict.get("file_path")
                resolved_path = self._resolve_video_path(stored_path) if isinstance(stored_path, str) else None
                if resolved_path and Path(resolved_path).exists():
                    filesize = row_dict.get("filesize")
                    if not isinstance(filesize, (int, float)) or (isinstance(filesize, float) and (math.isnan(filesize) or not math.isfinite(filesize))) or filesize <= 0:
                        corrected = Path(resolved_path).stat().st_size / (1024 * 1024)
                        row_dict["filesize"] = corrected
                        cursor.execute("UPDATE file_records SET filesize = ? WHERE id = ?", (corrected, row_dict["id"]))
                        db.commit()

                    if row_dict.get("duration") is None:
                        meta = self._probe_video_metadata(resolved_path)
                        duration = meta.get("duration")
                        if duration:
                            row_dict["duration"] = duration
                            cursor.execute("UPDATE file_records SET duration = ? WHERE id = ?", (duration, row_dict["id"]))
                            db.commit()

                    if row_dict.get("video_width") is None or row_dict.get("video_height") is None:
                        meta = self._probe_video_metadata(resolved_path)
                        w, h = meta.get("width"), meta.get("height")
                        ar, ori = meta.get("aspect_ratio"), meta.get("orientation")
                        if w and h:
                            row_dict["video_width"] = w
                            row_dict["video_height"] = h
                            row_dict["aspect_ratio"] = ar
                            row_dict["orientation"] = ori
                            cursor.execute(
                                "UPDATE file_records SET video_width = ?, video_height = ?, aspect_ratio = ?, orientation = ? WHERE id = ?",
                                (w, h, ar, ori, row_dict["id"]),
                            )
                            db.commit()
            except Exception:
                pass

            files.append(FileResponse(
                id=row_dict['id'],
                filename=row_dict['filename'],
                filesize=row_dict['filesize'],
                file_path=row_dict['file_path'],
                upload_time=datetime.fromisoformat(row_dict['upload_time']) if row_dict.get('upload_time') else None,
                status=row_dict.get('status', 'pending'),
                published_at=datetime.fromisoformat(row_dict['published_at']) if row_dict.get('published_at') else None,
                last_platform=row_dict.get('last_platform'),
                last_accounts=row_dict.get('last_accounts'),
                note=row_dict.get('note'),
                group_name=row_dict.get('group_name'),
                title=row_dict.get('title'),
                description=row_dict.get('description'),
                tags=row_dict.get('tags'),
                cover_image=row_dict.get('cover_image'),
                ai_title=row_dict.get('ai_title'),
                ai_description=row_dict.get('ai_description'),
                ai_tags=row_dict.get('ai_tags'),
                duration=row_dict.get('duration'),
                video_width=row_dict.get("video_width"),
                video_height=row_dict.get("video_height"),
                aspect_ratio=row_dict.get("aspect_ratio"),
                orientation=row_dict.get("orientation"),
            ))

        return FileListResponse(total=total, items=files)

    async def get_file(self, db, file_id: int) -> Optional[FileResponse]:
        """Get single file by ID"""
        if mysql_enabled():
            warnings.warn("SQLite file_records path is deprecated; using MySQL via DATABASE_URL", DeprecationWarning)
            with sa_connection() as conn:
                row = conn.execute(
                    text("SELECT * FROM file_records WHERE id = :id"),
                    {"id": file_id},
                ).mappings().first()
            if not row:
                return None
            row_dict = dict(row)
            return FileResponse(
                id=row_dict['id'],
                filename=row_dict['filename'],
                filesize=row_dict['filesize'],
                file_path=row_dict['file_path'],
                upload_time=datetime.fromisoformat(row_dict['upload_time']) if row_dict.get('upload_time') else None,
                status=row_dict.get('status', 'pending'),
                published_at=datetime.fromisoformat(row_dict['published_at']) if row_dict.get('published_at') else None,
                last_platform=row_dict.get('last_platform'),
                last_accounts=row_dict.get('last_accounts'),
                note=row_dict.get('note'),
                group_name=row_dict.get('group_name'),
                title=row_dict.get('title'),
                description=row_dict.get('description'),
                tags=row_dict.get('tags'),
                cover_image=row_dict.get('cover_image'),
                ai_title=row_dict.get('ai_title'),
                ai_description=row_dict.get('ai_description'),
                ai_tags=row_dict.get('ai_tags'),
                duration=row_dict.get('duration'),
                video_width=row_dict.get("video_width"),
                video_height=row_dict.get("video_height"),
                aspect_ratio=row_dict.get("aspect_ratio"),
                orientation=row_dict.get("orientation"),
            )

        cursor = db.cursor()
        self._ensure_file_record_columns(cursor, db)
        cursor.execute("SELECT * FROM file_records WHERE id = ?", (file_id,))
        row = cursor.fetchone()

        if not row:
            return None

        # Convert Row to dict
        row_dict = dict(row)
        return FileResponse(
            id=row_dict['id'],
            filename=row_dict['filename'],
            filesize=row_dict['filesize'],
            file_path=row_dict['file_path'],
            upload_time=datetime.fromisoformat(row_dict['upload_time']) if row_dict.get('upload_time') else None,
            status=row_dict.get('status', 'pending'),
            published_at=datetime.fromisoformat(row_dict['published_at']) if row_dict.get('published_at') else None,
            last_platform=row_dict.get('last_platform'),
            last_accounts=row_dict.get('last_accounts'),
            note=row_dict.get('note'),
            group_name=row_dict.get('group_name'),
            title=row_dict.get('title'),
            description=row_dict.get('description'),
            tags=row_dict.get('tags'),
            cover_image=row_dict.get('cover_image'),
            ai_title=row_dict.get('ai_title'),
            ai_description=row_dict.get('ai_description'),
            ai_tags=row_dict.get('ai_tags'),
            duration=row_dict.get('duration'),
            video_width=row_dict.get("video_width"),
            video_height=row_dict.get("video_height"),
            aspect_ratio=row_dict.get("aspect_ratio"),
            orientation=row_dict.get("orientation"),
        )

    async def save_file_record(
        self,
        db,
        filename: str,
        file_path: str,
        filesize_mb: float,
        note: Optional[str] = None,
        group_name: Optional[str] = None
    ) -> int:
        """Save file record to database"""
        if mysql_enabled():
            warnings.warn("SQLite file_records path is deprecated; using MySQL via DATABASE_URL", DeprecationWarning)
            upload_time = now_beijing_iso()
            title = Path(filename).stem
            meta = self._probe_video_metadata(file_path)
            duration = meta.get("duration")
            video_width = meta.get("width")
            video_height = meta.get("height")
            aspect_ratio = meta.get("aspect_ratio")
            orientation = meta.get("orientation")

            with sa_connection() as conn:
                self._ensure_file_record_columns_mysql(conn)
                file_id = None
                try:
                    res = conn.execute(
                        text(
                            """
                            INSERT INTO file_records (
                                filename, file_path, filesize, upload_time, status, note, group_name, title, duration,
                                video_width, video_height, aspect_ratio, orientation
                            ) VALUES (
                                :filename, :file_path, :filesize, :upload_time, :status, :note, :group_name, :title, :duration,
                                :video_width, :video_height, :aspect_ratio, :orientation
                            )
                            """
                        ),
                        {
                            "filename": filename,
                            "file_path": file_path,
                            "filesize": filesize_mb,
                            "upload_time": upload_time,
                            "status": "pending",
                            "note": note,
                            "group_name": group_name,
                            "title": title,
                            "duration": duration,
                            "video_width": video_width,
                            "video_height": video_height,
                            "aspect_ratio": aspect_ratio,
                            "orientation": orientation,
                        },
                    )
                    file_id = getattr(res, "lastrowid", None)
                except Exception as e:
                    # Backward compatible fallback: if schema migration fails (no privileges / different schema),
                    # insert without new columns.
                    logger.warning(f"[FileService] MySQL insert with video metadata failed, fallback to base columns: {e}")
                    res = conn.execute(
                        text(
                            """
                            INSERT INTO file_records (
                                filename, file_path, filesize, upload_time, status, note, group_name, title, duration
                            ) VALUES (
                                :filename, :file_path, :filesize, :upload_time, :status, :note, :group_name, :title, :duration
                            )
                            """
                        ),
                        {
                            "filename": filename,
                            "file_path": file_path,
                            "filesize": filesize_mb,
                            "upload_time": upload_time,
                            "status": "pending",
                            "note": note,
                            "group_name": group_name,
                            "title": title,
                            "duration": duration,
                        },
                    )
                    file_id = getattr(res, "lastrowid", None)

            logger.info(f"File record saved (MySQL): {filename} (ID: {file_id})")
            fid = int(file_id) if file_id is not None else 0
            if fid:
                try:
                    await self.ensure_first_frame(db, fid)
                except Exception as e:
                    logger.debug(f"First-frame extraction skipped: {e}")
            return fid

        cursor = db.cursor()
        self._ensure_file_record_columns(cursor, db)

        upload_time = now_beijing_iso()
        
        # Auto-generate title from filename (remove extension)
        title = Path(filename).stem

        meta = self._probe_video_metadata(file_path)
        duration = meta.get("duration")
        video_width = meta.get("width")
        video_height = meta.get("height")
        aspect_ratio = meta.get("aspect_ratio")
        orientation = meta.get("orientation")

        cursor.execute("""
            INSERT INTO file_records (
                filename, file_path, filesize, upload_time, status, note, group_name, title, duration,
                video_width, video_height, aspect_ratio, orientation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            filename,
            file_path,
            filesize_mb,
            upload_time,
            'pending',
            note,
            group_name,
            title,
            duration,
            video_width,
            video_height,
            aspect_ratio,
            orientation,
        ))

        db.commit()
        file_id = cursor.lastrowid

        logger.info(f"File record saved: {filename} (ID: {file_id})")
        try:
            await self.ensure_first_frame(db, int(file_id))
        except Exception as e:
            logger.debug(f"First-frame extraction skipped: {e}")
        return file_id

    async def generate_ai_cover(
        self,
        db,
        file_id: int,
        *,
        platform_name: str,
        aspect_ratio: str,
        style_hint: str = "",
        prompt_override: str = "",
        image_bytes_override: Optional[bytes] = None,
    ) -> dict:
        """
        Generate a unified AI cover from the video's first frame, store it under VIDEO_FILES_DIR/covers,
        update file_records.cover_image, and return paths.
        """
        from automation.cover_generation import build_prompt_from_image, build_unified_cover_prompt, generate_cover_image

        first_rel = await self.ensure_first_frame(db, file_id)
        first_path = (self.video_dir / Path(first_rel)).resolve()
        if not first_path.exists():
            raise RuntimeError("first frame not found on disk")
        first_bytes = first_path.read_bytes()
        base_image_bytes = image_bytes_override or first_bytes

        prompt = (prompt_override or "").strip()
        base_platform = platform_name or "全平台"
        if not prompt:
            try:
                prompt = build_prompt_from_image(
                    base_image_bytes,
                    platform_name=base_platform,
                    aspect_ratio=aspect_ratio,
                    style_hint=style_hint,
                )
            except Exception as e:
                logger.warning(f"封面提示词生成失败，使用默认模板: {e}")
                prompt = build_unified_cover_prompt(
                    platform_name=base_platform,
                    aspect_ratio=aspect_ratio,
                    extra_style=(style_hint or "").strip(),
                )
        else:
            # 用户输入作为“额外要求”，仍附带统一的封面规范，避免出现长句文字/水印等问题
            prompt = (
                build_unified_cover_prompt(
                    platform_name=base_platform,
                    aspect_ratio=aspect_ratio,
                    extra_style=(style_hint or "").strip(),
                )
                + f"\n用户额外要求：{prompt}"
            )

        result = await generate_cover_image(image_bytes=base_image_bytes, prompt=prompt, aspect_ratio=aspect_ratio)
        ct = (result.content_type or "").lower()
        ext = "png"
        if "jpeg" in ct or "jpg" in ct:
            ext = "jpg"
        elif "png" in ct:
            ext = "png"
        elif "webp" in ct:
            ext = "webp"

        out_name = self._ai_cover_filename(file_id, platform_name, ext=ext)
        out_path = self.covers_dir / out_name
        out_path.write_bytes(result.image_bytes)
        rel = self._cover_rel_path(out_name)

        if mysql_enabled():
            with sa_connection() as conn:
                conn.execute(
                    text("UPDATE file_records SET cover_image = :c WHERE id = :id"),
                    {"c": rel, "id": file_id},
                )
                conn.commit()
        else:
            cursor = db.cursor()
            self._ensure_file_record_columns(cursor, db)
            cursor.execute("UPDATE file_records SET cover_image = ? WHERE id = ?", (rel, file_id))
            db.commit()

        return {
            "cover_path": rel,
            "first_frame_path": first_rel,
            "prompt": prompt,
            "raw_url": result.raw_url,
        }

    async def update_file(self, db, file_id: int, update_data: FileUpdate) -> bool:
        """Update file metadata"""
        fields_set = (
            getattr(update_data, "model_fields_set", None)
            or getattr(update_data, "__fields_set__", None)
            or set()
        )
        if mysql_enabled():
            warnings.warn("SQLite file_records path is deprecated; using MySQL via DATABASE_URL", DeprecationWarning)
            updates = []
            params: dict = {"id": file_id}

            if "filename" in fields_set:
                updates.append("filename = :filename")
                params["filename"] = update_data.filename
            if "note" in fields_set:
                updates.append("note = :note")
                params["note"] = update_data.note
            if "group_name" in fields_set:
                updates.append("group_name = :group_name")
                params["group_name"] = update_data.group_name
            if "status" in fields_set:
                updates.append("status = :status")
                params["status"] = update_data.status
            if "title" in fields_set:
                updates.append("title = :title")
                params["title"] = update_data.title
            if "description" in fields_set:
                updates.append("description = :description")
                params["description"] = update_data.description
            if "tags" in fields_set:
                updates.append("tags = :tags")
                params["tags"] = update_data.tags
            if "cover_image" in fields_set:
                updates.append("cover_image = :cover_image")
                params["cover_image"] = update_data.cover_image
            if "ai_title" in fields_set:
                updates.append("ai_title = :ai_title")
                params["ai_title"] = update_data.ai_title
            if "ai_description" in fields_set:
                updates.append("ai_description = :ai_description")
                params["ai_description"] = update_data.ai_description
            if "ai_tags" in fields_set:
                updates.append("ai_tags = :ai_tags")
                params["ai_tags"] = update_data.ai_tags

            if not updates:
                return True

            with sa_connection() as conn:
                exists = conn.execute(text("SELECT 1 FROM file_records WHERE id = :id"), {"id": file_id}).first()
                if not exists:
                    return False
                conn.execute(text(f"UPDATE file_records SET {', '.join(updates)} WHERE id = :id"), params)

            logger.info(f"File record updated (MySQL): ID {file_id}")
            return True

        cursor = db.cursor()
        self._ensure_file_record_columns(cursor, db)

        # Check if file exists
        cursor.execute("SELECT id FROM file_records WHERE id = ?", (file_id,))
        if not cursor.fetchone():
            return False

        # Build update query dynamically
        updates = []
        params = []

        if "filename" in fields_set:
            updates.append("filename = ?")
            params.append(update_data.filename)

        if "note" in fields_set:
            updates.append("note = ?")
            params.append(update_data.note)

        if "group_name" in fields_set:
            updates.append("group_name = ?")
            params.append(update_data.group_name)

        if "status" in fields_set:
            updates.append("status = ?")
            params.append(update_data.status)
            
        if "title" in fields_set:
            updates.append("title = ?")
            params.append(update_data.title)
            
        if "description" in fields_set:
            updates.append("description = ?")
            params.append(update_data.description)
            
        if "tags" in fields_set:
            updates.append("tags = ?")
            params.append(update_data.tags)

        if "cover_image" in fields_set:
            updates.append("cover_image = ?")
            params.append(update_data.cover_image)

        if "ai_title" in fields_set:
            updates.append("ai_title = ?")
            params.append(update_data.ai_title)

        if "ai_description" in fields_set:
            updates.append("ai_description = ?")
            params.append(update_data.ai_description)

        if "ai_tags" in fields_set:
            updates.append("ai_tags = ?")
            params.append(update_data.ai_tags)

        if not updates:
            return True  # Nothing to update

        query = f"UPDATE file_records SET {', '.join(updates)} WHERE id = ?"
        params.append(file_id)

        cursor.execute(query, params)
        db.commit()

        logger.info(f"File record updated: ID {file_id}")
        return True

    async def list_groups(self, db) -> list[str]:
        """List distinct non-empty group names."""
        if mysql_enabled():
            warnings.warn("SQLite file_records path is deprecated; using MySQL via DATABASE_URL", DeprecationWarning)
            with sa_connection() as conn:
                rows = conn.execute(
                    text(
                        "SELECT DISTINCT group_name "
                        "FROM file_records "
                        "WHERE group_name IS NOT NULL AND group_name != '' "
                        "ORDER BY group_name"
                    )
                ).all()
            return [r[0] for r in rows if r and r[0]]

        cursor = db.cursor()
        self._ensure_file_record_columns(cursor, db)
        cursor.execute(
            "SELECT DISTINCT group_name FROM file_records "
            "WHERE group_name IS NOT NULL AND group_name != '' "
            "ORDER BY group_name"
        )
        return [r[0] for r in cursor.fetchall() if r and r[0]]

    async def rename_group(self, db, from_name: str, to_name: str) -> int:
        """Rename a group in bulk; returns number of affected rows."""
        from_name = (from_name or "").strip()
        to_name = (to_name or "").strip()
        if not from_name:
            raise BadRequestException("from_name 不能为空")
        if not to_name:
            raise BadRequestException("to_name 不能为空")
        if from_name == to_name:
            return 0

        if mysql_enabled():
            warnings.warn("SQLite file_records path is deprecated; using MySQL via DATABASE_URL", DeprecationWarning)
            with sa_connection() as conn:
                res = conn.execute(
                    text("UPDATE file_records SET group_name = :to WHERE group_name = :from"),
                    {"from": from_name, "to": to_name},
                )
                conn.commit()
                return int(getattr(res, "rowcount", 0) or 0)

        cursor = db.cursor()
        self._ensure_file_record_columns(cursor, db)
        cursor.execute(
            "UPDATE file_records SET group_name = ? WHERE group_name = ?",
            (to_name, from_name),
        )
        db.commit()
        return int(cursor.rowcount or 0)

    async def delete_group(self, db, name: str) -> int:
        """Delete a group in bulk (set group_name=NULL); returns number of affected rows."""
        name = (name or "").strip()
        if not name:
            raise BadRequestException("name 不能为空")

        if mysql_enabled():
            warnings.warn("SQLite file_records path is deprecated; using MySQL via DATABASE_URL", DeprecationWarning)
            with sa_connection() as conn:
                res = conn.execute(
                    text("UPDATE file_records SET group_name = NULL WHERE group_name = :name"),
                    {"name": name},
                )
                conn.commit()
                return int(getattr(res, "rowcount", 0) or 0)

        cursor = db.cursor()
        self._ensure_file_record_columns(cursor, db)
        cursor.execute(
            "UPDATE file_records SET group_name = NULL WHERE group_name = ?",
            (name,),
        )
        db.commit()
        return int(cursor.rowcount or 0)

    async def rename_file(self, db, file_id: int, new_filename: str, update_disk: bool = True) -> bool:
        """
        重命名文件（同步数据库和磁盘）

        Args:
            db: 数据库连接
            file_id: 文件ID
            new_filename: 新文件名（含扩展名）
            update_disk: 是否同步修改磁盘文件名

        Returns:
            bool: 是否成功
        """
        # 清理新文件名，防止路径遍历攻击
        safe_new_filename = Path(new_filename.strip()).name
        if not safe_new_filename:
            raise BadRequestException("文件名不能为空")

        if mysql_enabled():
            warnings.warn("SQLite file_records path is deprecated; using MySQL via DATABASE_URL", DeprecationWarning)
            with sa_connection() as conn:
                # 查询现有文件信息
                row = conn.execute(
                    text("SELECT id, filename, file_path FROM file_records WHERE id = :id"),
                    {"id": file_id},
                ).mappings().first()

                if not row:
                    return False

                old_filename = row.get("filename")
                old_file_path = row.get("file_path")

                # 如果需要同步修改磁盘文件
                if update_disk and old_file_path:
                    old_path = self._resolve_video_path(old_file_path)
                    if old_path and Path(old_path).exists():
                        old_full_path = Path(old_path)
                        new_full_path = old_full_path.parent / safe_new_filename

                        # 检查目标文件是否已存在
                        if new_full_path.exists() and new_full_path != old_full_path:
                            raise BadRequestException(f"目标文件已存在: {safe_new_filename}")

                        try:
                            # 重命名磁盘文件
                            old_full_path.rename(new_full_path)
                            logger.info(f"File renamed on disk: {old_full_path} -> {new_full_path}")

                            # 更新数据库中的 file_path（只存储文件名）
                            conn.execute(
                                text("UPDATE file_records SET filename = :filename, file_path = :file_path WHERE id = :id"),
                                {"filename": safe_new_filename, "file_path": safe_new_filename, "id": file_id},
                            )
                        except Exception as e:
                            logger.error(f"Failed to rename file on disk: {e}")
                            raise BadRequestException(f"重命名文件失败: {str(e)}")
                    else:
                        # 文件不存在，仅更新数据库
                        conn.execute(
                            text("UPDATE file_records SET filename = :filename WHERE id = :id"),
                            {"filename": safe_new_filename, "id": file_id},
                        )
                else:
                    # 仅更新数据库中的 filename（显示名称）
                    conn.execute(
                        text("UPDATE file_records SET filename = :filename WHERE id = :id"),
                        {"filename": safe_new_filename, "id": file_id},
                    )

                conn.commit()
                logger.info(f"File record renamed (MySQL): ID {file_id}, old: {old_filename}, new: {safe_new_filename}")
                return True

        # SQLite 路径
        cursor = db.cursor()
        self._ensure_file_record_columns(cursor, db)

        # 查询现有文件信息
        cursor.execute("SELECT filename, file_path FROM file_records WHERE id = ?", (file_id,))
        row = cursor.fetchone()

        if not row:
            return False

        old_filename = self._row_get(row, "filename")
        old_file_path = self._row_get(row, "file_path")

        # 如果需要同步修改磁盘文件
        if update_disk and old_file_path:
            old_path = self._resolve_video_path(old_file_path)
            if old_path and Path(old_path).exists():
                old_full_path = Path(old_path)
                new_full_path = old_full_path.parent / safe_new_filename

                # 检查目标文件是否已存在
                if new_full_path.exists() and new_full_path != old_full_path:
                    raise BadRequestException(f"目标文件已存在: {safe_new_filename}")

                try:
                    # 重命名磁盘文件
                    old_full_path.rename(new_full_path)
                    logger.info(f"File renamed on disk: {old_full_path} -> {new_full_path}")

                    # 更新数据库中的 file_path（只存储文件名）
                    cursor.execute(
                        "UPDATE file_records SET filename = ?, file_path = ? WHERE id = ?",
                        (safe_new_filename, safe_new_filename, file_id)
                    )
                except Exception as e:
                    logger.error(f"Failed to rename file on disk: {e}")
                    raise BadRequestException(f"重命名文件失败: {str(e)}")
            else:
                # 文件不存在，仅更新数据库
                cursor.execute(
                    "UPDATE file_records SET filename = ? WHERE id = ?",
                    (safe_new_filename, file_id)
                )
        else:
            # 仅更新数据库中的 filename（显示名称）
            cursor.execute(
                "UPDATE file_records SET filename = ? WHERE id = ?",
                (safe_new_filename, file_id)
            )

        db.commit()
        logger.info(f"File record renamed: ID {file_id}, old: {old_filename}, new: {safe_new_filename}")
        return True

    async def delete_file(self, db, file_id: int) -> bool:
        """Delete file and record (use path resolution to avoid blocking)"""
        logger.info(f"[FileService] Starting delete: file_id={file_id}")

        if mysql_enabled():
            warnings.warn("SQLite file_records path is deprecated; using MySQL via DATABASE_URL", DeprecationWarning)
            with sa_connection() as conn:
                row = conn.execute(
                    text("SELECT file_path FROM file_records WHERE id = :id"),
                    {"id": file_id},
                ).mappings().first()
                if not row:
                    logger.warning(f"[FileService] File not found: file_id={file_id}")
                    return False
                stored_path = row.get("file_path")
                logger.info(f"[FileService] Found file record: stored_path={stored_path}")

                # Delete database record first
                conn.execute(text("DELETE FROM file_records WHERE id = :id"), {"id": file_id})
                conn.commit()
                logger.info(f"[FileService] Database record deleted: file_id={file_id}")

            # Then delete physical file (non-blocking, with proper path resolution)
            if stored_path:
                try:
                    resolved_path = self._resolve_video_path(stored_path)
                    logger.info(f"[FileService] Resolved path: {resolved_path}")
                    if resolved_path and Path(resolved_path).exists():
                        os.remove(resolved_path)
                        logger.info(f"[FileService] Physical file deleted: {resolved_path}")
                    else:
                        logger.warning(f"[FileService] File not found on disk (skipped): {stored_path}")
                except Exception as e:
                    logger.warning(f"[FileService] Failed to delete physical file (ID {file_id}): {e}", exc_info=True)

            logger.info(f"[FileService] Delete completed (MySQL): file_id={file_id}")
            return True

        cursor = db.cursor()

        # Get file info
        cursor.execute("SELECT file_path FROM file_records WHERE id = ?", (file_id,))
        row = cursor.fetchone()

        if not row:
            logger.warning(f"[FileService] File not found: file_id={file_id}")
            return False

        stored_path = row['file_path']
        logger.info(f"[FileService] Found file record: stored_path={stored_path}")

        # Delete database record first
        cursor.execute("DELETE FROM file_records WHERE id = ?", (file_id,))
        db.commit()
        logger.info(f"[FileService] Database record deleted: file_id={file_id}")

        # Then delete physical file (non-blocking, with proper path resolution)
        if stored_path:
            try:
                resolved_path = self._resolve_video_path(stored_path)
                logger.info(f"[FileService] Resolved path: {resolved_path}")
                if resolved_path and Path(resolved_path).exists():
                    os.remove(resolved_path)
                    logger.info(f"[FileService] Physical file deleted: {resolved_path}")
                else:
                    logger.warning(f"[FileService] File not found on disk (skipped): {stored_path}")
            except Exception as e:
                logger.warning(f"[FileService] Failed to delete physical file (ID {file_id}): {e}", exc_info=True)

        logger.info(f"[FileService] Delete completed: file_id={file_id}")
        return True

    async def batch_delete_files(self, db, file_ids: list[int]) -> dict:
        """
        批量删除文件（高性能版本）

        优势：
        - 单次数据库查询获取所有文件路径
        - 批量删除数据库记录
        - 批量删除物理文件
        - 支持部分成功，返回失败列表

        Args:
            db: 数据库连接
            file_ids: 要删除的文件ID列表

        Returns:
            dict: {
                "success_count": 成功数量,
                "failed_count": 失败数量,
                "failed_ids": 失败的文件ID列表
            }
        """
        logger.info(f"[FileService] Starting batch delete: {len(file_ids)} files")

        success_count = 0
        failed_count = 0
        failed_ids = []

        if mysql_enabled():
            warnings.warn("SQLite file_records path is deprecated; using MySQL via DATABASE_URL", DeprecationWarning)
            with sa_connection() as conn:
                # 批量查询所有文件路径
                placeholders = ", ".join([":id" + str(i) for i in range(len(file_ids))])
                params = {f"id{i}": file_id for i, file_id in enumerate(file_ids)}
                query = f"SELECT id, file_path FROM file_records WHERE id IN ({placeholders})"
                rows = conn.execute(text(query), params).mappings().fetchall()

                # 构建路径映射
                file_path_map = {row["id"]: row["file_path"] for row in rows}
                logger.info(f"[FileService] Found {len(file_path_map)} files to delete")

                # 批量删除数据库记录
                if file_path_map:
                    delete_query = f"DELETE FROM file_records WHERE id IN ({placeholders})"
                    conn.execute(text(delete_query), params)
                    conn.commit()
                    logger.info(f"[FileService] Database records deleted: {len(file_path_map)} files")

            # 批量删除物理文件
            for file_id, stored_path in file_path_map.items():
                if stored_path:
                    try:
                        resolved_path = self._resolve_video_path(stored_path)
                        if resolved_path and Path(resolved_path).exists():
                            os.remove(resolved_path)
                            success_count += 1
                            logger.debug(f"[FileService] Deleted file {file_id}: {resolved_path}")
                        else:
                            logger.warning(f"[FileService] File not found on disk: {stored_path}")
                            success_count += 1  # 记录已删除，文件不存在也算成功
                    except Exception as e:
                        logger.warning(f"[FileService] Failed to delete file {file_id}: {e}")
                        failed_count += 1
                        failed_ids.append(file_id)
                else:
                    success_count += 1

            # 统计未找到的文件ID
            missing_ids = set(file_ids) - set(file_path_map.keys())
            failed_count += len(missing_ids)
            failed_ids.extend(missing_ids)

            logger.info(f"[FileService] Batch delete completed (MySQL): success={success_count}, failed={failed_count}")
            return {
                "success_count": success_count,
                "failed_count": failed_count,
                "failed_ids": failed_ids
            }

        cursor = db.cursor()

        # 批量查询所有文件路径
        placeholders = ", ".join(["?"] * len(file_ids))
        query = f"SELECT id, file_path FROM file_records WHERE id IN ({placeholders})"
        cursor.execute(query, file_ids)
        rows = cursor.fetchall()

        # 构建路径映射
        file_path_map = {row["id"]: row["file_path"] for row in rows}
        logger.info(f"[FileService] Found {len(file_path_map)} files to delete")

        # 批量删除数据库记录
        if file_path_map:
            delete_query = f"DELETE FROM file_records WHERE id IN ({placeholders})"
            cursor.execute(delete_query, list(file_path_map.keys()))
            db.commit()
            logger.info(f"[FileService] Database records deleted: {len(file_path_map)} files")

        # 批量删除物理文件
        for file_id, stored_path in file_path_map.items():
            if stored_path:
                try:
                    resolved_path = self._resolve_video_path(stored_path)
                    if resolved_path and Path(resolved_path).exists():
                        os.remove(resolved_path)
                        success_count += 1
                        logger.debug(f"[FileService] Deleted file {file_id}: {resolved_path}")
                    else:
                        logger.warning(f"[FileService] File not found on disk: {stored_path}")
                        success_count += 1  # 记录已删除，文件不存在也算成功
                except Exception as e:
                    logger.warning(f"[FileService] Failed to delete file {file_id}: {e}")
                    failed_count += 1
                    failed_ids.append(file_id)
            else:
                success_count += 1

        # 统计未找到的文件ID
        missing_ids = set(file_ids) - set(file_path_map.keys())
        failed_count += len(missing_ids)
        failed_ids.extend(missing_ids)

        logger.info(f"[FileService] Batch delete completed: success={success_count}, failed={failed_count}")
        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "failed_ids": failed_ids
        }

    async def get_stats(self, db) -> FileStatsResponse:
        """Get file statistics"""
        if mysql_enabled():
            warnings.warn("SQLite file_records path is deprecated; using MySQL via DATABASE_URL", DeprecationWarning)
            with sa_connection() as conn:
                total_files = conn.execute(text("SELECT COUNT(*) AS c FROM file_records")).mappings().one()["c"]
                pending_files = conn.execute(text("SELECT COUNT(*) AS c FROM file_records WHERE status = 'pending'")).mappings().one()["c"]
                published_files = conn.execute(text("SELECT COUNT(*) AS c FROM file_records WHERE status = 'published'")).mappings().one()["c"]
                total_size_mb = conn.execute(text("SELECT COALESCE(SUM(filesize), 0) AS s FROM file_records")).mappings().one()["s"]

            avg_size_mb = (total_size_mb / total_files) if total_files else 0
            return FileStatsResponse(
                total_files=int(total_files),
                pending_files=int(pending_files),
                published_files=int(published_files),
                total_size_mb=round(float(total_size_mb or 0), 2),
                avg_size_mb=round(float(avg_size_mb or 0), 2)
            )

        cursor = db.cursor()

        # Total files
        cursor.execute("SELECT COUNT(*) FROM file_records")
        total_files = cursor.fetchone()[0]

        # Pending files
        cursor.execute("SELECT COUNT(*) FROM file_records WHERE status = 'pending'")
        pending_files = cursor.fetchone()[0]

        # Published files
        cursor.execute("SELECT COUNT(*) FROM file_records WHERE status = 'published'")
        published_files = cursor.fetchone()[0]

        # Total size
        cursor.execute("SELECT COALESCE(SUM(filesize), 0) FROM file_records")
        total_size_mb = cursor.fetchone()[0]

        # Average size
        avg_size_mb = total_size_mb / total_files if total_files > 0 else 0

        return FileStatsResponse(
            total_files=total_files,
            pending_files=pending_files,
            published_files=published_files,
            total_size_mb=round(total_size_mb, 2),
            avg_size_mb=round(avg_size_mb, 2)
        )

    def validate_disk_space(self, required_mb: float) -> bool:
        """Check if enough disk space is available"""
        try:
            stat = shutil.disk_usage(str(self.video_dir))
            available_mb = stat.free / (1024 * 1024)

            # Require 2x the file size for safety
            required_space_mb = required_mb * 2

            if available_mb < required_space_mb:
                logger.warning(
                    f"Insufficient disk space: {available_mb:.2f}MB available, "
                    f"{required_space_mb:.2f}MB required"
                )
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking disk space: {e}")
            return False

    async def sync_files_from_disk(self, db) -> dict:
        """
        同步磁盘文件到数据库
        扫描 videoFile 目录，将未入库的文件添加到数据库
        """
        if mysql_enabled():
            warnings.warn("SQLite file_records path is deprecated; using MySQL via DATABASE_URL", DeprecationWarning)
            with sa_connection() as conn:
                rows = conn.execute(text("SELECT filename FROM file_records")).mappings().all()
                existing_filenames = {r.get("filename") for r in rows if r.get("filename")}
        else:
            cursor = db.cursor()

            # 获取数据库中已有的文件名
            cursor.execute("SELECT filename FROM file_records")
            existing_filenames = {row['filename'] for row in cursor.fetchall()}
        
        logger.info(f"📂 Scanning directory: {self.video_dir}")
        logger.info(f"💾 Existing records in DB: {len(existing_filenames)}")
        
        # 统计信息
        stats = {
            "scanned": 0,
            "added": 0,
            "skipped": 0,
            "errors": 0,
            "added_files": []
        }
        
        # 支持的视频格式
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm', '.m4v'}
        
        # 扫描目录
        if not self.video_dir.exists():
            logger.warning(f"Video directory does not exist: {self.video_dir}")
            return stats
        
        for file_path in self.video_dir.iterdir():
            if not file_path.is_file():
                continue
            
            # 跳过隐藏文件和非视频文件
            if file_path.name.startswith('.'):
                continue
            
            if file_path.suffix.lower() not in video_extensions:
                logger.debug(f"Skipping non-video file: {file_path.name}")
                continue
            
            stats["scanned"] += 1
            
            # 检查文件是否已在数据库中 (基于文件名)
            if file_path.name in existing_filenames:
                stats["skipped"] += 1
                logger.debug(f"File already in DB: {file_path.name}")
                continue
            
            # 添加新文件到数据库
            try:
                filesize_mb = file_path.stat().st_size / (1024 * 1024)
                upload_time = datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                
                # Auto-generate title from filename
                title = file_path.stem
                duration = self._probe_duration_seconds(str(file_path))
                
                if mysql_enabled():
                    with sa_connection() as conn:
                        conn.execute(
                            text(
                                """
                                INSERT INTO file_records (
                                    filename, file_path, filesize, upload_time, status, note, group_name, title, duration
                                ) VALUES (
                                    :filename, :file_path, :filesize, :upload_time, :status, :note, :group_name, :title, :duration
                                )
                                """
                            ),
                            {
                                "filename": file_path.name,
                                "file_path": str(file_path),
                                "filesize": filesize_mb,
                                "upload_time": upload_time,
                                "status": "pending",
                                "note": f"自动同步: {file_path.name}",
                                "group_name": None,
                                "title": title,
                                "duration": duration,
                            },
                        )
                else:
                    self._ensure_file_record_columns(cursor, db)
                    cursor.execute("""
                        INSERT INTO file_records (
                            filename, file_path, filesize, upload_time, status, note, group_name, title, duration
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        file_path.name,
                        str(file_path),
                        filesize_mb,
                        upload_time,
                        'pending',
                        f"自动同步: {file_path.name}",
                        None,
                        title,
                        duration
                    ))
                
                stats["added"] += 1
                stats["added_files"].append({
                    "filename": file_path.name,
                    "size_mb": round(filesize_mb, 2)
                })
                logger.info(f"✅ Added to DB: {file_path.name} ({filesize_mb:.2f}MB)")
                
            except Exception as e:
                stats["errors"] += 1
                logger.error(f"❌ Error adding {file_path.name}: {e}")
        
        # 提交事务（SQLite）
        if not mysql_enabled():
            db.commit()
        
        logger.info(
            f"🎉 Sync complete: Scanned={stats['scanned']}, "
            f"Added={stats['added']}, Skipped={stats['skipped']}, "
            f"Errors={stats['errors']}"
        )
        
        return stats
