---
name: prism-publish-kuaishou
description: "Prism 快手发布：登录、校验、视频发布（及图文/笔记）与 CLI/API/MCP 工具契约。"
version: 1.0.0
author: Prism
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Prism, publish, kuaishou]
    related_skills: [prism-project-layout]
prerequisites:
  commands: [prism]
---
# Prism 快手发布

在 快手 上发布内容。能力已注册为独立工具，三层自动暴露：**MCP tool**、
**API**（`POST /api/v1/tool-catalog/<name>`）、**CLI**（`prism tool invoke <name>` / `prism kuaishou ...`）。

## 工具面

| 能力 | 工具名 |
|---|---|
| 视频发布 | `publish_video_to_kuaishou` |
| 图文/笔记发布 | `publish_note_to_kuaishou` |
| 登录 | `login_to_kuaishou` |
| 校验登录态 | `check_account_kuaishou` |

## 视频发布参数（`publish_video_to_kuaishou`）

通用：`account_file`（账号 cookie json 路径）、`file_path`（本地视频）、`title`（标题）、
`description`（描述）、`tags`（话题数组）、`schedule`（`YYYY-MM-DD HH:MM`，留空立即发布）、
`thumbnail`（封面）、`headless`（无头/有头）。

快手 专属：

| —— | 通用参数即可 |

## 登录（`login_to_kuaishou`）

扫码登录；有头，二维码展示给用户。

## 话题与坑

- 话题逐个输入再按空格分隔，避免粘连；图文/笔记走 publish_note_to_kuaishou。
- 一次输入完整 `#关键词` 再按空格确认/分隔，避免重复 `##`、换行或把多个话题粘成 `#话题1#话题2`。
- 账号 cookie 文件按 `runtime_home()/cookiesFile/kuaishou_<account>.json`。
- 其它通用后端/API 见 `docs/hermes-skills/prism-project-layout/SKILL.md` 与 `POST /api/v1/publish/batch`。

## 安全基线

- 抖音 `preview=true` 预览模式跑到「发布」前停，绝不真正发布。
- 禁止在生产使用 `app_new/platforms/douyin_http.py`（纯 HTTP 逆向，仅本地开发）。
- 不提交任何本地数据（cookies、指纹、代理、数据库、日志）到 Git。
