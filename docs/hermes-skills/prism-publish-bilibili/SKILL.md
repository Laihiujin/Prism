---
name: prism-publish-bilibili
description: "Prism B站发布：登录、校验、视频发布（及无图文）与 CLI/API/MCP 工具契约。"
version: 1.0.0
author: Prism
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Prism, publish, bilibili]
    related_skills: [prism-project-layout]
prerequisites:
  commands: [prism]
---
# Prism B站发布

在 B站 上发布内容。能力已注册为独立工具，三层自动暴露：**MCP tool**、
**API**（`POST /api/v1/tool-catalog/<name>`）、**CLI**（`prism tool invoke <name>` / `prism bilibili ...`）。

## 工具面

| 能力 | 工具名 |
|---|---|
| 视频发布 | `publish_video_to_bilibili` |
| 图文/笔记发布 | `（B站 不支持图文/笔记发布）` |
| 登录 | `login_to_bilibili` |
| 校验登录态 | `check_account_bilibili` |

## 视频发布参数（`publish_video_to_bilibili`）

通用：`account_file`（账号 cookie json 路径）、`file_path`（本地视频）、`title`（标题）、
`description`（描述）、`tags`（话题数组）、`schedule`（`YYYY-MM-DD HH:MM`，留空立即发布）、
`thumbnail`（封面）、`headless`（无头/有头）。

B站 专属：

| `tid` | 分区 ID（必填） |
| `tag` | 独立标签（逗号分隔） |

## 登录（`login_to_bilibili`）

必须在本机交互终端 `biliup login`；非交互环境返回失败。

## 话题与坑

- 图文不支持；走独立标签 --tag。走 biliup 命令行，非浏览器自动化。
- 一次输入完整 `#关键词` 再按空格确认/分隔，避免重复 `##`、换行或把多个话题粘成 `#话题1#话题2`。
- 账号 cookie 文件按 `runtime_home()/cookiesFile/bilibili_<account>.json`。
- 其它通用后端/API 见 `docs/hermes-skills/prism-project-layout/SKILL.md` 与 `POST /api/v1/publish/batch`。

## 安全基线

- 抖音 `preview=true` 预览模式跑到「发布」前停，绝不真正发布。
- 禁止在生产使用 `app_new/platforms/douyin_http.py`（纯 HTTP 逆向，仅本地开发）。
- 不提交任何本地数据（cookies、指纹、代理、数据库、日志）到 Git。
