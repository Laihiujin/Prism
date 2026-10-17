"""Durable login-to-publish distribution. Login credentials stay in the auth subsystem."""
import asyncio
import contextlib
import json
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator

PLATFORMS = {"xiaohongshu": 1, "tencent": 2, "douyin": 3, "kuaishou": 4,
             "bilibili": 5, "tiktok": 6, "youtube": 7}
SHANGHAI = timezone(timedelta(hours=8))


class MaterialBinding(BaseModel):
    file_id: int = Field(gt=0)
    presets: dict[str, str] = Field(min_length=1)


class DistributionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    materials: list[MaterialBinding] = Field(min_length=1, max_length=100)
    platforms: list[str] = Field(min_length=1, max_length=7)
    accounts_per_platform: int = Field(default=1, ge=1, le=100)
    allocation: Literal["one_per_account", "all_per_account"] = "one_per_account"
    auto_publish: bool = False
    schedule_type: Literal["immediate", "scheduled"] = "immediate"
    scheduled_time: datetime | None = None
    interval_seconds: int = Field(default=600, ge=60, le=86400)
    expires_hours: int = Field(default=24, ge=1, le=168)

    @model_validator(mode="after")
    def check_configuration(self):
        if len(set(self.platforms)) != len(self.platforms) or any(p not in PLATFORMS for p in self.platforms):
            raise ValueError("平台重复或尚未支持")
        if len({m.file_id for m in self.materials}) != len(self.materials):
            raise ValueError("素材重复")
        if self.allocation == "one_per_account" and self.accounts_per_platform > len(self.materials):
            raise ValueError("每账号一条时，账号数量不得超过素材数量")
        if self.schedule_type == "scheduled":
            if not self.scheduled_time:
                raise ValueError("请选择发布时间")
            value = self.scheduled_time
            self.scheduled_time = value.replace(tzinfo=SHANGHAI) if value.tzinfo is None else value
            if self.scheduled_time <= datetime.now(SHANGHAI):
                raise ValueError("发布时间必须在未来")
        for material in self.materials:
            if any(not material.presets.get(p) for p in self.platforms):
                raise ValueError("每条素材必须为每个目标平台绑定预设")
        return self


class QRDistributionService:
    def __init__(self, db_path=None):
        from fastapi_app.core.config import settings
        self.db_path = str(db_path or settings.DATABASE_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.owner = uuid.uuid4().hex
        self.runners = {}
        self.locks = {}
        self.supervisor = None
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS qr_distributions (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL, owner TEXT, lease_until REAL DEFAULT 0)""")

    @contextlib.contextmanager
    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, task_id):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM qr_distributions WHERE id=?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(404, "分发任务不存在")
        return json.loads(row[0])

    def list(self):
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM qr_distributions ORDER BY rowid DESC").fetchall()
        return [json.loads(row[0]) for row in rows]

    def save(self, task):
        with self.connect() as db:
            changed = db.execute("UPDATE qr_distributions SET payload=?, lease_until=? WHERE id=? AND owner=?",
                                 (json.dumps(task, ensure_ascii=False), time.time() + 600, task["id"], self.owner)).rowcount
        if not changed:
            raise HTTPException(409, "任务正由其他服务进程处理，请稍后重试")

    def acquire(self, task_id):
        with self.connect() as db:
            return bool(db.execute("UPDATE qr_distributions SET owner=?, lease_until=? WHERE id=? AND (owner=? OR lease_until<?)",
                                   (self.owner, time.time() + 600, task_id, self.owner, time.time())).rowcount)

    def create(self, request, db):
        from fastapi_app.api.v1.publish.material_presets import resolve_material_preset
        from fastapi_app.core.config import settings
        snapshot = []
        for material in request.materials:
            record = db.execute("SELECT * FROM file_records WHERE id=?", (material.file_id,)).fetchone()
            if record is None:
                raise HTTPException(404, f"素材 {material.file_id} 不存在")
            row = dict(record)
            if Path(row.get("file_path") or row.get("filename") or "").suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}:
                raise HTTPException(400, "扫码分发请选择视频素材")
            configurations = {}
            for platform in request.platforms:
                try:
                    preset = resolve_material_preset(settings.VIDEO_FILES_DIR, material.file_id, PLATFORMS[platform],
                                                     {str(PLATFORMS[platform]): material.presets[platform]})
                except (OSError, ValueError) as error:
                    raise HTTPException(400, f"素材 {material.file_id} 的 {platform} 预设无效") from error
                if not preset or not preset["title"].strip():
                    raise HTTPException(400, f"素材 {material.file_id} 的 {platform} 预设缺少标题")
                configurations[platform] = preset
            snapshot.append({"file_id": material.file_id, "name": row.get("filename") or str(material.file_id), "configurations": configurations})
        task = {"id": uuid.uuid4().hex, "name": request.name, "config": request.model_dump(mode="json"),
                "materials": snapshot, "status": "active", "created_at": time.time(),
                "expires_at": time.time() + request.expires_hours * 3600, "packages": [],
                "lanes": {p: {"status": "pending", "completed": 0, "refreshes": [], "next_refresh_at": 0,
                              "session_id": None, "qr_image": None, "account_alias": None} for p in request.platforms}}
        with self.connect() as conn:
            conn.execute("INSERT INTO qr_distributions(id,payload,owner,lease_until) VALUES (?,?,?,?)",
                         (task["id"], json.dumps(task, ensure_ascii=False), self.owner, time.time() + 600))
        self.ensure_runner(task["id"])
        return task

    def ensure_runner(self, task_id):
        if task_id not in self.runners or self.runners[task_id].done():
            self.runners[task_id] = asyncio.create_task(self.run(task_id))

    @staticmethod
    def has_automatic_work(task):
        return any(p.get('automatic_pending') for p in task['packages'])

    async def supervise(self):
        while True:
            for task in self.list():
                if task["status"] == "active" or self.has_automatic_work(task):
                    self.ensure_runner(task["id"])
                elif any(i["status"] == "submitting" for p in task["packages"] for i in p["items"]) and self.acquire(task["id"]):
                    async with self.locks.setdefault(task["id"], asyncio.Lock()):
                        recovered = self.get(task["id"])
                        for package in recovered["packages"]:
                            for item in package["items"]:
                                if item["status"] == "submitting":
                                    item.update(status="needs_review", error="提交结果待核对，请到任务管理检查")
                        self.save(recovered)
            await asyncio.sleep(30)

    async def start(self):
        # A process restart must never resend a submission whose outcome is unknown.
        for task in self.list():
            if self.acquire(task["id"]):
                for package in task["packages"]:
                    for item in package["items"]:
                        if item["status"] == "submitting":
                            item.update(status="needs_review", error="服务重启，提交结果待核对，请到任务管理检查")
                self.save(task)
            if task["status"] == "active" or self.has_automatic_work(task):
                self.ensure_runner(task["id"])

        if self.supervisor is None or self.supervisor.done():
            self.supervisor = asyncio.create_task(self.supervise())

    async def close(self):
        if self.supervisor:
            self.supervisor.cancel()
            await asyncio.gather(self.supervisor, return_exceptions=True)
        for runner in self.runners.values():
            runner.cancel()
        await asyncio.gather(*self.runners.values(), return_exceptions=True)
        with self.connect() as db:
            db.execute("UPDATE qr_distributions SET lease_until=0 WHERE owner=?", (self.owner,))

    async def run(self, task_id):
        try:
            while True:
                if self.acquire(task_id):
                    async with self.locks.setdefault(task_id, asyncio.Lock()):
                        task = self.get(task_id)
                        if task["status"] != "active" and not self.has_automatic_work(task):
                            return
                        for package in task["packages"]:
                            for item in package["items"]:
                                if item["status"] == "submitting":
                                    item.update(status="needs_review", error="提交结果待核对，请到任务管理检查，避免重复发布")
                        for package in task["packages"]:
                            if package.get("automatic_pending"):
                                await self.automatic_package(task, package)
                        if task["status"] != "active":
                            self.save(task)
                            return
                        if time.time() >= task["expires_at"]:
                            task["status"] = "expired"
                            await self.cancel_sessions(task)
                        else:
                            for platform, lane in task["lanes"].items():
                                if lane["completed"] < task["config"]["accounts_per_platform"]:
                                    await self.tick_lane(task, platform, lane)
                            if all(lane["completed"] >= task["config"]["accounts_per_platform"] for lane in task["lanes"].values()):
                                task["status"] = "completed"
                        self.save(task)
                        if task["status"] != "active":
                            return
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            raise
        except Exception:
            from fastapi_app.core.logger import logger
            logger.exception("扫码分发调度中断，任务保留，等待服务重启恢复")

    async def begin_login(self, platform, alias, sid=None):
        from fastapi_app.api.v1.auth.router import generate_qrcode
        from fastapi_app.api.v1.auth.schemas import PlatformType
        return await generate_qrcode(platform=PlatformType(platform), account_id=alias,
                                     login_role="creator", session_id=sid, headless=None)

    async def poll_login(self, sid):
        from fastapi_app.api.v1.auth.router import poll_login_status
        return await poll_login_status(sid)

    async def tick_lane(self, task, platform, lane):
        if lane.get("status") == "error" and time.time() < lane["next_refresh_at"]:
            return
        try:
            if lane.get("status") == "error":
                await self.refresh(task, platform, lane)
                return
            if not lane.get("session_id"):
                if time.time() < lane["next_refresh_at"]:
                    return
                await self.refresh(task, platform, lane)
                return
            # API memory can be lost independently of the worker. Re-register the
            # original alias/session; do not silently log in with an existing account.
            from fastapi_app.api.v1.auth.router import login_sessions
            from fastapi_app.api.v1.auth.schemas import PlatformType
            login_sessions.setdefault(lane["session_id"], {"platform": PlatformType(platform),
                "account_id": lane["account_alias"], "worker_session_id": lane["session_id"], "status": "waiting", "created_at": time.time()})
            result = await self.poll_login(lane["session_id"])
            lane["status"] = result.status
            lane["error"] = ""
            if result.status == "waiting" and platform not in ("tiktok", "youtube") and time.time() >= lane.get("next_snapshot_at", 0):
                lane["next_snapshot_at"] = time.time() + 30
                from automation_worker.client import get_worker_client
                with contextlib.suppress(Exception):
                    snapshot = await get_worker_client().qrcode_image(lane["session_id"])
                    if snapshot["qr_image"] != lane.get("qr_image"):
                        lane.update(qr_image=snapshot["qr_image"], qr_expires_at=time.time() + 300)
            if result.status == "confirmed":
                from myUtils.cookie_manager import cookie_manager
                data = result.data or {}
                worker_data = data.get("data") or data
                uid = (worker_data.get("user_info") or {}).get("user_id")
                account = cookie_manager.get_account_by_user_id(str(uid), platform="channels" if platform == "tencent" else platform) if uid else None
                account = account or cookie_manager.get_account_by_id(lane["account_alias"])
                if not account or account.get("status") != "valid":
                    raise ValueError("登录已确认，但账号尚未成功保存；请检查账号管理")
                account_id = account["account_id"]
                if not any(p["platform"] == platform and p["account_id"] == account_id for p in task["packages"]):
                    package = self.make_package(task, platform, account_id)
                    task["packages"].append(package)
                    lane["completed"] += 1
                    # Claim before queue submission. A disconnect cannot reassign it.
                    lane.update(session_id=None, qr_image=None, account_alias=None, refreshes=[], next_refresh_at=time.time() + 30)
                    self.save(task)
                    if task["config"]["auto_publish"]:
                        await self.automatic_package(task, package)
                else:
                    lane.update(session_id=None, qr_image=None, account_alias=None, next_refresh_at=time.time() + 30,
                                error="该账号已领取此分发任务，请使用另一个账号")
            elif (result.status == "expired" or result.status == "waiting" and platform not in ("tiktok", "youtube") and time.time() >= lane.get("qr_expires_at", float("inf"))) and time.time() >= lane["next_refresh_at"]:
                await self.refresh(task, platform, lane)
            elif result.status == "failed":
                lane["error"] = "登录失败；请手动刷新重试"
        except Exception as error:
            lane["status"] = "error"
            lane["error"] = error.detail if isinstance(error, HTTPException) and isinstance(error.detail, str) else "登录服务暂不可用，请检查服务或手动刷新"
            # Never hammer a missing worker or invalid browser session.
            lane["next_refresh_at"] = max(lane["next_refresh_at"], time.time() + 600)

    async def refresh(self, task, platform, lane):
        now = time.time()
        lane["refreshes"] = [t for t in lane["refreshes"] if t > now - 86400]
        if now < lane["next_refresh_at"]:
            raise HTTPException(429, "登录页正在冷却，请等待后重试")
        if len(lane["refreshes"]) >= 12:
            lane["status"] = "cooldown"
            lane["next_refresh_at"] = lane["refreshes"][0] + 86400
            return
        lane["refreshes"].append(now)
        lane["next_refresh_at"] = now + min(600 * 2 ** (len(lane["refreshes"]) - 1), 7200)
        # Persist the budget before network activity, including failed attempts.
        self.save(task)
        alias = lane.get("account_alias") or f"dispatch_{uuid.uuid4().hex}"
        lane["account_alias"] = alias
        sid = lane.get("session_id")
        if lane.get("status") in ("failed", "error"):
            await self.cancel_lane(lane)
            sid = None
        try:
            response = await self.begin_login(platform, alias, sid)
        except HTTPException as error:
            if sid and error.status_code in (404, 409, 410):
                await self.cancel_lane(lane)
            raise
        lane.update(session_id=response.qr_id, qr_image=response.qr_image, status="waiting", error="",
                    qr_expires_at=now + (response.expires_in or 300))
        self.save(task)

    def make_package(self, task, platform, account_id):
        config = task["config"]
        index = task["lanes"][platform]["completed"]
        materials = task["materials"][index:index + 1] if config["allocation"] == "one_per_account" else task["materials"]
        items = [{"file_id": m["file_id"], **m["configurations"][platform], "scheduled_time": None,
                  "status": "ready", "result": None} for m in materials]
        return {"id": uuid.uuid4().hex, "platform": platform, "account_id": account_id, "items": items,
                "automatic_pending": config["auto_publish"],
                "created_at": time.time(), "schedule": {"schedule_type": config["schedule_type"],
                    "scheduled_time": config["scheduled_time"], "interval_seconds": config["interval_seconds"],
                    "item_count": len(items)}}

    async def publish_item(self, package, item):
        from fastapi_app.api.v1.publish.services import get_publish_service
        from fastapi_app.db.session import main_db_pool
        with main_db_pool.get_connection() as db:
            return await get_publish_service().publish_batch(db=db, file_ids=[item["file_id"]],
                accounts=[package["account_id"]], platform=PLATFORMS[package["platform"]], title=item["title"],
                description=item["description"], topics=item["topics"], cover_path=item["cover"],
                scheduled_time=item["scheduled_time"], items=[{"file_id": item["file_id"], "title": item["title"],
                    "description": item["description"], "topics": item["topics"], "cover_path": item["cover"]}])

    async def automatic_package(self, task, package):
        count = sum(item["status"] == "ready" for item in package["items"])
        try:
            if count:
                await self.submit_package(task, package, {"item_count": count})
        except HTTPException as error:
            package["error"] = str(error.detail)
        package["automatic_pending"] = False
        self.save(task)

    def configure_package(self, package, options=None):
        schedule = {**package["schedule"], **(options or {})}
        ready = [item for item in package["items"] if item["status"] == "ready"]
        if not ready:
            raise HTTPException(409, "该任务包没有待执行条目")
        count = schedule.get("item_count") or len(ready)
        if not 1 <= count <= len(ready):
            raise HTTPException(422, "本次发布数量超出待执行素材数量")
        interval = schedule["interval_seconds"]
        if not 60 <= interval <= 86400:
            raise HTTPException(422, "发布间隔应在60秒至24小时之间")
        if schedule["schedule_type"] == "scheduled":
            if not schedule.get("scheduled_time"):
                raise HTTPException(422, "请选择定时发布时间")
            base = datetime.fromisoformat(schedule["scheduled_time"])
            base = base.replace(tzinfo=SHANGHAI) if base.tzinfo is None else base
            if base <= datetime.now(SHANGHAI):
                raise HTTPException(422, "定时发布时间已过，请重新设置")
        else:
            base = datetime.now(SHANGHAI)
        package["schedule"] = schedule
        package.pop("error", None)
        selected = ready[:count]
        for offset, item in enumerate(selected):
            item["scheduled_time"] = (base + timedelta(seconds=offset * interval)).isoformat() if offset or schedule["schedule_type"] == "scheduled" else None
        return selected

    async def submit_package(self, task, package, options=None):
        selected = self.configure_package(package, options)
        self.save(task)
        for item in selected:
            item["status"] = "submitting"
            self.save(task)
            try:
                result = await self.publish_item(package, item)
                item.update(status="queued" if result.get("success_count", 0) else "failed", result=result)
            except Exception:
                # An exception might happen after the broker accepted the message.
                item.update(status="needs_review", error="提交结果待核对，请到任务管理检查，避免重复发布")
            self.save(task)
        remaining = sum(item["status"] == "ready" for item in package["items"])
        package["schedule"]["item_count"] = remaining

    async def cancel_lane(self, lane):
        if lane.get("session_id"):
            from automation_worker.client import get_worker_client
            from fastapi_app.api.v1.auth.router import login_sessions
            sid = lane["session_id"]
            await get_worker_client().cancel_session(sid)
            login_sessions.pop(sid, None)
        lane.update(session_id=None, qr_image=None)

    async def cancel_sessions(self, task):
        for lane in task["lanes"].values():
            with contextlib.suppress(Exception):
                await self.cancel_lane(lane)

    async def action(self, task_id, action, platform=None, package_id=None, schedule=None):
        self.get(task_id)
        if not self.acquire(task_id):
            raise HTTPException(409, "任务正由其他服务进程处理，请稍后重试")
        async with self.locks.setdefault(task_id, asyncio.Lock()):
            task = self.get(task_id)
            if action == "stop":
                task["status"] = "stopped"
                await self.cancel_sessions(task)
            elif action == "refresh":
                if task["status"] != "active" or time.time() >= task["expires_at"]:
                    raise HTTPException(409, "分发任务已结束")
                if platform not in task["lanes"] or task["lanes"][platform]["completed"] >= task["config"]["accounts_per_platform"]:
                    raise HTTPException(400, "该平台没有待登录任务")
                await self.refresh(task, platform, task["lanes"][platform])
            elif action in ("configure", "publish"):
                package = next((p for p in task["packages"] if p["id"] == package_id), None)
                if not package:
                    raise HTTPException(404, "账号任务包不存在")
                if action == "configure":
                    self.configure_package(package, schedule)
                else:
                    await self.submit_package(task, package, schedule)
            self.save(task)
            return task


_service = None


def get_qr_distribution_service():
    global _service
    if _service is None:
        _service = QRDistributionService()
    return _service
