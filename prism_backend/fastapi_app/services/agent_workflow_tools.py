"""Explicit workflow tools shared by MCP, CLI and the tool-catalog API."""
from urllib.parse import quote
from typing import Any
import httpx

S = {"type": "string", "minLength": 1}
ID = {"type": "integer", "minimum": 1}
B = {"type": "boolean"}
PLATFORM = {"type": "string", "enum": ["douyin", "kuaishou", "xiaohongshu", "bilibili", "tencent", "tiktok", "youtube"]}


def build_workflow_tool_specs():
    from .tool_catalog import ToolSpec
    from .qr_distribution import DistributionRequest

    schema = DistributionRequest.model_json_schema()
    definitions_by_name = schema.pop("$defs", {})
    def expand(value):
        if isinstance(value, dict):
            if "$ref" in value:
                return expand(definitions_by_name[value["$ref"].rsplit("/", 1)[-1]])
            return {key: expand(item) for key, item in value.items()}
        if isinstance(value, list):
            return [expand(item) for item in value]
        return value
    configuration_schema = expand(schema)

    definitions = [
        ("list_qr_distributions", "列出扫码分发、平台登录状态和账号任务包。", "GET", "/tasks/distribution", {}, [], "json"),
        ("create_qr_distribution", "固定素材与平台预设并创建扫码分发；默认不自动执行。", "POST", "/tasks/distribution", {"configuration": configuration_schema}, ["configuration"], "configuration"),
        ("get_qr_distribution", "读取扫码分发详情、二维码和任务包。", "GET", "/tasks/distribution/{task_id}", {"task_id": S}, ["task_id"], "json"),
        ("qr_distribution_action", "刷新登录、停止分发、保存安排或执行任务包。schedule可设置数量、间隔及定时。", "POST", "/tasks/distribution/{task_id}/action", {"task_id": S, "action": {"type": "string", "enum": ["refresh", "stop", "configure", "publish"]}, "platform": PLATFORM, "package_id": S, "schedule": {"type": "object", "properties": {"schedule_type": {"type": "string", "enum": ["immediate", "scheduled"]}, "scheduled_time": S, "interval_seconds": {"type": "integer", "minimum": 60, "maximum": 86400}, "item_count": {"type": "integer", "minimum": 1, "maximum": 100}}, "required": ["schedule_type", "interval_seconds", "item_count"]}}, ["task_id", "action"], "json"),
        ("generate_cover", "生成AI封面，返回job_id；使用get_cover_job查询进度。会使用配置的图像生成服务。", "POST", "/files/{file_id}/ai-cover-job", {"file_id": ID, "platform_name": S, "aspect_ratio": {"type": "string", "enum": ["3:4", "4:3"]}, "prompt": S, "style_hint": S, "use_first_frame": B}, ["file_id"], "form"),
        ("get_cover_job", "查询封面生成状态、错误及封面路径。", "GET", "/files/ai-cover-jobs/{job_id}", {"job_id": S}, ["job_id"], "json"),
        ("list_material_covers", "查看素材的封面库与已选封面。", "GET", "/files/{file_id}/covers", {"file_id": ID}, ["file_id"], "json"),
        ("select_material_cover", "为素材选用已存在的封面。", "POST", "/files/{file_id}/covers/select", {"file_id": ID, "cover_id": S}, ["file_id", "cover_id"], "json"),
        ("adapt_material_cover", "将封面库中的图片裁切为横竖封面。path为素材库相对路径。", "POST", "/files/{file_id}/covers/adapt", {"file_id": ID, "path": S, "platform": S}, ["file_id", "path"], "json"),
        ("list_publish_verifications", "列出待人工验证的发布任务；含账号、任务与重发状态。关闭UI不影响查询。", "GET", "/verification/otp-events", {}, [], "json"),
        ("submit_publish_verification", "回传用户提供的发布验证码；account_id使用待验证事件中的标识，不要猜测验证码。", "POST", "/verification/submit-code", {"account_id": S, "code": {"type": "string", "pattern": "^[0-9]{4,8}$"}}, ["account_id", "code"], "json"),
        ("resend_publish_verification", "通知该发布任务重新获取验证码；受平台及服务冷却限制。", "POST", "/verification/resend-code", {"account_id": S}, ["account_id"], "json"),
        ("start_login_qrcode", "开始扫码登录；传session_id时在原浏览器刷新二维码。由用户扫码确认。", "POST", "/auth/qrcode/generate", {"platform": PLATFORM, "account_id": S, "session_id": S}, ["platform", "account_id"], "query"),
        ("get_login_status", "查询扫码/待确认/人工验证/成功状态，并完成账号同步。", "GET", "/auth/qrcode/poll", {"session_id": S}, ["session_id"], "json"),
        ("start_login_sms", "使用用户提供的手机号开始短信登录。", "POST", "/auth/sms/start", {"platform": {"type": "string", "enum": ["douyin", "kuaishou", "xiaohongshu", "bilibili"]}, "account_id": S, "phone": {"type": "string", "pattern": "^1[0-9]{10}$"}, "login_role": {"type": "string", "enum": ["creator", "mcn"]}}, ["platform", "account_id", "phone"], "json"),
        ("login_verification_action", "登录验证码获取/重发/回传、账号选择、身份验证二维码。验证码必须由用户提供。", "POST", "/auth/qrcode/sms", {"session_id": S, "action": {"type": "string", "enum": ["request", "resend", "submit", "select_account", "identity_qr"]}, "code": {"type": "string", "pattern": "^[0-9]{4,8}$"}, "account_choice": {"type": "string", "pattern": "^[0-9]{1,30}$"}}, ["session_id", "action"], "json"),
        ("get_login_browser_frame", "获取指定登录或创作者中心会话的实时截图。创作者中心打开接口返回session_id。", "GET", "/auth/qrcode/view/{session_id}", {"session_id": S}, ["session_id"], "json"),
        ("login_browser_pointer", "操作登录浏览器：点击拖动、wheel滚动、text文字、key按键；坐标0到1。人工验证码交给用户处理。", "POST", "/auth/qrcode/pointer/{session_id}", {"session_id": S, "action": {"type": "string", "enum": ["down", "move", "up", "cancel", "wheel", "text", "key"]}, "x": {"type": "number", "minimum": 0, "maximum": 1}, "y": {"type": "number", "minimum": 0, "maximum": 1}, "delta_x": {"type": "number", "minimum": -2000, "maximum": 2000}, "delta_y": {"type": "number", "minimum": -2000, "maximum": 2000}, "text": S, "key": S}, ["session_id", "action"], "json"),
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
                request = {"params": body} if method == "GET" or encoding == "query" else {"data" if encoding == "form" else "json": body.get("preferences") if encoding == "unwrap" else body.get("configuration") if encoding == "configuration" else body}
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
