# Prism Rust 轻量化预开发架构规划

> 状态：预开发规划，不改变当前生产运行链路。  
> 原则：**Rust 负责产品运行骨架；Python + Patchright 负责平台浏览器自动化。**

## 1. 背景与目标

Prism 是一个自托管的多平台内容编排与发布系统，现有能力包括素材、账号、计划、排期、队列、执行监控、数据回收、Web 控制台和桌面端。

当前桌面运行链路由 Electron、Python 服务、多个启动脚本以及浏览器自动化进程组成。后续引入 Rust 的目的不是重写产品，而是降低桌面版的资源占用、安装复杂度与进程管理成本。

目标：

- 桌面端由 Electron 逐步迁移到 Tauri，降低包体、内存与启动开销；
- 以一个 Rust 守护进程统一管理端口、子进程、健康检查、日志与升级；
- 逐步将本地任务调度、任务状态机和 CLI 收敛到 Rust；
- 保持现有 FastAPI API、数据和平台上传器可用；
- 保持 Patchright 作为唯一的生产浏览器自动化运行时。

非目标：

- 不以 Rust 重写抖音、小红书、快手、视频号、B 站等页面适配器；
- 不将 Patchright 替换为 Rust 的 CDP 或 Playwright 封装；
- 不在一次发布中同时替换桌面壳、调度器和自动化层；
- 不破坏已有 HTTP API、Cookie 文件、SQLite 数据和桌面用户数据。

## 2. 目标架构

```text
┌───────────────────────────────────────────────────────┐
│ Prism Desktop（Tauri + React/Next.js UI）              │
└──────────────────────────┬────────────────────────────┘
                           │ IPC / localhost HTTP
┌──────────────────────────▼────────────────────────────┐
│ prism-core（Rust daemon）                              │
│ - 生命周期与端口管理   - 健康检查与崩溃重启            │
│ - 本地任务调度         - CLI / 日志 / 自动更新          │
│ - SQLite 状态索引      - 配置和密钥引用管理             │
└───────────────┬──────────────────────┬────────────────┘
                │ HTTP                 │ stdio / HTTP
┌───────────────▼──────────────┐  ┌────▼─────────────────┐
│ prism-api（Python / FastAPI）│  │ prism-automation      │
│ - 既有 REST API              │  │ （Python + Patchright）│
│ - AI、素材、账号、数据服务   │  │ - 登录、上传、校验     │
└──────────────────────────────┘  │ - 平台适配器、截图诊断 │
                                  └───────────────────────┘
```

`prism-automation` 是技术无关的服务名；其实现固定使用 Patchright。这样未来可调整自动化服务内部组织，而不会让公开 API 或桌面进程名称绑定到具体库名。

## 3. 组件职责

| 组件 | 技术 | 负责 | 不负责 |
| --- | --- | --- | --- |
| `prism-desktop` | Tauri + React | 界面、系统托盘、桌面 IPC、安装包 | 平台页面操作、调度算法 |
| `prism-core` | Rust | 服务托管、任务状态机、CLI、健康检查、日志、SQLite 索引 | 平台选择器与 Cookie 注入 |
| `prism-api` | Python / FastAPI | 既有 Web API、AI 服务、账号/素材/数据业务 | 桌面进程生命周期 |
| `prism-automation` | Python / Patchright | 登录、上传、账号状态检查、浏览器诊断 | 长期任务编排、桌面 UI |

## 4. 为什么保留 Python + Patchright

平台上传是变化最快、风险最高的部分。现有上传器、页面选择器、异常处理、Cookie 逻辑和上游参考实现均在 Python 生态；Patchright 也是当前发布自动化的首选运行时。

将这部分换成 Rust 会造成两类风险：

1. 需要重新验证所有平台页面交互、无头模式和反自动化兼容性；
2. Rust 的浏览器自动化库不能直接替代 Patchright 的当前行为。

因此 Rust 只负责让系统更轻、更稳地运行；它通过稳定契约调用 Python 自动化服务，而不是接管浏览器控制。

## 5. 服务契约

### 5.1 自动化服务

保留并逐步规范为本地 HTTP API：

```text
POST /v1/automation/login
POST /v1/automation/check
POST /v1/automation/publish/video
GET  /v1/automation/jobs/{job_id}
GET  /healthz
```

所有请求必须带：

```json
{
  "request_id": "uuid",
  "platform": "douyin",
  "account_id": "creator_a",
  "headless": true
}
```

发布任务应返回可持久化的 `job_id`，并使用统一状态：

```text
queued → running → succeeded | failed | cancelled
```

失败响应需包含可脱敏的 `error_code`、`message`、`retryable`、`diagnostic_artifacts`；截图、HTML 和日志文件只保存路径或受控访问地址，不直接嵌入响应。

### 5.2 Rust Core 与 FastAPI

迁移期间，`prism-core` 不直接读取或修改 FastAPI 的业务表。它只维护自己的本地运行状态库，例如：

```text
runtime.db
  managed_processes
  task_runs
  task_events
  health_checks
  migration_state
```

业务数据继续由现有数据库与 FastAPI 管理。只有在调度器迁移成熟后，才对任务表建立版本化迁移计划。

## 6. 建议目录结构

```text
prism/
├── prism_core/            # Rust workspace：daemon、scheduler、shared types
├── prism_desktop/         # Tauri desktop shell
├── prism_backend/         # Python FastAPI 与既有业务服务
├── prism_automation/      # Python + Patchright 自动化服务（可从 backend 中拆出）
├── prism_frontend/        # Web UI；后续可作为 Tauri 前端复用
├── prism_cli/             # 初期 Python CLI，后期由 Rust 二进制接管
└── docs/
```

在第一阶段不强制移动现有 Python 文件。先完成服务边界和接口稳定，再按模块迁移，避免“目录重组”和“运行逻辑重写”同时发生。

## 7. 分期计划

### Phase 0：稳定基础（当前优先）

- 完成 Prism 品牌、目录、环境变量和桌面应用标识迁移；
- 统一为 Patchright 生产运行时；
- 提供 `prism` CLI，支持账号登录、账号检查和视频发布；
- 将自动化 Worker 的公开名称统一为 `automation_worker`；
- 为现有启动链路补足健康检查与端到端测试。

验收：Web、桌面端、Docker、CLI 都使用相同的 `PRISM_*` 配置，并能完成至少一个平台的登录、检查与发布模拟。

### Phase 1：Rust Supervisor（最小可行迁移）

新建 `prism-core`，仅做服务守护，不接管业务调度：

- 启动 Redis、FastAPI、Celery、Automation Worker、前端；
- 处理端口分配、健康检查、退出回收和重启策略；
- 提供 `prism-core status|start|stop|logs`；
- 维护独立的 `runtime.db`。

验收：桌面端和命令行都通过 Rust daemon 启停服务；失败重启和日志采集不再依赖批处理脚本。

### Phase 2：Tauri Desktop

- 用 Tauri 替换 Electron 的主进程、安装器和系统托盘；
- 复用现有 React UI，优先将其编译为静态前端或轻量前端；
- 桌面 IPC 只调用 `prism-core`，不直接拉起 Python 子进程；
- 保留 Electron 发行版一个过渡版本，提供数据迁移与回退说明。

验收：Windows 桌面端可安装、升级、启动、显示服务状态、打开 Web UI，并支持自动化运行时诊断。

### Phase 3：任务调度器迁移

- 在 Rust 中实现时间触发、并发上限、指数退避、幂等键和任务状态机；
- Rust Scheduler 通过自动化服务契约执行发布；
- Celery 仅保留给未迁移的异步业务或作为过渡消费者；
- 使用双写/影子运行比较新旧调度决策，之后再切流。

验收：同一批计划在影子模式下任务数量、排期和重试结果与现有系统一致；切流后可回退到 Celery。

### Phase 4：Rust CLI 与发布工件

- 将 `prism` 命令入口迁移成 Rust 二进制；
- CLI 通过 `prism-core` 调用本地或远程实例；
- 保持命令语义稳定：`prism <platform> login|check|upload-video`；
- 为 Windows、macOS、Linux 发行签名和自动更新工件。

## 8. 技术选型建议

| 领域 | 推荐 | 理由 |
| --- | --- | --- |
| Rust Runtime | Tokio | 成熟的异步、子进程与网络支持 |
| HTTP / IPC | Axum + localhost HTTP | 易调试，能同时服务 CLI、Tauri 和 Web |
| SQLite | SQLx | 迁移、类型安全查询、异步支持 |
| 任务调度 | 自研状态机 + Tokio 时间驱动 | 发布任务需要幂等、可观察和可控重试 |
| Desktop | Tauri v2 | 资源占用低，Rust 主进程原生整合 |
| 日志 | tracing + tracing-subscriber | 可结构化输出并关联 `request_id` / `job_id` |
| 配置 | TOML + 环境变量 | 与当前 `.env` 兼容，便于桌面端管理 |

## 9. 数据与兼容性要求

- 运行时配置统一使用 `PRISM_*` 环境变量；
- 用户数据目录和 Cookie 目录迁移必须可回滚、可备份；
- CLI 参数与 HTTP 请求需要版本号，避免未来破坏自动化脚本；
- 同一个发布任务必须有幂等键，重复提交不得重复发帖；
- 任务状态变更必须记录事件时间、执行器版本、平台与账号；
- 自动化服务崩溃后，`running` 任务应由 Core 标记为待确认或可重试，不能直接误报成功。

## 10. 风险与控制

| 风险 | 控制方式 |
| --- | --- |
| 同时重写过多层 | 按 Phase 逐层替换，每阶段保持可回退 |
| 平台页面频繁变更 | 平台适配器继续保留 Python + Patchright 快速迭代 |
| Rust/Python 双调度 | 先影子运行，未验证前只允许一个执行者实际发布 |
| 桌面用户数据丢失 | 迁移前备份，使用版本化迁移状态与恢复命令 |
| CLI 破坏脚本兼容 | 固定命令语义、提供 `--json` 输出与弃用周期 |

## 11. 进入开发的前置条件

只有满足以下条件后才启动 Phase 1：

1. Prism 改名迁移已完成，旧名称不再出现在公开 API、桌面配置和新文档中；
2. Patchright 单运行时已在本地和 Docker 验证；
3. 至少覆盖抖音、小红书各一个登录/发布冒烟流程；
4. 现有服务有统一的 `/healthz` 或等价健康检查；
5. 当前 Celery 任务的状态、重试和失败语义已形成测试基线。

## 12. 成功标准

Rust 迁移完成后，Prism 应达到：

- 桌面启动不再依赖多个 `.bat` 脚本；
- 用户只需安装一个桌面应用或一个 `prism` 二进制；
- 所有后台服务由单一 daemon 管理并可诊断；
- 自动化发布能力保持由 Patchright 驱动，平台适配不降级；
- 任务可以可靠恢复、观察、重试和回退；
- Web 自托管、Docker 与 Desktop 都继续可用。
