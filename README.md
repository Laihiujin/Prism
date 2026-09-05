<div align="center">

# Prism

**面向 MCN、短视频创作者的多账号多平台自动化矩阵分发**\
**内嵌 Agentic Development Runtime —— 多 AI Agent 协同 Computer Use 自我迭代与闭环**\
**支持异步高并发任务调度、分布式账号锁，实现单账号互斥/多账号并行**

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat-square&logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![Celery](https://img.shields.io/badge/Celery-37814A?style=flat-square&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io/)
[![Patchright](https://img.shields.io/badge/Patchright-2E3440?style=flat-square)](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python)
[![Persona Studio](https://img.shields.io/badge/Persona%20Studio-7C3AED?style=flat-square)](https://github.com/TechQaiser/persona-studio)
[![HermesAgent](https://img.shields.io/badge/HermesAgent-111827?style=flat-square)](https://github.com/NousResearch/hermes-agent)

[![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square)](https://www.apache.org/licenses/LICENSE-2.0)
[![Python](https://img.shields.io/badge/python-3.11-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Node](https://img.shields.io/badge/node-%3E%3D18-339933?style=flat-square&logo=nodedotjs&logoColor=white)](https://nodejs.org/)

**[English](README_EN.md)** | **简体中文**

</div>

---

## 关键词（便于搜索）/ Keywords

**中文**：抖音自动发布、小红书发布助手、快手、视频号、B站、TikTok 自动化、YouTube 上传、短视频矩阵发布、多账号内容分发、跨平台发布、定时发布、批量上传、自媒体矩阵、账号身份隔离、浏览器指纹、代理池、矩阵投放、AI 智能体、MCP

**English**：Douyin uploader、Xiaohongshu publishing、Kuaishou、WeChat Channels、Bilibili、TikTok automation、YouTube uploader、matrix publishing、multi-account content distribution、cross-platform publishing、scheduled publishing、browser fingerprint isolation、proxy pool、AI agent、MCP server

---

## 🟟 产品演示 / Product Demo

**交互演示 / Interaction Walkthrough**

![walkthrough](docs/demos/prism_wrap.gif)

---

[快速开始](#快速开始) · [架构设计](#架构设计) · [命令行](#命令行) · [API](#api) · [目录结构](#目录结构) · [参与贡献](#参与贡献) — [English Version ↑](README_EN.md)

## Prism 是什么

Prism 是一个**前后端分离**的自托管系统，用于在多个平台（抖音、快手、小红书、视频号、B 站、TikTok、YouTube）上批量运营多个创作者账号，且账号之间彼此隔离、互不牵连。核心架构基于 **Celery + Redis** 承载异步高并发任务，并通过**账号级 Redis 分布式锁**（`SET NX` + 心跳续期）保证同一账号同时只有一个活跃 Browser Runtime，互不争抢。

它不是剪辑工具，也不生产素材，定位在内容生产链路的下游，只做四件事：

- **账号身份隔离**——每个账号拥有独立的浏览器指纹、持久化登录会话和固定出口代理，让同一台机器上的十个账号在平台侧不会被识别为同一个操作者。
- **调度与执行**——素材 → 矩阵任务 → 队列化、并发、可失败重试的跨账号跨平台执行。
- **可观测性**——每账号运行时状态、任务日志与异常提醒。
- **数据回收**——发布后拉回数据指标，形成复盘闭环。

上游的内容生产（剪辑、素材生成）Prism 自己不碰，但可以通过内置的 **Hermes** 接进来：把开源项目集成进组件库与插件库（含 skill 库），让生产段的能力作为组件接入，拼成完整链路。

如果你在评估这个仓库，最值得先弄清楚的两件事是下面的[身份/执行链路](#账号执行链路)，以及 AI 层（`HermesAgent`）是发布链路之上的可选工具，而不是发布流程的依赖项。

## 功能概览

| 模块 | 已实现内容 |
|---|---|
| 账号管理 | 抖音/快手/小红书/视频号/B 站扫码登录，TikTok/YouTube 本机浏览器登录，Chrome 已登录 Profile 导入，掉线检测 |
| 身份层 | 通过集成 Persona Studio 生成相干指纹（OS/UA/GPU/时区/语言一致），未安装 Persona 时自动回退到独立的 Patchright Profile |
| 网络层 | 自研 Proxy Manager（健康检测、sticky 固定绑定、空闲池自动分配）+ 可选的 per-country mihomo 代理网关（新加坡/日本/美国/德国/台湾/香港） |
| 调度 | N 账号 × M 平台 × K 素材的矩阵任务生成，Celery/Redis 队列，定时发布，失败重试，每账号 Redis 分布式执行锁 |
| 监控 | 任务队列看板、执行日志、账号环境视图（一次调用返回浏览器 × 代理 × 运行时状态） |
| 数据回收 | 抖音/B 站本地采集，TikTok/YouTube 通过 TikHub API 采集，并自动反查回填账号资料（头像/昵称） |
| AI 编排 | 内置 Agent（HermesAgent）支持自然语言发布指令、标题标签生成，以及一键安装的技能/工具市场（`/tools`） |
| 接入方式 | Web 控制台（Next.js）、Electron 桌面客户端、`prism` 命令行、面向外部 AI Agent 的 stdio MCP 服务 |

## 架构设计

### 账号执行链路

所有自动化浏览器操作——登录、发布、数据采集——都走同一条固定链路：

```text
账号
  │
  ▼
Persona Profile          （指纹 + 持久化 Cookie/LocalStorage/IndexedDB）
  │
  ▼
Sticky Proxy             （Proxy Manager 固定绑定，可选按地区经 mihomo 路由）
  │
  ▼
Patchright（CDP）        （反检测浏览器驱动，connect_over_cdp）
  │
  ▼
平台适配器               （各平台的登录 / 发布 / 采集逻辑）
```

职责边界清晰地分给两个系统，而不是塞进一个单体：

| 层 | 归属 |
|---|---|
| 账号 / 平台 / 任务 / Celery / Redis | Prism |
| 代理注册、健康检测、sticky 绑定 | Prism（`services/ip_pool_service.py`） |
| per-country 代理网关（端口 7771–7776） | mihomo，通过 Persona Studio 的代理工具 |
| 浏览器指纹 / Profile 持久化 | Persona Studio（可选组件，MIT 协议，作为子模块引入） |
| 浏览器执行 | Prism，通过 Patchright `connect_over_cdp` |

如果未安装 Persona Studio，身份层会降级为每账号独立的 Patchright `persistent_context`（存于 `data/browser_profiles/<account>/`）——发布功能不受影响，只是失去跨会话的指纹一致性增强。

### 系统组件

```text
prism_frontend/     Next.js 控制台 —— 计划、矩阵任务、看板、/tools、/cms
prism_backend/      FastAPI 后端 —— REST API、矩阵调度、AI 服务、平台适配器
  ├── fastapi_app/    API 路由、服务层、SQLAlchemy 模型、Celery 任务
  ├── platforms/      各平台适配器（登录/发布/采集）
  ├── automation_worker/  独立执行 Worker
  ├── ai_service/     基于 LLM 的标题/标签生成、function calling
  └── douyin_tiktok_api/  内置的解析/数据 API（来自 Douyin_TikTok_Download_API）
desktop-electron/    包装 Web 控制台的桌面客户端
scripts/             启动、部署、运维、代理池脚本
tools/               自托管组件：hermes-agent、persona-studio、代理网关
```

### 进程拓扑（自托管部署）

| 进程 | 作用 | 默认地址 |
|---|---|---|
| `prism-backend` | FastAPI API + 矩阵调度 | `:7000` |
| `prism-worker` | 自动化 Worker（浏览器执行） | `:7001` |
| `prism-celery` | Celery 任务消费者 | 经由 Redis |
| `prism-frontend` | Next.js 控制台 | `:3000` |
| `persona-api` | Persona Studio 身份服务（可选） | `:8787` |
| `persona-proxy` | mihomo per-country 网关（可选） | `:7771`–`:7776` |
| HermesAgent | 内置 AI Agent 面板/WebUI | `:9119` / `:9131` |

所有进程统一由 **PM2（macOS/Linux/Windows）** 托管（`ecosystem.config.js`，跨平台），目的是让进程缺失"显性报错"而不是"静默降级"——比如后端在跑、Worker 没起，控制台依然能打开，但任务调度会悄悄失效，因此启动脚本默认整套一起拉起。

## 快速开始

**零依赖一键部署**：无需预装 **Python / Node / Redis** —— 仓库自带的部署器会自动补齐并把整套拉起来。macOS/Linux 用 `deploy.sh`，Windows 用 `deploy.cmd`（两者都是同一个 `deploy/deploy.py` 引擎的入口，幂等、可重复执行，日志写入 `runtime-data/deploy.log`）。

### macOS / Linux

```bash
git clone https://github.com/Laihiujin/Prism.git
cd Prism
./deploy.sh            # 等价于 ./deploy.sh full —— 一键部署整套并启动
```

`deploy.sh` 会先解析一个可用的 Python（优先系统 `python3`，否则用仓库内嵌的 micromamba 自动造一个 `.deployenv`，全程无需你手动装 Python），再把命令转发给部署引擎。

### Windows

```bat
git clone https://github.com/Laihiujin/Prism.git
cd Prism
deploy.cmd full
```

`deploy.cmd` 只是转到 `deploy.ps1`：没有系统 Python 时会自动下载一份便携 Python（python-build-standalone，放到 `.tools\python`），再运行同一个 `deploy\deploy.py` 引擎。

### `full` 一键部署会做什么

`full = plan → install-tools → bootstrap → start`，每一步幂等，已就绪的自动跳过：

- **plan**：只探测本机缺什么（Python / Node / Redis / 浏览器 / 依赖），不改动，可用 `--json` 输出机器可读结果
- **install-tools**：补齐缺失的 **Node / Redis** 等外部工具
- **bootstrap**：Prism 运行时 —— `prismenv` + 后端/前端依赖 + 生成 `.env` + 浏览器
- **start**：**PM2** 拉起整套进程 + 健康检查

### 部署 Web UI（可视化，逐条点按）

```bash
./deploy.sh webui        # macOS / Linux
deploy.cmd               # Windows：不带参数 = 启动部署 Web UI
```

打开 `http://127.0.0.1:8440`，可逐条执行 `plan` / `install-tools` / `bootstrap` / `start` / `stop` / `status`，日志以 SSE 流式展示（同时写入 `runtime-data/deploy.log`）。

### 常用子命令

| 子命令 | 作用 |
|---|---|
| `./deploy.sh`（无参，macOS/Linux）/ `deploy.cmd full`（Windows）| 完整一键部署（plan → install-tools → bootstrap → start）|
| `./deploy.sh start` / `deploy.cmd start` | 环境就绪时快速启动（跳过浏览器）|
| `./deploy.sh stop` / `deploy.cmd stop` | 停止（pm2 delete all，保留数据）|
| `./deploy.sh status` / `deploy.cmd status` | 进程 + 端点存活快照 |
| `./deploy.sh check` / `./deploy.sh plan` | 只探测环境 / 打印部署计划，不改动 |
| `./deploy.sh bootstrap` | 轻量引导（venv 路径，不重建组件环境）|
| `./deploy.sh webui` / `deploy.cmd`（无参，Windows）| 打开部署 Web UI（`127.0.0.1:8440`）|

启动顺序：**Redis → Celery Worker → Automation Worker → 后端 → 前端**。控制台 `http://localhost:3000`，API 文档 `http://localhost:7000/api/docs`。

> **进程托管**：macOS/Linux/Windows 统一由 **PM2** 托管全部进程（`ecosystem.config.js`，跨平台）。`full` 默认整套一起拉起，进程缺失会"显性报错"而非"静默降级"（比如后端在跑、Worker 没起，控制台虽能打开但调度会悄悄失效）。

> **虚拟环境**：仓库统一用名为 `prismenv` 的虚拟环境（部署器、桌面打包、Hermes 运行时都用它）。`full` 已包含创建 `prismenv` 并安装依赖；等价的手工命令为
> ```bash
> python3.11 -m venv prismenv
> prismenv/bin/python -m pip install -r requirements.txt   # Windows: prismenv\Scripts\python.exe
> cd prism_frontend && npm install && cd ..
> cp env.example .env
> ```

## 本地构建 / 打包 Electron 桌面客户端（可选）

`desktop-electron/` 是对 Web 控制台的桌面封装。打包时会从仓库带入 `prismenv`、`prism_backend`、`tools/hermes-agent`、`tools/hermes-webui`、`config`，以及 `prism_frontend/.next/standalone`、`prism_frontend/.next/static`、`prism_frontend/public`。因此**必须先构建好 Next.js 前端（standalone），否则会被 `electron-builder` 卡在缺资源上**。

### 0. 前置（与 Web 版一致，做一遍即可）

```bash
python3 bootstrap.py        # 创建 prismenv + 后端/前端依赖 + 生成 .env
```

### 1. 先构建前端（Next.js standalone 输出）

```bash
cd prism_frontend
npm install
npm run build               # 生成 .next/standalone、.next/static、public
```

要求 `prism_frontend/next.config.ts` 保留 `output: "standalone"`（打包管线依赖它）。

### 2. 打包

#### macOS

```bash
cd desktop-electron
npm install                 # 安装 electron / electron-builder（postinstall 自动 install-app-deps）

npm run pack                # electron-builder --dir → dist-build/<arch>/Prism.app
# 或构建完整安装镜像（x64 + arm64 的 dmg / zip）：
npx electron-builder --mac
```

- 产物在 `desktop-electron/dist-build/`。
- **macOS 需自备系统 Redis**：mac 安装包不内嵌 Redis 二进制，先启动本机 Redis：
  ```bash
  brew install redis && redis-server --daemonize yes
  ```
- 当前 `mac` 段配置为 `hardenedRuntime: false`、`gatekeeperAssess: false`，未做签名/公证，本地自用即可；对外分发需自行补签名与 notarization。

#### Windows

```bat
cd prism_frontend
npm install
npm run build

cd ..\desktop-electron
npm install
npm run build               :: NSIS 安装包 → dist-build\Prism-<version>-setup.exe
npm run build:dir           :: 仅目录包 → dist-build\win-unpacked\（便于本地测试）
```

- Windows 一键打包脚本（构建前端 + 后端服务 + pm2_controller + Inno/NSIS 安装包）：
  ```bat
  scripts\packaging\build-package.bat
  ```
- Windows 打包前置依赖：
  - `desktop-electron\resources\redis\`：放入 `redis-server.exe`、`redis-cli.exe`、`redis.windows*.conf`（从 [tporadowski/redis](https://github.com/tporadowski/redis/releases) 下载后放入）。
  - Chromium：由 `python bootstrap.py --browsers` 准备。
  - 进程托管：`pm2_controller.js`（electron-builder 从 `resources\pm2` 打包），不再是 supervisor。
  - 需要 `prismenv\Scripts\python.exe` 与 `prismenv\_python\python.exe`（`bootstrap.py` 已建好）。

### 3. 本地联调（不打包，直接跑 Electron 壳）

```bash
# 先让外部栈跑起来，再让 Electron 指向它：
#   macOS:  ./start-mac.sh      Windows: start.bat
cd desktop-electron
npm run start               # electron . —— 连接到已启动的外部后端/前端
```

> Windows 也可直接用仓库根目录的 `launch-electron-desktop.bat`；macOS 想让 Electron 自己拉起前后端，可改用 `npm run dev`（设置 `PRISM_START_SERVICES=1`、`PRISM_START_FRONTEND=1`）。

## 命令行

`prism` CLI 与 Web 控制台、桌面端共用同一套平台适配器、账号存储和 Patchright 运行时——从任一入口发起的任务，在其他入口都能看到。

```bash
pip install -e .

prism douyin login --account creator
prism douyin check --account creator
prism douyin upload-video \
  --account creator \
  --file ./video.mp4 \
  --title "示例标题" \
  --description "示例简介" \
  --tags "Prism,自动发布"

# 定时发布（本地时间）
prism xiaohongshu upload-video --account creator --file ./video.mp4 \
  --title "示例" --schedule "2026-08-18 20:30"

# 无原生扫码登录的平台（首次需真实浏览器登录一次）
prism tiktok login --account creator
prism youtube login --account creator

prism accounts            # 列出所有账号（JSON）
prism history             # 查询发布历史（JSON）
prism mcp                 # 以 MCP stdio 服务方式启动，供外部 AI Agent 接入
```

## API

REST API 统一挂载在 `/api/v1` 下，按业务域分组（`accounts`、`matrix`、`publish`、`persona`、`persona_proxy`、`ip_pool`、`analytics`、`tools`、`agent` 等）。交互式文档自动生成于 `/api/docs`（Swagger）与 `/api/redoc`。

生成矩阵发布任务：

```http
POST /api/v1/matrix/generate_tasks
Content-Type: application/json

{
  "platforms": ["xiaohongshu", "douyin"],
  "accounts": {
    "xiaohongshu": ["account_id_1", "account_id_2"],
    "douyin": ["account_id_3"]
  },
  "materials": ["material_id_1", "material_id_2"],
  "title": "xxxxx",
  "topics": ["#xxx", "#xxx"]
}
```

将账号绑定到某个代理地区：

```http
GET  /api/v1/accounts/{account_id}/persona-proxy
PUT  /api/v1/accounts/{account_id}/persona-proxy
```

单次调用获取账号完整环境快照（浏览器后端 + 代理 + 运行时状态）：

```http
GET /api/v1/accounts/{account_id}/environment
```

## 目录结构

```text
prism_backend/fastapi_app/
  api/v1/         30+ 个业务域路由（accounts、matrix、publish、persona、ip_pool、tikhub…）
  services/       业务逻辑层 —— matrix_scheduler、ip_pool_service、runtime_lock_service、persona_client…
  models/         SQLAlchemy 模型
  tasks/          Celery 任务定义
  agent/          HermesAgent 集成 + MCP 工具桥接
prism_backend/platforms/     各平台登录/发布/采集适配器
prism_frontend/src/app/       Next.js 路由 —— dashboard、matrix、accounts、ip-pool、persona、tools、cms
desktop-electron/            Electron 封装与安装包构建
scripts/                     launchers/、deploy/、maintenance/、ip_pool/、hermes/
```

## 配置

两个文件决定能否正常跑起来：

- **`.env`**——端口、Redis 地址、浏览器路径、前后端互联地址、`PLAYWRIGHT_HEADLESS`、`PRISM_BROWSER_BACKEND_DEFAULT`（`patchright` / `persona`）、`PRISM_DOUYIN_LOGIN_MODE`（`browser` / `http`）。
- **`prism_backend/config/llm_config.toml`**——HermesAgent 及 AI 标题/标签生成所用的 LLM provider / model / api_key / base_url。

## 项目支持与采用

Prism 在几个关键难点上选择集成而非重复造轮子，各自是独立的上游项目，遵循各自许可证（详见 [`NOTICE.txt`](./NOTICE.txt)）：

| 组件 | 上游项目 | 许可证 |
|---|---|---|
| CLI / 发布适配器基础 | [social-auto-upload](https://github.com/dreammis/social-auto-upload) | MIT |
| 抖音 / TikTok 解析与数据 API | [Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API) | Apache-2.0 |
| 本地 AI Agent 运行时 | [HermesAgent](https://github.com/nousresearch/hermes-agent) | MIT |
| 浏览器身份/指纹层 | [Persona Studio](https://github.com/TechQaiser/persona-studio) | MIT |

Prism 自身代码基于 Apache-2.0 开源；引入的 MIT 组件保留原始许可证与署名要求。

## 已知局限

如实列出现状，而不是回避：

- **默认存储为 SQLite**——单机自托管场景下没问题；如果要在 Celery 上跑真正的高并发写入，需要提前规划迁移到服务端数据库。
- **表结构变更靠手写脚本**，不是标准迁移框架——在共享环境里改表结构前建议先看一遍 `prism_backend/db/`。
- **CORS 默认 `allow_origins=["*"]`**（`fastapi_app/main.py`）——如果要把 API 暴露到本机之外，务必先收紧这项配置。

## 合规声明 / Compliance

请仅在**授权 / 自有账号场景**下使用，并遵守各平台用户协议。

- 请勿提交 cookie、登录态、浏览器 profile、设备指纹、代理凭证、API key 到仓库（详见 [`AGENT.md`](./AGENT.md) 与 [`.gitignore`](./.gitignore)）。

本项目**仅限测试、学术研究与技术交流使用**，请勿用于任何违反法律法规、平台服务条款的恶意攻击用途，因违规使用产生的后果由使用者自行承担。

## 参与贡献

欢迎提交 Issue 和 PR。如果你在用 AI 编程助手协作本仓库，请先看 [`AGENT.md`](./AGENT.md) 里的仓库卫生规则（不要提交 cookie、浏览器 profile、指纹、代理数据）。

## 许可

Apache License 2.0，详见 [`LICENSE`](./LICENSE)。项目中引入的 MIT / Apache-2.0 上游组件继续适用各自原始许可证，署名要求见 [`NOTICE.txt`](./NOTICE.txt)。

## Community

本项目在 [LINUX DO](https://linux.do/) 社区进行交流与开源推广。

感谢 LINUX DO 社区为开发者提供交流与分享的平台。

## [BuymeaCoffee](https://buymeacoffee.com/laihiujin3)

| | | |
|-|-|-|
| ![1d1114b7-9c71-4c18-91df-0a462bed5405](https://github.com/user-attachments/assets/f0c38071-f69a-4262-a339-182c090d4c41) | ![dac9dc35-e027-42e8-b6aa-81f3211906da](https://github.com/user-attachments/assets/761ae5f1-8350-49d6-bba6-de2f01f1b73e) | <img width="1284" height="2289" alt="prism" src="https://github.com/user-attachments/assets/3d5234d1-2a85-4eea-8435-5d1642790805" /> |

<div align="right">

[回到顶部](#prism) · [English Version ↑](README_EN.md)

</div>
