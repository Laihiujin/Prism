"""Douyin creator QR-login protocol metadata.

The creator page was observed to call the paths below on 2026-08-17. The
request includes short-lived values produced by Douyin's own page runtime.
This module intentionally does not copy, persist, or attempt to synthesize
those anti-abuse parameters. A browser-backed adapter should observe the
official page result and normalize it to the models in this package.
"""

from .registry import LOGIN_PROTOCOLS

PROTOCOL = LOGIN_PROTOCOLS["douyin"]

CREATE_OPERATION = {
    "method": "GET",
    "host": "creator.douyin.com",
    "path": "/passport/web/get_qrcode/",
    "verified": True,
}

POLL_OPERATION = {
    "method": "GET",
    "host": "creator.douyin.com",
    "path": "/passport/web/check_qrconnect/",
    "verified": True,
}

# A root URL alone is not proof of authentication: the SPA may briefly render
# the login component at `/`. Require both an authenticated route and creator
# workspace UI before exporting the runtime session.
SUCCESS_EVIDENCE = {
    "route_prefixes": ("/creator-micro/home",),
    "required_ui_any": ("作品发布", "内容管理", "数据中心"),
    "forbidden_ui_any": ("扫码登录", "请输入手机号"),
    "verified": True,
}

POST_LOGIN_OPERATIONS = (
    {"method": "GET", "host": "creator.douyin.com", "path": "/passport/user_info/get_sec_ts/"},
    {"method": "GET", "host": "creator.douyin.com", "path": "/web/api/v1/im/token/"},
    {"method": "GET", "host": "creator.douyin.com", "path": "/aweme/v1/creator/im/user_token/"},
)
