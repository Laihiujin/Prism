from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LoginProtocol:
    platform: str
    login_url: str
    create_path: str | None = None
    poll_path: str | None = None
    transport: str = "browser_observed"
    capture_status: str = "pending"
    notes: str = ""


LOGIN_PROTOCOLS = {
    "douyin": LoginProtocol(
        platform="douyin",
        login_url="https://creator.douyin.com/creator-micro/login?enter_from=qr",
        create_path="/passport/web/get_qrcode/",
        poll_path="/passport/web/check_qrconnect/",
        transport="browser_generated_request",
        capture_status="end_to_end_verified",
        notes="Dynamic parameters come from the official page runtime; success requires authenticated route plus creator UI.",
    ),
    "kuaishou": LoginProtocol(
        platform="kuaishou",
        login_url="https://cp.kuaishou.com/profile",
        notes="Awaiting sanitized network capture.",
    ),
    "xiaohongshu": LoginProtocol(
        platform="xiaohongshu",
        login_url="https://creator.xiaohongshu.com/new/home",
        notes="Legacy XhsClient proves create/check operations exist; current creator endpoint awaits capture.",
    ),
    "channels": LoginProtocol(
        platform="channels",
        login_url="https://channels.weixin.qq.com/login.html",
        notes="QR is rendered in a login iframe; endpoint capture awaits verification.",
    ),
}
