"""抖音 HTTP 登录验证脚本（mode=http）。

用法:
    1. 另开终端启动 worker:
       AUTOMATION_WORKER_PORT=7001 PYTHONPATH=.:prism_backend .venv/bin/python prism_backend/automation_worker/worker.py
    2. 本脚本: PYTHONPATH=.:prism_backend .venv/bin/python scripts/dev/verify_douyin_http_login.py
    3. 打开 /tmp/prism_douyin_qr.png，用抖音 App 扫码并确认，然后按回车轮询。

预期结果:
    - confirmed + auth_cookies 含 sessionid/sessionid_ss/sid_guard → 修复生效
    - failed + "账号会话未激活：缺少..." → 把缺失列表发给开发补激活接口
"""

from __future__ import annotations

import base64
import sys
import time

import httpx

BASE = "http://127.0.0.1:7001"
AUTH_COOKIE_NAMES = ("sessionid", "sessionid_ss", "sid_guard", "sid_tt", "passport_auth_id", "odin_tt")


def main() -> int:
    client = httpx.Client(timeout=60)

    # 1. 生成 HTTP 模式二维码
    resp = client.post(
        f"{BASE}/qrcode/generate",
        params={"platform": "douyin", "account_id": "http-test", "mode": "http"},
    )
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        print(f"[FAIL] generate 失败: {body}")
        return 1
    data = body["data"]
    session_id = data["session_id"]
    qr_b64 = data["qr_image"].split(",", 1)[1]
    with open("/tmp/prism_douyin_qr.png", "wb") as fh:
        fh.write(base64.b64decode(qr_b64))
    print(f"[1] 二维码已保存: /tmp/prism_douyin_qr.png")
    print(f"    session_id: {session_id}  过期: {data['expires_in']}s")
    input("    请用抖音 App 扫码并确认，然后按回车开始轮询…")

    # 2. 轮询登录状态
    deadline = time.time() + int(data["expires_in"] or 300)
    while time.time() < deadline:
        resp = client.get(f"{BASE}/qrcode/status/{session_id}")
        resp.raise_for_status()
        poll = resp.json()["data"]
        status = poll["status"]
        print(f"    status={status:<10} msg={poll.get('message')}")
        if status in ("confirmed", "failed", "expired"):
            if status == "confirmed":
                cookies = poll.get("cookies") or {}
                auth = sorted(k for k in AUTH_COOKIE_NAMES if cookies.get(k))
                extra = (poll.get("user_info") or {}).get("extra") or {}
                print(f"[OK] 登录成功！cookie 总数={len(cookies)}")
                print(f"    账号 cookie: {auth}")
                if extra.get("activated_cookies"):
                    print(f"    激活确认: {extra['activated_cookies']}")
                state = poll.get("full_state") or {}
                print(f"    storage_state cookies={len(state.get('cookies') or [])}")
                if any(cookies.get(k) for k in ("sessionid", "sessionid_ss", "sid_guard")):
                    print("    ✅ 核心登录 cookie 已拿到，账号会话可用")
                    return 0
                print("    ❌ confirmed 但核心 cookie 缺失（不应发生）")
                return 2
            print(f"[END] 状态={status}: {poll.get('message')}")
            return 2 if status == "failed" else 0
        time.sleep(3)
    print("[END] 轮询超时（QR 可能已过期），重新跑一次")
    return 2


if __name__ == "__main__":
    sys.exit(main())
