"""
B站多方式登录 API（短信[含极验] / 账密 / Cookie 导入）

路由前缀：/auth/bilibili/*
落盘复用 auth/router.py 的 _save_bilibili_login（cookie 结构保持一致，
账号页/发布链路无需改动即可用）。

短信链路（完整回传调度）：
  1. POST /sms/send      {phone, country_code}
     → state=sent（sms_token）/ state=need_recaptcha（sms_token + recaptcha_url）
  2. POST /sms/recaptcha {sms_token, challenge, validate}   （仅 need_recaptcha 时）
     → state=sent（同一 sms_token，验证码已补发）
  3. POST /sms/confirm   {sms_token, code, account_id}
     → 登录并落盘，返回 user_info

说明：
- 扫码仍走统一 /auth/qrcode/*（HTTP passport API），不在此重复。
- 短信/账密为风控敏感路径，默认开启（ALLOW_BILIBILI_ALT_LOGIN 默认 true），
  可在 .env 设 ALLOW_BILIBILI_ALT_LOGIN=false 关闭。
- 网络调用为同步 requests，包在 run_in_executor 中执行。
"""

from __future__ import annotations

import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from fastapi_app.core.config import settings
from fastapi_app.core.logger import logger


router = APIRouter(prefix="/bilibili", tags=["B站登录"])


def _alt_login_enabled() -> bool:
    return bool(getattr(settings, "ALLOW_BILIBILI_ALT_LOGIN", True))


def _reject_if_disabled() -> None:
    if not _alt_login_enabled():
        raise HTTPException(
            status_code=403,
            detail="B站短信/账密登录已关闭（ALLOW_BILIBILI_ALT_LOGIN=false）。如需开启请在后端 .env 设置 ALLOW_BILIBILI_ALT_LOGIN=true 后重启；也可使用扫码或 Cookie 导入。",
        )


async def _run_sync(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


async def _persist_bilibili_login(account_id: str, cookie_data: dict) -> None:
    """复用 auth/router.py 的落库逻辑（懒加载避免循环导入）。"""
    from fastapi_app.api.v1.auth.router import _save_bilibili_login

    session = {"account_id": account_id}
    login_data = {
        "cookies": (cookie_data.get("cookie_info") or {}).get("cookies") or [],
        "user_info": cookie_data.get("user_info") or {},
    }
    await _save_bilibili_login(session, login_data)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SmsSendRequest(BaseModel):
    phone: str = Field(..., description="手机号")
    country_code: str = Field(default="86", description="区号")


class SmsRecaptchaRequest(BaseModel):
    sms_token: str = Field(..., description="send 阶段返回的短信会话 token")
    challenge: str = Field(..., description="极验 challenge（开发者工具 ajax.php 请求 payload）")
    gee_validate: str = Field(
        ...,
        alias="validate",
        description="极验 validate（开发者工具 ajax.php 响应）",
    )

    model_config = {"populate_by_name": True}


class SmsConfirmRequest(BaseModel):
    sms_token: str = Field(..., description="send/recaptcha 阶段返回的短信会话 token")
    code: str = Field(..., description="短信验证码")
    account_id: str = Field(..., description="账号ID（落盘文件名 bilibili_<account_id>.json）")


class PasswordPrepareRequest(BaseModel):
    username: str = Field(..., description="B站用户名/手机号")


class PasswordLoginRequest(BaseModel):
    pwd_token: str = Field(..., description="prepare 阶段返回的账密登录会话 token")
    password: str = Field(..., description="密码")
    challenge: str = Field(default="", description="极验 challenge（内嵌 geetest 通过后回传）")
    validate: str = Field(default="", description="极验 validate（geetest_validate）")
    seccode: str = Field(default="", description="极验 seccode（geetest_seccode）")
    account_id: str = Field(..., description="账号ID（落盘文件名 bilibili_<account_id>.json）")


class PasswordSmsConfirmRequest(BaseModel):
    pwd_token: str = Field(..., description="账密登录会话 token")
    sms_token: str = Field(..., description="短信会话 token（对绑定手机号 send_sms 后返回）")
    code: str = Field(..., description="短信验证码")
    account_id: str = Field(..., description="账号ID")


class CookieImportRequest(BaseModel):
    account_id: str = Field(..., description="账号ID")
    cookie: str = Field(..., description="Cookie：浏览器粘贴串 或 cookie json 字符串")


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------

@router.post("/sms/send", summary="B站短信验证码发送")
async def bilibili_sms_send(req: SmsSendRequest):
    _reject_if_disabled()
    from platforms.bilibili import methods as bili

    result = await _run_sync(bili.send_sms, req.phone, req.country_code)
    return {
        "success": result.state != "error",
        "state": result.state,
        "message": result.message,
        "sms_token": result.sms_token or None,
        "recaptcha_url": result.recaptcha_url or None,
        "geetest_gt": result.geetest_gt or None,
        "geetest_challenge": result.geetest_challenge or None,
    }


@router.post("/sms/recaptcha", summary="B站短信极验通过后补发验证码")
async def bilibili_sms_recaptcha(req: SmsRecaptchaRequest):
    _reject_if_disabled()
    from platforms.bilibili import methods as bili

    result = await _run_sync(bili.send_sms_with_recaptcha, req.sms_token, req.challenge, req.gee_validate)
    return {
        "success": result.state != "error",
        "state": result.state,
        "message": result.message,
        "sms_token": result.sms_token or None,
        "recaptcha_url": None,
    }


@router.post("/sms/confirm", summary="B站短信验证码登录确认")
async def bilibili_sms_confirm(req: SmsConfirmRequest):
    _reject_if_disabled()
    from platforms.bilibili import methods as bili

    outcome = await _run_sync(bili.login_by_sms, req.sms_token, req.code)
    if not outcome.success or not outcome.cookie_data:
        raise HTTPException(status_code=400, detail=outcome.message or "短信登录失败")
    await _persist_bilibili_login(req.account_id, outcome.cookie_data)
    return {
        "success": True,
        "message": "B站登录成功",
        "account_id": req.account_id,
        "user_info": outcome.cookie_data.get("user_info") or {},
    }


@router.post("/password/prepare", summary="B站账密登录：建会话取 RSA 密钥")
async def bilibili_password_prepare(req: PasswordPrepareRequest):
    _reject_if_disabled()
    from platforms.bilibili import methods as bili

    result = await _run_sync(bili.prepare_password_login, req.username)
    return {
        "success": result.state != "error",
        "state": result.state,
        "message": result.message,
        "pwd_token": result.pwd_token or None,
        "geetest_gt": result.geetest_gt or None,
    }


@router.post("/password", summary="B站账密登录（可带极验/短信二次）")
async def bilibili_password_login(req: PasswordLoginRequest):
    _reject_if_disabled()
    from platforms.bilibili import methods as bili

    result = await _run_sync(
        bili.password_login,
        req.pwd_token, req.password,
        req.challenge, req.validate, req.seccode,
    )
    if result.state == "success" and result.cookie_data:
        await _persist_bilibili_login(req.account_id, result.cookie_data)
        return {
            "success": True,
            "state": "success",
            "message": "B站登录成功",
            "account_id": req.account_id,
            "user_info": result.cookie_data.get("user_info") or {},
        }
    if result.state == "need_captcha":
        return {
            "success": False,
            "state": "need_captcha",
            "message": result.message or "需要滑块验证",
            "pwd_token": result.pwd_token,
            "geetest_gt": result.geetest_gt,
            "geetest_challenge": result.geetest_challenge,
            "recaptcha_url": result.recaptcha_url,
        }
    if result.state == "need_sms":
        return {
            "success": False,
            "state": "need_sms",
            "message": result.message or "密码通过，需短信验证码二次确认",
            "pwd_token": result.pwd_token,
        }
    raise HTTPException(status_code=400, detail=result.message or "账密登录失败")


@router.post("/password/sms-confirm", summary="B站账密登录：短信二次验证确认")
async def bilibili_password_sms_confirm(req: PasswordSmsConfirmRequest):
    _reject_if_disabled()
    from platforms.bilibili import methods as bili

    result = await _run_sync(bili.password_login_sms_confirm, req.pwd_token, req.sms_token, req.code)
    if result.state == "success" and result.cookie_data:
        await _persist_bilibili_login(req.account_id, result.cookie_data)
        return {
            "success": True,
            "state": "success",
            "message": "B站登录成功",
            "account_id": req.account_id,
            "user_info": result.cookie_data.get("user_info") or {},
        }
    raise HTTPException(status_code=400, detail=result.message or "短信验证失败")


@router.post("/cookie/import", summary="B站 Cookie 导入登录")
async def bilibili_cookie_import(req: CookieImportRequest):
    from platforms.bilibili import methods as bili

    outcome = await _run_sync(bili.import_cookie, req.cookie)
    if not outcome.success or not outcome.cookie_data:
        raise HTTPException(status_code=400, detail=outcome.message or "Cookie 无效")
    await _persist_bilibili_login(req.account_id, outcome.cookie_data)
    return {
        "success": True,
        "message": "B站 Cookie 导入成功",
        "account_id": req.account_id,
        "user_info": outcome.cookie_data.get("user_info") or {},
    }


@router.get("/alt-enabled", summary="B站备选登录是否可用")
async def bilibili_alt_enabled():
    return {"success": True, "enabled": _alt_login_enabled()}
