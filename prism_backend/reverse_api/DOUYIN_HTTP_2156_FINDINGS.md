# 抖音 HTTP 登录 2156 风控逆向记录（2026-09-02 实测）

## 结论

`DouyinHttpAdapter`（纯 HTTP QR 登录）扫码确认交接阶段被 passport 拒绝
（`error_code=2156, description="系统繁忙，请重启应用或刷新页面后重试"`）的
根因已定位：

**HTTP 会话缺少 verifycenter 会话信任** —— 浏览器版登录在 `get_qrcode` 前会
调用 `/passport/web/challenge/`（verifycenter / rmc-nocaptcha），该接口要求
会话持有 verifycenter JS 采集行为指纹后种下的 cookie（`s_v_web_id`、`ttwid`、
`__security_mc_1_s_sdk_crypt_sdk`、`bd_ticket_guard_*` 等）。HTTP 客户端无法
执行这些 JS，因此 challenge 返回 `error_code=4 参数错误`，passport 无验证
状态，扫码确认交接被拒。

## 实测证据链

1. 关梯子（直连国内 IP）后，QR 扫码可被识别（`status=scanned`）；此前海外 IP
   连扫码识别都失败（IP 级风控）→ **代理/梯子会触发抖音 IP 风控**。
2. 扫码后所有 `check_qrconnect` 轮询返回 2156；浏览器版同一时刻轮询全部
   `HTTP200 status=new/scanned`（每 ~1s 一次）。
3. 抓包浏览器版登录流程（patchright + 本机 Chrome）：
   ```
   POST /passport/ticket_guard/get_client_cert/   → server_cert（X.509）
   POST /passport/web/challenge/?skip_c=1...      → passportiv + JS template
   GET  /passport/web/get_qrcode/                 → qrcode（is_frontier=false）
   POST /passport/web/check_qrconnect/            → 循环轮询（无 2156）
   POST /passport/user_info/get_sec_ts/
   GET  /passport/token/beat/web/
   ```
4. challenge 完整参数（浏览器版，SDK 3.4.6-beta.2）与 HTTP 版差异：
   - SDK 版本：`passport_jssdk_version=3.4.6-beta.2`、`p_ui=2.4.6-beta.2`、
     `p_js_v=3.4.6-beta.2`、`p_ver=1.1.4-beta.5`、`p_ca_real=1.0.0.892`
     （HTTP 版停留在 3.4.2 / 2.4.2 / 1.1.3 / 1.0.0.874）
   - `p_zt=3.3.23`（HTTP 版为 `unknown`）
   - 参数集含 `p_no`（SHA256 字段子集）、`sign`/`qs`（passport 签名）、
     `biz_trace_id`、`msToken`、`a_bogus`（官方 JS 运行时）
5. 二分实验：
   - HTTP 复刻 challenge（完整参数 + 签名）→ `error_code=4 参数错误`
   - **浏览器原始 challenge URL 重放到全新 HTTP 会话 → 同样 `参数错误`**
   - 结论：challenge 依赖会话级 cookie/前置状态（verifycenter JS 产物），
     与 sign/a_bogus 值生成无关。

## 结论

纯 HTTP 无法完成抖音创作者扫码登录的确认交接：verifycenter（rmc-nocaptcha）
行为指纹采集只能由真实浏览器 JS 执行。**浏览器登录（`DouyinAdapter`，本机
Chrome）是唯一可靠路径**，`DouyinHttpAdapter` 保持 experimental（QR 生成、
签名、扫码识别已验证可用）。

## 参考

- 抓包产物：`reverse_api/captures/`（sanitized）
- 归档：`reverse_api/artifacts/douyin_{abogus,http,dtrait}_20260817/`
- 相关代码：`app_new/platforms/douyin_http.py`、`reverse_api/signing/`
