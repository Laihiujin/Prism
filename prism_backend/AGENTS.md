# Prism Backend Agent Rules

本文件约束在 `prism_backend/` 下工作的 AI Agent（Codex / Claude Code /
OpenClaw / Prism HermesAgent）与开发者。更具体的指令优先于本文件。

## 抖音登录：HTTP 逆向（app_new）生产禁用

`prism_backend/app_new/platforms/douyin_http.py`（`DouyinHttpAdapter`）是
**实验性逆向实现，仅允许开发者本地测试（`mode=http`）**，**严禁在生产/
正式发布链路中使用**，包括但不限于：

- ❌ 把 `PRISM_DOUYIN_LOGIN_MODE` 设为 `http` 用于正式环境
- ❌ 让 worker / API 默认走 `DouyinHttpAdapter`
- ❌ 在账号系统、发布链路、桌面端中依赖 HTTP 登录产出的 cookie
- ❌ 移除/绕过下述限制、或把 HTTP 登录伪装成正式功能

生产登录**必须走浏览器模式**：

- ✅ `DouyinAdapter`（`app_new/platforms/douyin.py`，patchright + 本机浏览器）
- ✅ `PlaywrightLoginManager`（`fastapi_app/api/v1/auth/services.py`）

### 为什么

纯 HTTP 登录无法完成扫码确认交接：passport 在确认阶段要求 verifycenter
会话信任（`/passport/web/challenge/` + rmc-nocaptcha 行为指纹采集，种
`s_v_web_id` 等 cookie），该信任只能由真实浏览器 JS 建立，HTTP 客户端
无法复刻 → 扫码确认被拒（`error_code=2156 "系统繁忙"`）。实测证据链见
`prism_backend/reverse_api/DOUYIN_HTTP_2156_FINDINGS.md`。

### 允许的开发用途

- 逆向研究：a_bogus / D-Trait / passport 签名（`reverse_api/signing/`）
- 本地测试：`/qrcode/generate?mode=http` 验证 QR 生成、扫码识别等
- 任何改动不得改变"HTTP = experimental"的定位；如需变更，先与用户确认

## 其他

- `reverse_api/` 下逆向产物的归档/验证/回滚流程（`artifacts/*/VERIFICATION.txt`
  + `ROLLBACK.sh`）应保持；新逆向改动请遵循同样的验证与回滚约定。
- 修改登录相关代码前，先读 `DOUYIN_HTTP_2156_FINDINGS.md` 与本文件。
