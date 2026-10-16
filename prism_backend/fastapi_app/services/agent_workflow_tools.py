"""Explicit workflow tools shared by MCP, CLI and the tool-catalog API."""
from urllib.parse import quote
from typing import Any
import httpx

S = {"type": "string", "minLength": 1}
ID = {"type": "integer", "minimum": 1}
B = {"type": "boolean"}
PLATFORM = {"type": "string", "enum": ["douyin", "kuaishou", "xiaohongshu", "bilibili", "tencent", "youtube"]}


def build_workflow_tool_specs():
    from .tool_catalog import ToolSpec

    definitions = [
        ("generate_cover", "生成AI封面，返回job_id；使用get_cover_job查询进度。会使用配置的图像生成服务。", "POST", "/files/{file_id}/ai-cover-job", {"file_id": ID, "platform_name": S, "aspect_ratio": {"type": "string", "enum": ["3:4", "4:3"]}, "prompt": S, "style_hint": S, "use_first_frame": B}, ["file_id"], "form"),
        ("get_cover_job", "查询封面生成状态、错误及封面路径。", "GET", "/files/ai-cover-jobs/{job_id}", {"job_id": S}, ["job_id"], "json"),
        ("list_material_covers", "查看素材的封面库与已选封面。", "GET", "/files/{file_id}/covers", {"file_id": ID}, ["file_id"], "json"),
        ("select_material_cover", "为素材选用已存在的封面。", "POST", "/files/{file_id}/covers/select", {"file_id": ID, "cover_id": S}, ["file_id", "cover_id"], "json"),
        ("adapt_material_cover", "将封面库中的图片裁切为横竖封面。path为素材库相对路径。", "POST", "/files/{file_id}/covers/adapt", {"file_id": ID, "path": S, "platform": S}, ["file_id", "path"], "json"),
        ("list_publish_verifications", "列出待人工验证的发布任务；含账号、任务与重发状态。关闭UI不影响查询。", "GET", "/verification/otp-events", {}, [], "json"),
        ("submit_publish_verification", "回传用户提供的发布验证码；account_id使用待验证事件中的标识，不要猜测验证码。", "POST", "/verification/submit-code", {"account_id": S, "code": {"type": "string", "pattern": "^[0-9]{4,8}$"}}, ["account_id", "code"], "json"),
        ("resend_publish_verification", "通知该发布任务重新获取验证码；受平台及服务冷却限制。", "POST", "/verification/resend-code", {"account_id": S}, ["account_id"], "json"),
        ("start_login_qrcode", "开始浏览器扫码登录；返回session_id和二维码。由用户扫码确认。", "POST", "/auth/qrcode/generate", {"platform": PLATFORM, "account_id": S}, ["platform", "account_id"], "json"),
        ("get_login_status", "查询扫码/待确认/人工验证/成功状态，并完成账号同步。", "GET", "/auth/qrcode/poll", {"session_id": S}, ["session_id"], "json"),
        ("start_login_sms", "使用用户提供的手机号开始短信登录。", "POST", "/auth/sms/start", {"platform": {"type": "string", "enum": ["douyin", "kuaishou", "xiaohongshu", "bilibili"]}, "account_id": S, "phone": {"type": "string", "pattern": "^1[0-9]{10}$"}, "login_role": {"type": "string", "enum": ["creator", "mcn"]}}, ["platform", "account_id", "phone"], "json"),
        ("login_verification_action", "登录验证码获取/重发/回传、账号选择、身份验证二维码。验证码必须由用户提供。", "POST", "/auth/qrcode/sms", {"session_id": S, "action": {"type": "string", "enum": ["request", "resend", "submit", "select_account", "identity_qr"]}, "code": {"type": "string", "pattern": "^[0-9]{4,8}$"}, "account_choice": {"type": "string", "pattern": "^[0-9]{1,30}$"}}, ["session_id", "action"], "json"),
        ("get_login_browser_frame", "获取指定登录或创作者中心会话的实时截图。创作者中心打开接口返回session_id。", "GET", "/auth/qrcode/view/{session_id}", {"session_id": S}, ["session_id"], "json"),
        ("login_browser_pointer", "操作登录浏览器：down/move/up/cancel，坐标0到1。人工验证码交给用户处理。", "POST", "/auth/qrcode/pointer/{session_id}", {"session_id": S, "action": {"type": "string", "enum": ["down", "move", "up", "cancel"]}, "x": {"type": "number", "minimum": 0, "maximum": 1}, "y": {"type": "number", "minimum": 0, "maximum": 1}}, ["session_id", "action", "x", "y"], "json"),
        ("get_browser_runtime", "查询已安装浏览器及当前Provider。", "GET", "/system/browser-runtime/status", {}, [], "json"),
        ("get_platform_browser_preferences", "读取各平台浏览器选择。", "GET", "/system/browser-runtime/platform-preferences", {}, [], "json"),
        ("set_platform_browser_preferences", "设置各平台auto/chromium/firefox偏好。", "PUT", "/system/browser-runtime/platform-preferences", {"preferences": {"type": "object", "additionalProperties": {"type": "string", "enum": ["auto", "chromium", "firefox"]}}}, ["preferences"], "unwrap"),
        ("get_browser_headless", "读取浏览器窗口显示设置。", "GET", "/system/browser-headless", {}, [], "json"),
        ("set_browser_headless", "设置浏览器是否隐藏窗口，下次创建浏览器生效。", "PUT", "/system/browser-headless", {"headless": B}, ["headless"], "json"),
    ]
    specs = []
    for name, description, method, route, properties, required, encoding in definitions:
        schema = {"type": "object", "properties": properties, "required": required, "additionalProperties": False}

        def make_handler(method, route, schema, encoding):
            async def handler(**arguments: Any):
                from fastapi_app.core.runtime import get_backend_url
                import re
                if set(arguments) - set(schema["properties"]):
                    raise ValueError("Unknown tool arguments")
                for key in schema["required"]:
                    if key not in arguments:
                        raise ValueError(f"Missing required argument: {key}")
                for key, value in arguments.items():
                    rule = schema["properties"][key]
                    types = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "object": dict}
                    if not isinstance(value, types[rule["type"]]) or (rule["type"] in ("integer", "number") and isinstance(value, bool)):
                        raise ValueError(f"Invalid type for {key}")
                    if "enum" in rule and value not in rule["enum"]:
                        raise ValueError(f"Invalid value for {key}")
                    if "pattern" in rule and not re.fullmatch(rule["pattern"], value):
                        raise ValueError(f"Invalid format for {key}")
                    if "minimum" in rule and value < rule["minimum"] or "maximum" in rule and value > rule["maximum"] or "minLength" in rule and len(value) < rule["minLength"]:
                        raise ValueError(f"Out of range: {key}")
                if route.endswith("/qrcode/sms"):
                    if arguments["action"] == "submit" and "code" not in arguments or arguments["action"] == "select_account" and "account_choice" not in arguments:
                        raise ValueError("This verification action requires code or account_choice")
                body = dict(arguments)
                path = route
                for key in re.findall(r"\{(\w+)\}", route):
                    path = path.replace("{" + key + "}", quote(str(body.pop(key)), safe=""))
                request = {"params": body} if method == "GET" else {"data" if encoding == "form" else "json": body.get("preferences") if encoding == "unwrap" else body}
                async with httpx.AsyncClient(base_url=get_backend_url(), timeout=60) as client:
                    response = await client.request(method, "/api/v1" + path, **request)
                payload = response.json()
                if not response.is_success or payload.get("success") is False:
                    # Do not echo credentials in exceptions or logs.
                    detail = payload.get("detail") or payload.get("message")
                    return {"ok": False, "message": detail if isinstance(detail, str) else f"HTTP {response.status_code}", "data": None}
                return {"ok": True, "message": payload.get("message", ""), "data": payload.get("data", payload)}
            return handler

        specs.append(ToolSpec(name=name, description=description, parameters=schema, handler=make_handler(method, route, schema, encoding), category="workflow"))
    return specs
