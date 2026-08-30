# Persona Studio 集成指南

最终架构：**Prism + Persona Studio + Patchright + Proxy Manager**

Persona Studio（[TechQaiser/persona-studio](https://github.com/TechQaiser/persona-studio)，MIT）是
开源自托管反检测浏览器与 Profile 管理器，负责 Prism 的 **Browser Identity / Fingerprint / Profile 层**：

- 相干指纹生成（OS/UA/GPU/屏幕/时区/语言 彼此一致）
- Profile 持久化（Cookie / LocalStorage / IndexedDB 随 Profile 留存）
- 持久会话（登录一次，下次启动仍在）
- 引擎可选：`cloak`(CloakBrowser) / `camoufox` / `patchright` / `playwright`
- 代理注入 + 出口 IP/泄漏检测

Prism **不**自研指纹、Profile 存储、指纹伪造 —— 全部委托 Persona Studio。

---

## 职责边界

| 层 | 归属 |
|---|---|
| 账号 / 平台 / 任务 / Celery / Redis | Prism（保留） |
| Proxy Manager（proxies、sticky 绑定、健康检测） | Prism（自研） |
| Browser Identity / Fingerprint / Profile | **Persona Studio** |
| 浏览器执行（平台 Adapter 驱动） | Prism Patchright（`connect_over_cdp`） |

固定链路：

```
Account
  → persona_profile_id（Prism 账号表）
  → Persona Profile（指纹 + 持久会话）
  → Sticky Proxy（Prism Proxy Manager 注入）
  → Patchright（connect_over_cdp 驱动）
  → Platform Adapter（发布/登录/数据回收）
```

---

## 安装 Persona Studio

```bash
git clone https://github.com/TechQaiser/persona-studio.git
cd persona-studio/engine

# 用 Prism 的 venv 或独立 venv 安装
pip install -e ".[api,launch]"
playwright install chromium      # 需要浏览器二进制

# 启动 HTTP API（dashboard 同款）
persona serve                    # 默认 http://127.0.0.1:8787
```

引擎选择（推荐 patchright，与 Prism 现有运行时一致）：

```bash
persona default-engine patchright
# 或每个 Profile 单独指定：persona create <name> --engine patchright
```

> 不装 Persona Studio 时，Prism 自动回退 **PatchrightBackend 直连模式**
> （每账号独立 `data/browser_profiles/<account>/` persistent context），
> 功能不中断，只是少了相干指纹/持久会话增强。

---

## Prism 侧配置（环境变量 / Settings）

| 配置 | 默认 | 说明 |
|---|---|---|
| `PERSONA_API_BASE` | `http://127.0.0.1:8787` | persona serve 地址 |
| `PERSONA_DEFAULT_ENGINE` | `patchright` | 新 Profile 默认引擎 |
| `PERSONA_INJECT_PROXY` | `true` | 创建 Profile 时注入账号固定代理 |
| `PERSONA_LAUNCH_TIMEOUT` | `60` | 启动超时（秒） |

---

## 集成实现

### 1. 账号绑定（已落地）

`cookie_accounts` 表新增：

```
proxy_id            -- Sticky Proxy（Proxy Manager 双写）
persona_profile_id  -- Persona Profile（默认 = account_id）
browser_backend     -- patchright / persona
```

`POST /api/v1/accounts/{id}/proxy/bind` 绑定代理时自动同步账号表；
`persona_profile_id` 默认取 `account_id`（Persona Profile name 一一对应）。

### 2. BrowserBackend（已落地）

`prism_backend/fastapi_app/services/browser_backend.py`：

- `PatchrightBackend` — 直连模式（回退）
- `PersonaBackend` — 调 Persona API：
  1. `ensure_profile(persona_profile_id, proxy, engine)` 幂等创建/更新
  2. `attach(persona_profile_id)` → 拿到 `wsUrl`（CDP）
  3. `patchright.connect_over_cdp(wsUrl)` → 返回 context/page

平台 Adapter 无感知（仍用 `utils.automation_provider` 的 patchright 接口）。

### 3. 浏览器生命周期 API（已落地）

```
POST /api/v1/accounts/{id}/browser/start    # 按绑定启动（headless 可选）
POST /api/v1/accounts/{id}/browser/stop     # 关闭进程，Profile 永久保留
GET  /api/v1/accounts/{id}/environment      # 环境视图（含 persona_online）
GET  /api/v1/ip-pool/persona/status         # Persona 服务状态
```

### 4. 旧登录态迁移（下一步）

现有 `cookiesFile/*.json`（Playwright storage state）在首次启动 Persona Profile 时
通过 `POST /api/profiles/{id}/cookies`（storage_state 格式）导入，保留登录态。

---

## 状态查看

账号管理页 → 每行「环境」按钮 → 显示：

- Browser: backend / persona_profile_id / persona_online
- Proxy: exit_ip / ASN / ISP / 地区 / 延迟 / 状态
- 固定绑定: 是 (Sticky) / 否

代理管理页 → 节点表显示 出口IP / ASN / 地区 / 绑定账号 / 状态 / 延迟。

---

## 说明

- 登录、发布、数据回收统一走同一 `persona_profile_id + proxy_id`（账号表持久绑定）。
- 3Proxy / gluetun / sing-box 只产出标准 HTTP/SOCKS5 endpoint，登记进 Proxy Manager，
  不进入 Prism 核心业务。
- MCP 不作为正式执行依赖；如后续需要 AI Browser Agent，通过 Persona attach 的
  CDP endpoint 扩展（预留 `PersonaBackend` 即可）。
