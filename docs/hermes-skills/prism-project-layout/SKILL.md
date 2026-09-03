---
name: prism-project-layout
description: "Prism 项目布局与调用指南：目录结构、全部后端 API 路由、prism CLI 用法、Hermes MCP 工具清单，以及各服务端口。"
version: 1.0.0
author: Prism
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Prism, project-layout, api, cli, mcp, publishing]
    related_skills: []
prerequisites:
  commands: [prism]
---

# Prism 项目布局与调用指南

Prism 是一个多平台内容编排与发布项目（矩阵调度 + AI 服务 + 账号/代理/运行时管理），
技术栈为 FastAPI（后端）、Next.js（前端）、Celery/Redis（任务队列）、Patchright（浏览器自动化）、
Electron（桌面端）、Hermes Agent（内置 AI 助手）。本技能描述项目布局，以及 Hermes 可用的
**全部 API、CLI、MCP 工具**及其调用方式。

## 1. 项目目录布局

```text
Prism/
├── prism_backend/          # FastAPI 后端
│   ├── fastapi_app/
│   │   ├── main.py         # 应用入口（docs_url=/api/docs, openapi_url=/api/openapi.json）
│   │   ├── api/v1/         # v1 路由（见 §2 全部前缀）
│   │   │   └── agent/      # Hermes/OpenClaw Agent API + config 路由
│   │   ├── agent/          # Hermes 集成层
│   │   │   ├── hermes_agent.py        # CLI 桥接 + Dashboard/WebUI 进程托管
│   │   │   ├── hermes_config.py       # hermes_agent.toml ↔ hermes-home/config.yaml 同步
│   │   │   ├── hermes_update.py       # 更新调度器
│   │   │   ├── mcp_server.py          # stdio MCP server（暴露 BaseTool 目录）
│   │   │   ├── hermes_tools*.py       # BaseTool 工具实现
│   │   │   ├── tikhub_tools.py        # TikHub 工具
│   │   │   └── tool_runtime.py        # BaseTool/ToolResult 基类
│   │   ├── core/config.py   # 端口/前缀等配置（API_V1_PREFIX=/api/v1, PORT=7000）
│   │   └── services/        # 业务服务（含 tool_registry.py：/tools 技能管理）
│   ├── config/              # 配置目录
│   │   ├── conf.py
│   │   └── hermes_agent.toml          # Hermes 模型/provider/api_key 配置（用户编辑）
│   ├── db/                  # 数据库（本地数据，不提交）
│   └── uploader/            # 各平台上传统一封装（douyin/ks/xiaohongshu/tencent/bilibili/baijiahao/tk/youtube）
├── prism_frontend/          # Next.js 控制台（端口 3000）
├── prism_cli.py             # prism CLI 入口（pyproject 注册为 `prism` 命令）
├── scripts/                 # 启动/运维脚本（deploy/dev/fixes/hermes/ip_pool/launchers/maintenance/packaging/release/tests/utilities）
├── tools/                   # 自托管组件
│   ├── hermes-agent/        # Hermes Agent 运行时（git 子模块，不提交）
│   ├── hermes-home/         # Hermes 运行时数据（config.yaml、skills/、sessions/…，不提交）
│   ├── hermes-webui/        # Hermes WebUI（端口 9131）
│   └── persona-studio/      # Persona 指纹/浏览器身份
├── desktop-electron/        # Electron 客户端与打包
├── docs/                    # 文档（agent-bootstrap.md、architecture/…）
├── runtime-data/            # 运行时数据（app/hermes-home/skills 为 /tools 技能管理根，不提交）
├── .env                     # 本地环境配置（端口、Redis、浏览器路径、Playwright 等）
└── AGENT.md                 # 仓库规范（敏感数据不入库、border token 规则等）
```

## 2. 后端 API（全部前缀）

后端基础地址：`http://127.0.0.1:7000`（以 `.env` 的 `BACKEND_PORT` 为准；Hermes agent 层默认
`9200` 由 `AGENT_API_BASE_URL` 覆盖）。API v1 前缀：`/api/v1`。
在线文档：`http://127.0.0.1:7000/api/docs`；OpenAPI JSON：`http://127.0.0.1:7000/api/openapi.json`。
调用任何 API 前，可先 GET `/api/openapi.json` 获取全部路径、方法、参数与响应结构。

| 前缀 | 说明 |
|---|---|
| `/api/v1/ping` | 连通性测试 |
| `/api/v1/accounts` | 账号管理（列表/增删改/状态） |
| `/api/v1/accounts/tools` | 账号工具 |
| `/api/v1/campaigns` `/plans` `/task-packages` | 投放计划 / 计划别名 / 任务包 |
| `/api/v1/auth` `/auth/login/browser` | 登录认证 / 浏览器登录 |
| `/api/v1/files` `/materials` | 文件管理 / 素材管理 |
| `/api/v1/analytics` | 数据分析（发布统计/互动/增长/趋势） |
| `/api/v1/scripts` | 后端脚本（GET /list 列出白名单脚本，POST /run 执行） |
| `/api/v1/publish` | 发布管理（矩阵/批量发布） |
| `/api/v1/tasks` `/tasks/distribution` | 任务队列 / 分发别名 |
| `/api/v1/recovery` | 恢复/补偿 |
| `/api/v1/data` | 数据 |
| `/api/v1/ai` `/ai/threads` `/ai-prompts` | AI 服务 / 线程 / AI 配置 |
| `/api/v1/dashboard` | 仪表盘 |
| `/api/v1/system` `/browser-profiles` | 系统维护 / 浏览器档案 |
| `/api/v1/verification` | 验证码 |
| `/api/v1/agent` `/agent/config` | Hermes Agent API（run/stream/stop/confirm、config/hermes、runtime、update、dashboard） |
| `/api/v1/matrix` | 矩阵发布调度 |
| `/api/v1/manual-tasks` | 人工任务管理 |
| `/api/v1/ip-pool` | IP 池管理（list/add/remove/test） |
| `/api/v1/concurrency` | 并发控制 |
| `/api/v1/cookies` | Cookie 验证/导入导出/刷新 |
| `/api/v1/creator` | 创作者中心 |
| `/api/v1/mediacrawler` | MediaCrawler |
| `/api/v1/crawler` | 混合爬虫（fetch_video / fetch_account_videos） |
| `/api/v1/tikhub` | TikHub 桥接 |
| `/api/v1/persona-proxy` | 代理网关（per-country 7771-7776） |
| `/api/v1/persona` | Persona Dashboard 托管 |
| `/api/v1/platforms` | 平台总入口 |
| `/api/v1/platforms/douyin` `/kuaishou` `/xiaohongshu` `/tencent` `/bilibili` `/tasks` | 各平台接口与平台任务 |
| `/api/v1/tools` | 开发者工具（/tools 页面，一键安装/启停 Hermes 技能） |
| `/api/v1/ccswitch` | CC Switch 桥接 |

## 3. CLI（prism）

入口：`prism_cli.py`，pyproject 注册为 `prism` 命令。用法：
`prism <platform> <action> [flags]`，平台与动作：

| 平台 | 动作 |
|---|---|
| `douyin` `kuaishou` `xiaohongshu` | `login` `check` `upload-video` `upload-note` |
| `bilibili` | `login` `check` `upload-video`（login 需交互终端，用 biliup） |
| `channels`（别名 `tencent`） | `login` `check` `upload-video` |
| `baijiahao`（别名 `baijia`） | `login` `check` `upload-video` |
| `tiktok`（别名 `tk`） | `login` `check` `upload-video` |
| `youtube`（别名 `yt`） | `login` `check` `upload-video` |
| `service` | 进程管理（start/stop/restart/status/logs/list，转发给 process_manager） |

常用 flag：`--account <名称>`（必填）、`--file`、`--title`、`--desc/--description`、`--tags`、
`--schedule "YYYY-MM-DD HH:MM"`、`--thumbnail`、`--headless/--headed`、`--debug`。
B 站 `--tid` 必填；抖音支持 `--thumbnail-landscape/--thumbnail-portrait/--product-link/--product-title/--declaration`。

其他脚本目录：`scripts/` 与 `prism_backend/scripts/`（启动、维护、部署、测试等）。

## 4. Hermes MCP 工具（全部清单）

Hermes 通过 `tools/hermes-home/config.yaml` 的 `mcp_servers.prism` 注册了一个 stdio MCP server
（`python -m fastapi_app.agent.mcp_server`），把 `prism_backend/fastapi_app/agent/` 下所有
`BaseTool` 子类暴露为可调用工具（`tools/list` + `tools/call`）。完整清单：

**账号/素材/发布（hermes_tools.py）**
- `list_accounts` — 列出可用账号（platform/status 筛选）
- `list_files` / `get_file_detail` — 素材视频列表 / 详情
- `generate_ai_metadata` — AI 生成标题/标签（可传 `platform` 启用平台网感文案规则 + 字数/话题红线，见 `prism-copywrite`）
- `POST /api/v1/ai/chat`（设置页"标题生成 / 对话模型"）— 请求体可带 `platform`（`douyin`/`xiaohongshu`/`kuaishou`/`bilibili`/`video_account`/`tiktok`）与 `language`（`zh`/`en`/`bilingual`，TikTok 默认双语），生成结果按平台红线截断。
- `publish_batch_videos` — 批量发布视频
- `create_publish_preset` / `list_publish_presets` / `use_preset_to_publish` — 发布预设
- `get_task_status` / `list_tasks_status` — 任务状态查询
- `data_analytics` — 数据分析报告
- `external_video_crawler` / `account_video_crawler` — 外部链接抓取 / 项目账号视频抓取

**扩展（hermes_tools_extended.py，与上表重名者以 hermes_tools 为准）**
- `ip_pool_manager` — IP 池 list/add/remove/test
- `run_backend_script` — 执行后端白名单脚本（POST /api/v1/scripts/run）
- `cookie_manager` — Cookie list/export/import/refresh

**社媒 API（hermes_tools_social_api.py，走 /api/v1/douyin-tiktok/api/...）**
- `douyin_fetch_user_info` / `douyin_fetch_user_videos` / `douyin_fetch_video_detail`
- `tiktok_fetch_user_info` / `tiktok_fetch_user_videos` / `tiktok_fetch_video_detail`
- `bilibili_fetch_user_info` / `bilibili_fetch_user_videos` / `bilibili_fetch_video_detail`

**TikHub（tikhub_tools.py，需配置 TikHub API key）**
- `tikhub_kuaishou_user_info` / `tikhub_kuaishou_user_posts`
- `tikhub_xiaohongshu_user_info` / `tikhub_xiaohongshu_user_notes` / `tikhub_xiaohongshu_note_id`
- `tikhub_wechat_channels_home` / `tikhub_wechat_channels_video_detail`

## 5. 服务端口速查

| 服务 | 端口 |
|---|---|
| FastAPI 后端 | 7000（`.env` BACKEND_PORT） |
| Next.js 前端 | 3000 |
| Hermes Dashboard | 9119 |
| Hermes WebUI | 9131 |
| Persona API | 8787 |
| Persona per-country 代理网关 | 7771–7776 |
| Redis | 6379 |

## 6. Hermes 集成点

- 模型配置：`prism_backend/config/hermes_agent.toml`（`[llm]` provider/model/api_key/base_url，`[runtime]` max_turns）。
  保存时由 `hermes_config.py::sync_agent_config_to_runtime` 同步到 `tools/hermes-home/config.yaml`，
  并写入 `mcp_servers.prism`（指向 `python -m fastapi_app.agent.mcp_server`）。
- Agent 执行：`POST /api/v1/agent/hermes-run`（一次性）、`/agent/hermes-stream`（SSE 流式）、
  `/agent/hermes-stop`、`/agent/hermes-confirm`；配置见 `/agent/config/hermes*`。
- Dashboard/WebUI 启动：`POST /agent/config/hermes/dashboard/start`（backend: official|webui）、
  `/dashboard/stop`；状态 `GET /agent/config/hermes/runtime`。
- 更新：`GET /agent/config/hermes/update`、`PUT .../update/settings`、`POST .../update/check`、`POST .../update/apply`。

## 7. 工作流建议

1. **先看文档**：`docs/agent-bootstrap.md`（CLI 契约）、`README.md`、`AGENT.md`（仓库规范）。
2. **矩阵/批量操作**优先走后端 API（/matrix、/publish、/tasks），**单平台明确操作**走 `prism` CLI。
3. **数据采集**优先用 MCP 工具（social API / crawler / tikhub），不要滥用浏览器自动化。
4. **账号操作前**先 `list_accounts` 或 `prism <platform> check --account <name>` 验证。
5. **登录产生二维码**时展示图片给用户；B 站登录必须在用户本地交互终端执行。
6. 不提交任何本地数据（cookies、浏览器档案、指纹、代理、数据库、日志）到 Git。
