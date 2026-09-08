"""
B站（bilibili）多方式登录 / 校验 / Cookie 工具。

短信链路为 requests 直连实现，契约对齐 biliup 系（biliup-app / HsuJv biliup rust 客户端）：
  POST /x/passport-login/sms/send  发码
      - 成功：data.captcha_key（验证码已发出，payload 需原样带回登录接口）
      - 风控：data.recaptcha_url（需先过极验，再带 gee_challenge/gee_validate/
        gee_seccode/recaptcha_token 重新调用发码接口）
  POST /x/passport-login/login/sms  登录
      - 携带 send 阶段的完整 payload（含 captcha_key）+ code，Android appkey 签名
因此 send→(极验)→confirm 之间必须回传“发送会话”状态 —— 由 sms_token 指向服务端
内存中的发送上下文（同一条 requests.Session 保证 buvid/cookie 延续）。

其余能力：
- 账密登录：login_by_password（RSA 加密）
- Cookie 导入：raw "name=value; ..." / cookie json → 校验 → Prism cookie json
- 登录态校验：nav

产出统一为 Prism 落盘格式：
  {cookie_info: {cookies: [{name,value,domain,path}...]},
   token_info: {access_token, refresh_token?, user_id},
   user_info: {user_id, username, name, avatar}}

说明：短信/账密为风控敏感路径；是否放行由后端开关 ALLOW_BILIBILI_ALT_LOGIN 控制
（默认开启，可在 .env 设 false 关闭）。
"""

from __future__ import annotations

import base64
import hashlib
import json
import random
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests
from loguru import logger


# ---------------------------------------------------------------------------
# 短信链路常量（Android appkey / appsec，来自 biliup rust 客户端 AppKeyStore）
# ---------------------------------------------------------------------------

_APPKEY = "783bbb7264451d82"
_APPSEC = "2653583c8873dea268ab9386918b1d65"
_SMS_APPKEY = _APPKEY
_SMS_APPSEC = _APPSEC
_SMS_SEND_URL = "https://passport.bilibili.com/x/passport-login/sms/send"
_SMS_LOGIN_URL = "https://passport.bilibili.com/x/passport-login/login/sms"
_SMS_TTL = 600  # 发送上下文有效期（秒）

# 账密登录（oauth2）
_PWD_KEY_URL = "https://passport.bilibili.com/x/passport-login/web/key"
_PWD_LOGIN_URL = "https://passport.bilibili.com/x/passport-login/oauth2/login"
# B站 geetest gt 常量（短信 recaptcha_url 中 gee_gt 一致，账密登录极验亦用此值）
_GEETEST_GT = "1c0ea7c7d47d8126dda19ee3431a5f38"
_PWD_TTL = 600  # 账密登录上下文有效期（秒）
# oauth2/login 返回 code 表示”需要极验“（风控）
_PWD_RISK_CODES = {-450, -412, -105, -102, 400}  # -450/-412/-105 常见风控码；400 兜底
# oauth2/login 返回 code 表示”需要短信二次验证“
_PWD_NEED_SMS_CODES = {-355, -354, -353}


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class SmsSendResult:
    state: str  # "sent" | "need_recaptcha" | "error"
    message: str = ""
    sms_token: str = ""  # 发送上下文 token（send/recaptcha/confirm 各阶段回传）
    recaptcha_url: str = ""
    geetest_gt: str = ""
    geetest_challenge: str = ""


@dataclass
class LoginOutcome:
    success: bool
    message: str = ""
    cookie_data: Optional[Dict[str, Any]] = None  # Prism 落盘格式
    user_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PasswordLoginResult:
    """账密登录分阶段结果。

    state: "success" | "need_captcha" | "need_sms" | "error"
      - success      ：登录完成，cookie_data 可落盘
      - need_captcha ：风控需极验，返回 geetest_gt / geetest_challenge，
                       前端内嵌 geetest，用户点过回传 challenge/validate/seccode 后重试
      - need_sms     ：密码通过但需短信二次验证，前端调 send → confirm 完成
    """
    state: str = "error"
    message: str = ""
    pwd_token: str = ""  # 账密登录上下文 token（跨阶段回传）
    cookie_data: Optional[Dict[str, Any]] = None
    user_info: Dict[str, Any] = field(default_factory=dict)
    geetest_gt: str = ""
    geetest_challenge: str = ""
    recaptcha_url: str = ""
    captcha_key: str = ""  # 供短信二次验证复用


class _SmsSession:
    """一次短信发送的完整上下文（同一 requests.Session，延续 buvid/cookie）。"""

    __slots__ = (
        "sms_token", "phone", "country_code", "client",
        "params", "recaptcha_url", "recaptcha_token", "expires_at", "lock",
    )

    def __init__(self, sms_token: str, phone: int, country_code: int, client: requests.Session,
                 params: Dict[str, Any], recaptcha_url: str = "", recaptcha_token: str = ""):
        self.sms_token = sms_token
        self.phone = phone
        self.country_code = country_code
        self.client = client
        self.params = params
        self.recaptcha_url = recaptcha_url
        self.recaptcha_token = recaptcha_token
        self.expires_at = time.time() + _SMS_TTL
        self.lock = threading.Lock()


_SMS_SESSIONS: Dict[str, _SmsSession] = {}
_SMS_REGISTRY_LOCK = threading.Lock()


class _PwdSession:
    """一次账密登录的完整上下文（同一 requests.Session + RSA 加密上下文）。

    跨阶段延续：password → (geetest 极验) → (短信二次验证)。
    """
    __slots__ = (
        "pwd_token", "username", "password", "client", "key_hash", "public_key",
        "challenge", "validate", "seccode", "expires_at", "lock",
    )

    def __init__(self, pwd_token: str, username: str, client: requests.Session,
                 key_hash: str, public_key):
        self.pwd_token = pwd_token
        self.username = username
        self.password = ""
        self.client = client
        self.key_hash = key_hash
        self.public_key = public_key
        self.challenge = ""
        self.validate = ""
        self.seccode = ""
        self.expires_at = time.time() + _PWD_TTL
        self.lock = threading.Lock()


_PWD_SESSIONS: Dict[str, _PwdSession] = {}
_PWD_REGISTRY_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# 短信链路底层（requests 直连，签名/参数对齐 biliup rust 客户端）
# ---------------------------------------------------------------------------

def _android_sign(body: str) -> str:
    return hashlib.md5(f"{body}{_SMS_APPSEC}".encode()).hexdigest()


def _new_http_client() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/63.0.3239.108",
        "Referer": "https://www.bilibili.com/",
        "Connection": "keep-alive",
    })
    return s


def _new_buvid() -> str:
    """生成形如 Yxxxxxxxx... 的随机 buvid（rust 客户端 generate_buvid 同款：Y+35 位大写 hex）。"""
    return "Y" + "".join(random.choices("0123456789ABCDEF", k=35))


def _sms_base_params(phone: int, country_code: int, buvid: str, ts: Optional[int] = None) -> Dict[str, str]:
    return {
        "actionKey": "appkey",
        "appkey": _SMS_APPKEY,
        "build": "6510400",
        "buvid": buvid,
        "channel": "bili",
        "cid": str(country_code),
        "device": "phone",
        "mobi_app": "android",
        "platform": "android",
        "tel": str(phone),
        "ts": str(ts if ts is not None else int(time.time())),
    }


def _post_signed(client: requests.Session, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """urlencode 后追加 Android sign 再 POST（顺序 = 签名顺序 = 发送顺序）。"""
    body = urllib.parse.urlencode(params)
    payload = f"{body}&sign={_android_sign(body)}"
    try:
        resp = client.post(
            url, data=payload, timeout=12,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    except requests.RequestException as e:
        logger.error(f"[BilibiliSMS] request failed: {e}")
        return {"code": -1, "message": f"网络请求失败: {e}"}
    try:
        return resp.json()
    except Exception:
        return {"code": -1, "message": f"响应解析失败(HTTP {resp.status_code})"}


def _extract_recaptcha_token(url: str) -> str:
    try:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        return (q.get("recaptcha_token") or [""])[0]
    except Exception:
        return ""


def _new_sms_token() -> str:
    return hashlib.md5(f"{time.time()}{random.random()}".encode()).hexdigest()


def _prune_sms_sessions() -> None:
    now = time.time()
    expired = [t for t, s in _SMS_SESSIONS.items() if s.expires_at < now]
    for token in expired:
        _SMS_SESSIONS.pop(token, None)


def _register_sms_session(phone: int, country_code: int, client: requests.Session,
                          params: Dict[str, Any], recaptcha_url: str, recaptcha_token: str) -> str:
    token = _new_sms_token()
    with _SMS_REGISTRY_LOCK:
        _prune_sms_sessions()
        _SMS_SESSIONS[token] = _SmsSession(
            token, phone, country_code, client, params, recaptcha_url, recaptcha_token
        )
    return token


def _get_sms_session(sms_token: str) -> Optional[_SmsSession]:
    with _SMS_REGISTRY_LOCK:
        _prune_sms_sessions()
        sess = _SMS_SESSIONS.get(sms_token)
        if sess is None or sess.expires_at < time.time():
            _SMS_SESSIONS.pop(sms_token, None)
            return None
        return sess


def _drop_sms_session(sms_token: str) -> None:
    with _SMS_REGISTRY_LOCK:
        _SMS_SESSIONS.pop(sms_token, None)


# ---------------------------------------------------------------------------
# 账密登录底层（requests 直连 + RSA + 极验/短信二次校验）
# ---------------------------------------------------------------------------

def _prune_pwd_sessions() -> None:
    now = time.time()
    expired = [t for t, s in _PWD_SESSIONS.items() if s.expires_at < now]
    for token in expired:
        _PWD_SESSIONS.pop(token, None)


def _register_pwd_session(username: str, client: requests.Session,
                          key_hash: str, public_key) -> str:
    token = _new_sms_token()
    with _PWD_REGISTRY_LOCK:
        _prune_pwd_sessions()
        _PWD_SESSIONS[token] = _PwdSession(token, username, client, key_hash, public_key)
    return token


def _get_pwd_session(pwd_token: str) -> Optional[_PwdSession]:
    with _PWD_REGISTRY_LOCK:
        _prune_pwd_sessions()
        sess = _PWD_SESSIONS.get(pwd_token)
        if sess is None or sess.expires_at < time.time():
            _PWD_SESSIONS.pop(pwd_token, None)
            return None
        return sess


def _drop_pwd_session(pwd_token: str) -> None:
    with _PWD_REGISTRY_LOCK:
        _PWD_SESSIONS.pop(pwd_token, None)


def _encrypt_password(public_key, key_hash: str, password: str) -> str:
    from Crypto.Cipher import PKCS1_v1_5
    from Crypto.PublicKey import RSA
    if isinstance(public_key, str):
        public_key = RSA.import_key(public_key)
    cipher = PKCS1_v1_5.new(public_key)
    enc = cipher.encrypt(f"{key_hash}{password}".encode())
    return base64.b64encode(enc).decode()


def _fetch_pwd_key(client: requests.Session) -> tuple[str, str]:
    """取 RSA 公钥 + hash（对齐 biliup rust get_key）。"""
    params = {"appkey": _APPKEY, "sign": _android_sign(f"appkey={_APPKEY}")}
    r = client.get(_PWD_KEY_URL, params=params, timeout=10)
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(data.get("message") or "获取登录密钥失败(code=%s)" % data.get("code"))
    d = data.get("data") or {}
    return str(d.get("hash") or ""), str(d.get("key") or "")


def _pwd_payload(sess: _PwdSession, password: str,
                 challenge: str = "", validate: str = "", seccode: str = "",
                 extra: Optional[Dict[str, Any]] = None) -> str:
    """构造 oauth2/login 表单（含极验字段 + Android 签名）。

    extra 用于承载需参与签名的附加字段（如短信二次验证的 code）。
    """
    enc_pwd = _encrypt_password(sess.public_key, sess.key_hash, password)
    params = {
        "actionKey": "appkey",
        "appkey": _APPKEY,
        "build": "6270200",
        "captcha": "",
        "challenge": challenge,
        "channel": "bili",
        "device": "phone",
        "mobi_app": "android",
        "password": enc_pwd,
        "permission": "ALL",
        "platform": "android",
        "seccode": seccode,
        "subid": 1,
        "ts": str(int(time.time())),
        "username": sess.username,
        "validate": validate,
    }
    if extra:
        params.update({k: str(v) for k, v in extra.items()})
    body = urllib.parse.urlencode(params)
    params2 = dict(params)
    params2["sign"] = _android_sign(body)
    return urllib.parse.urlencode(params2)


def _parse_geetest_from_url(url: str) -> tuple[str, str]:
    """从 recaptcha_url 解析 (gee_gt, gee_challenge)。"""
    try:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        return (q.get("gee_gt") or [""])[0], (q.get("gee_challenge") or [""])[0]
    except Exception:
        return "", ""


# ---------------------------------------------------------------------------
# 对外 API（同步；网络调用由调用方放入线程池）
# ---------------------------------------------------------------------------

def send_sms(phone: str, country_code: str = "86") -> SmsSendResult:
    """发送短信验证码（第一步）。

    返回 state：
      - "sent"           ：验证码已发出，sms_token 供 /sms/confirm 登录
      - "need_recaptcha" ：需先过极验；recaptcha_url 由用户浏览器打开完成，
                           拿到 challenge/validate 后调 send_sms_with_recaptcha
      - "error"          ：失败
    """
    try:
        tel = int(str(phone).strip())
        cid = int(str(country_code).strip())
        if tel <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return SmsSendResult(state="error", message="手机号/区号格式不正确")

    client = _new_http_client()
    params = _sms_base_params(tel, cid, _new_buvid())
    data = _post_signed(client, _SMS_SEND_URL, params)

    code = data.get("code")
    msg = data.get("message") or ""
    d = data.get("data") or {}
    if not isinstance(d, dict):
        d = {}

    if code == 0:
        captcha_key = str(d.get("captcha_key") or "")
        recaptcha_url = str(d.get("recaptcha_url") or "")
        if captcha_key:
            params["captcha_key"] = captcha_key
            token = _register_sms_session(tel, cid, client, params, "", "")
            return SmsSendResult(state="sent", message="验证码已发送", sms_token=token)
        if recaptcha_url:
            token = _register_sms_session(tel, cid, client, params, recaptcha_url,
                                          _extract_recaptcha_token(recaptcha_url))
            gt, gchallenge = _parse_geetest_from_url(recaptcha_url)
            return SmsSendResult(
                state="need_recaptcha", message=msg or "需先通过滑块验证",
                sms_token=token, recaptcha_url=recaptcha_url,
                geetest_gt=gt, geetest_challenge=gchallenge,
            )

    # 旧版/兜底风控分支：code 为 -105/21005 或消息含 captcha
    if code in (-105, 21005) or "recaptcha" in msg.lower() or "captcha" in msg.lower():
        recaptcha_url = str(d.get("recaptcha_url") or "")
        if recaptcha_url:
            token = _register_sms_session(tel, cid, client, params, recaptcha_url,
                                          _extract_recaptcha_token(recaptcha_url))
            gt, gchallenge = _parse_geetest_from_url(recaptcha_url)
            return SmsSendResult(
                state="need_recaptcha", message=msg, sms_token=token, recaptcha_url=recaptcha_url,
                geetest_gt=gt, geetest_challenge=gchallenge,
            )
        return SmsSendResult(state="need_recaptcha", message=msg or f"发送被风控拦截(code={code})")

    return SmsSendResult(state="error", message=msg or f"发送失败(code={code})")


def send_sms_with_recaptcha(sms_token: str, challenge: str, validate: str) -> SmsSendResult:
    """极验通过后补发短信（第二步）。

    challenge/validate 由用户在 recaptcha_url 页面完成滑块后，从开发者工具
    ajax.php 请求/响应中取得（与 biliup-app 交互一致）；recaptcha_token 由
    后端从 recaptcha_url 自动解析。
    """
    challenge = (challenge or "").strip()
    validate = (validate or "").strip()
    if not challenge or not validate:
        return SmsSendResult(state="error", message="请填写 challenge 与 validate")

    sess = _get_sms_session(sms_token)
    if sess is None:
        return SmsSendResult(state="error", message="短信会话不存在或已过期，请重新发送验证码")
    if not sess.recaptcha_url or not sess.recaptcha_token:
        return SmsSendResult(state="error", message="当前会话无需滑块验证，请直接输入短信验证码")

    with sess.lock:
        params = _sms_base_params(sess.phone, sess.country_code,
                                  sess.params.get("buvid") or _new_buvid(),
                                  sess.params.get("ts"))
        # B站 极验补发的签名必须包含 gee_gt（与首次 send 的 recaptcha_url 里的 gee_gt 一致）
        gt, _ = _parse_geetest_from_url(sess.recaptcha_url)
        params.update({
            "gee_gt": gt or _GEETEST_GT,
            "gee_challenge": challenge,
            "gee_seccode": f"{validate}|jordan",
            "gee_validate": validate,
            "recaptcha_token": sess.recaptcha_token,
        })
        data = _post_signed(sess.client, _SMS_SEND_URL, params)

        code = data.get("code")
        msg = data.get("message") or ""
        d = data.get("data") or {}
        captcha_key = str(d.get("captcha_key") or "") if isinstance(d, dict) else ""
        if code == 0 and captcha_key:
            params["captcha_key"] = captcha_key
            sess.params = params
            sess.recaptcha_url = ""
            sess.recaptcha_token = ""
            sess.expires_at = time.time() + _SMS_TTL
            return SmsSendResult(state="sent", message="验证码已发送", sms_token=sms_token)
        return SmsSendResult(state="error", message=msg or f"滑块验证提交失败(code={code})")


def login_by_sms(sms_token: str, code: str) -> LoginOutcome:
    """用短信验证码完成登录（最后一步，需先 send_sms 且拿到 sms_token）。"""
    code = (code or "").strip()
    if not code:
        return LoginOutcome(success=False, message="请输入短信验证码")

    sess = _get_sms_session(sms_token)
    if sess is None:
        return LoginOutcome(success=False, message="短信会话不存在或已过期，请重新发送验证码")

    with sess.lock:
        params = dict(sess.params)
        params["code"] = code
        data = _post_signed(sess.client, _SMS_LOGIN_URL, params)
        _drop_sms_session(sms_token)  # 一次性会话

        if not data or data.get("code") != 0:
            msg = (data or {}).get("message") or "短信验证码错误或已过期"
            logger.warning(f"[BilibiliSMS] login failed: {msg}")
            return LoginOutcome(success=False, message=msg)

        outcome = _build_login_outcome(data, sess.client)
        if not outcome.success or not _cookie_data_to_flat(outcome.cookie_data):
            return LoginOutcome(success=False, message="登录响应缺少 Cookie，可能需要二次验证，请改用扫码")
        return _attach_user_info(outcome)


# ---------------------------------------------------------------------------
# 数据结构/落盘共用（biliup 或直连接口响应 → Prism 格式）
# ---------------------------------------------------------------------------

def _extract_cookie_json(session) -> Dict[str, Any]:
    """把 requests.Session 的 cookie 转成 Prism 落盘格式。"""
    cookies_list = [
        {"name": c.name, "value": c.value, "domain": c.domain or ".bilibili.com", "path": c.path or "/"}
        for c in session.cookies
        if c.value
    ]
    return {
        "cookie_info": {"cookies": cookies_list},
        "token_info": {},
        "user_info": {},
    }


def _build_login_outcome(raw: Dict[str, Any], session) -> LoginOutcome:
    """把登录成功响应（code==0，含 data.cookie_info / token_info）落成 Prism 格式。"""
    data = raw.get("data") or {}
    cookie_info = data.get("cookie_info") or {}
    cookies = cookie_info.get("cookies") or []
    token_info = data.get("token_info") or {}

    cookie_data = {
        "cookie_info": {
            "cookies": [
                {
                    "name": c.get("name"),
                    "value": c.get("value"),
                    "domain": c.get("domain") or ".bilibili.com",
                    "path": c.get("path") or "/",
                    "expires": c.get("expires"),
                    "httpOnly": c.get("http_only", c.get("httpOnly")),
                }
                for c in cookies
                if c.get("name") and c.get("value") is not None
            ]
        },
        "token_info": {
            "access_token": token_info.get("access_token") or "",
            "refresh_token": token_info.get("refresh_token") or "",
            "user_id": str(cookies_user_id(cookies)),
        },
        "user_info": {},
    }
    # 尽量从 session 兜底 cookie（部分登录会 set 进 session）
    if not cookie_data["cookie_info"]["cookies"]:
        cookie_data = _extract_cookie_json(session)
    return LoginOutcome(success=True, message="登录成功", cookie_data=cookie_data)


def cookies_user_id(cookies: List[Dict[str, Any]]) -> str:
    for c in cookies or []:
        if c.get("name") in ("DedeUserID", "DedeUserID__ckMd5"):
            return str(c.get("value") or "")
    return ""


def _parse_raw_cookie(raw: str) -> Dict[str, Any]:
    """把浏览器粘贴的 "k1=v1; k2=v2; ..." 解析为 cookie json。"""
    cookies = []
    for seg in raw.split(";"):
        seg = seg.strip()
        if not seg or "=" not in seg:
            continue
        name, _, value = seg.partition("=")
        name = name.strip()
        value = value.strip().strip('"')
        if name and value:
            cookies.append({"name": name, "value": value, "domain": ".bilibili.com", "path": "/"})
    return {"cookie_info": {"cookies": cookies}, "token_info": {}, "user_info": {}}


def _cookie_data_to_flat(data: Dict[str, Any]) -> Dict[str, str]:
    """Prism cookie json → flat dict（供 biliup login_by_cookies / 校验）。"""
    result: Dict[str, str] = {}
    cookies = []
    if isinstance(data, dict):
        ci = data.get("cookie_info") or {}
        cookies = ci.get("cookies") or [] if isinstance(ci, dict) else []
    for c in cookies:
        if isinstance(c, dict) and c.get("name") and c.get("value") is not None:
            result[str(c["name"])] = str(c["value"])
    return result


def _biliup_cookie_payload(flat: Dict[str, str]) -> Dict[str, Any]:
    return {
        "cookie_info": {
            "cookies": [
                {"name": k, "value": v, "domain": ".bilibili.com", "path": "/"}
                for k, v in flat.items()
            ]
        },
        "token_info": {},
    }


# ---------------------------------------------------------------------------
# 账密登录 / Cookie 导入 / 校验（biliup 同步库）
# ---------------------------------------------------------------------------

def _new_bilibili():
    """新建 BiliBili 会话（自带 requests.Session + UA）。"""
    from biliup.plugins.bili_webup import BiliBili, Data
    return BiliBili(Data())


def prepare_password_login(username: str) -> PasswordLoginResult:
    """账密登录第 1 步：取 RSA 密钥，建立会话，返回 pwd_token。

    前端拿到 pwd_token 后：直接提交密码（可能被风控要求极验/短信）；
    或先内嵌 geetest（geetest_gt/geetest_challenge）取 validate 再提交。
    """
    username = (username or "").strip()
    if not username:
        return PasswordLoginResult(state="error", message="请输入账号")
    try:
        client = _new_http_client()
        key_hash, pub_key = _fetch_pwd_key(client)
        if not pub_key or not key_hash:
            return PasswordLoginResult(state="error", message="获取登录密钥失败")
        token = _register_pwd_session(username, client, key_hash, pub_key)
        return PasswordLoginResult(
            state="ready", message="登录会话已建立",
            pwd_token=token, geetest_gt=_GEETEST_GT,
        )
    except Exception as e:
        logger.error(f"[BilibiliPassword] prepare failed: {e}")
        return PasswordLoginResult(state="error", message=str(e) or "登录会话建立失败")


def password_login(pwd_token: str, password: str,
                   challenge: str = "", validate: str = "", seccode: str = "") -> PasswordLoginResult:
    """账密登录主体（第 2 步）。

    首次可空极验字段提交；若 B站 风控返回需极验/短信，则：
      - need_captcha ：返回 geetest_gt/challenge，前端内嵌 geetest，回传 validate/seccode 再试
      - need_sms     ：密码通过但需短信二次验证，前端走 send→confirm 完成
    """
    sess = _get_pwd_session(pwd_token)
    if sess is None:
        return PasswordLoginResult(state="error", message="登录会话不存在或已过期，请重新登录")
    if not password:
        return PasswordLoginResult(state="error", message="请输入密码")
    sess.password = password  # 供短信二次验证复用同一加密上下文
    # 记录本次回传的极验值
    if challenge:
        sess.challenge = challenge
    if validate:
        sess.validate = validate
    if seccode:
        sess.seccode = seccode

    with sess.lock:
        payload = _pwd_payload(sess, password, sess.challenge, sess.validate, sess.seccode)
        try:
            resp = sess.client.post(
                _PWD_LOGIN_URL, data=payload, timeout=12,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            raw = resp.json()
        except Exception as e:
            logger.error(f"[BilibiliPassword] login request failed: {e}")
            return PasswordLoginResult(state="error", message=f"网络请求失败: {e}")

        code = raw.get("code")
        msg = raw.get("message") or ""
        d = raw.get("data") or {}
        if not isinstance(d, dict):
            d = {}

        # 登录成功
        if code == 0 and d.get("cookie_info"):
            outcome = _build_login_outcome(raw, sess.client)
            _drop_pwd_session(pwd_token)
            if not outcome.success or not outcome.cookie_data:
                return PasswordLoginResult(state="error", message="登录响应缺少 Cookie")
            return PasswordLoginResult(
                state="success", message="账密登录成功",
                cookie_data=outcome.cookie_data, user_info=outcome.cookie_data.get("user_info") or {},
            )

        # 需要短信二次验证
        if code in _PWD_NEED_SMS_CODES or (msg and ("短信" in msg or "验证" in msg and "极验" not in msg)):
            return PasswordLoginResult(
                state="need_sms", message=msg or "密码通过，需短信验证码二次确认",
                pwd_token=pwd_token, geetest_gt=_GEETEST_GT,
            )

        # 需要极验（风控）
        if code in _PWD_RISK_CODES or (msg and ("极验" in msg or "验证码" in msg or "风控" in msg)) or \
                (msg and "captcha" in msg.lower()):
            gt, challenge = _parse_geetest_from_url(str(d.get("recaptcha_url") or ""))
            return PasswordLoginResult(
                state="need_captcha",
                message=msg or "需要滑块验证",
                pwd_token=pwd_token,
                geetest_gt=gt or _GEETEST_GT,
                geetest_challenge=challenge,
                recaptcha_url=str(d.get("recaptcha_url") or ""),
            )

        return PasswordLoginResult(state="error", message=msg or f"账密登录失败(code={code})")


def password_login_sms_confirm(pwd_token: str, sms_token: str, code: str) -> PasswordLoginResult:
    """账密登录短信二次验证确认（第 3 步）。

    密码已通过、B站 要求短信验证时，复用短信链完成登录：前端先对账号绑定手机号
    调 send_sms 拿到 sms_token，再带 code 调本函数；login_by_sms 会返回同一账号
    的 cookie（即密码账号的 cookie），供落盘。pwd_token 仅作流程上下文校验。
    """
    # 可选上下文校验（不阻断，因为短信链自带会话）
    if pwd_token:
        _get_pwd_session(pwd_token)  # 仅触发过期清理/校验
        if _get_pwd_session(pwd_token) is None:
            # 密码上下文过期，但短信链独立有效，仍允许（不提前失败）
            pass
    code = (code or "").strip()
    if not code:
        return PasswordLoginResult(state="error", message="请输入短信验证码")
    if not sms_token:
        return PasswordLoginResult(state="error", message="短信会话缺失，请先发送验证码")

    outcome = login_by_sms(sms_token, code)
    if outcome.success and outcome.cookie_data:
        _drop_pwd_session(pwd_token) if pwd_token else None
        return PasswordLoginResult(
            state="success", message="登录成功",
            cookie_data=outcome.cookie_data, user_info=outcome.cookie_data.get("user_info") or {},
        )
    return PasswordLoginResult(state="error", message=outcome.message or "短信验证码错误或已过期，请重新验证")


def import_cookie(raw_or_json: str) -> LoginOutcome:
    """Cookie 导入：接受浏览器粘贴串或 JSON，校验后落成 Prism cookie json。"""
    raw = (raw_or_json or "").strip()
    if not raw:
        return LoginOutcome(success=False, message="Cookie 为空")
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and parsed.get("cookie_info"):
            cookie_data = parsed
        else:
            raise ValueError("not prism cookie json")
    except Exception:
        cookie_data = _parse_raw_cookie(raw)

    flat = _cookie_data_to_flat(cookie_data)
    if not flat:
        return LoginOutcome(success=False, message="未解析到任何 Cookie（需 SESSDATA/bili_jct 等）")

    # 校验
    outcome = verify_cookie(cookie_data)
    if not outcome.success:
        return outcome
    return outcome


def verify_cookie(cookie_data: Dict[str, Any]) -> LoginOutcome:
    """用 nav 接口校验 cookie 有效性，并回填用户信息。"""
    flat = _cookie_data_to_flat(cookie_data)
    if not flat:
        return LoginOutcome(success=False, message="Cookie 为空")
    try:
        bili = _new_bilibili()
        bili.login_by_cookies(_biliup_cookie_payload(flat))
        nav = bili.__session.get(
            "https://api.bilibili.com/x/web-interface/nav",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"},
        ).json()
    except Exception as e:
        logger.warning(f"[BilibiliVerify] nav failed: {e}")
        return LoginOutcome(success=False, message="Cookie 无效或已过期")
    if nav.get("code") != 0:
        return LoginOutcome(success=False, message=nav.get("message") or "Cookie 无效或已过期")

    data = nav.get("data") or {}
    mid = data.get("mid")
    name = data.get("uname") or data.get("name") or ""
    face = data.get("face") or ""
    # 回填 user_id / token_info.user_id
    ci = cookie_data.get("cookie_info") or {}
    cookies = ci.get("cookies") or []
    uid = str(mid) if mid else cookies_user_id(cookies)
    cookie_data.setdefault("token_info", {})["user_id"] = uid
    cookie_data["user_info"] = {
        "user_id": uid,
        "username": name,
        "name": name,
        "avatar": face,
    }
    return LoginOutcome(success=True, message="Cookie 有效", cookie_data=cookie_data, user_info=cookie_data["user_info"])


def _attach_user_info(outcome: LoginOutcome) -> LoginOutcome:
    if not outcome.success or not outcome.cookie_data:
        return outcome
    try:
        verified = verify_cookie(outcome.cookie_data)
        if verified.success:
            return verified
    except Exception as e:
        logger.warning(f"[BilibiliLogin] user info attach failed: {e}")
    return outcome
