---
name: prism-publish-douyin
description: "Prism 抖音发布：登录、校验、视频发布（及图文/笔记）与 CLI/API/MCP 工具契约。"
version: 1.0.0
author: Prism
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Prism, publish, douyin]
    related_skills: [prism-project-layout]
prerequisites:
  commands: [prism]
---
# Prism 抖音发布

在 抖音 上发布内容。能力已注册为独立工具，三层自动暴露：**MCP tool**、
**API**（`POST /api/v1/tool-catalog/<name>`）、**CLI**（`prism tool invoke <name>` / `prism douyin ...`）。

## 工具面

| 能力 | 工具名 |
|---|---|
| 视频发布 | `publish_video_to_douyin` |
| 图文/笔记发布 | `publish_note_to_douyin` |
| 登录 | `login_to_douyin` |
| 校验登录态 | `check_account_douyin` |

## 视频发布参数（`publish_video_to_douyin`）

通用：`account_file`（账号 cookie json 路径）、`file_path`（本地视频）、`title`（标题）、
`description`（描述）、`tags`（话题数组）、`schedule`（`YYYY-MM-DD HH:MM`，留空立即发布）、
`thumbnail`（封面）、`headless`（无头/有头）。

抖音 专属：

| `product_link` `product_title` | 商品链接/短标题（购物车） |
| `declaration` | 自主声明（如'内容由AI生成'） |
| `location` | 位置 POI |
| `random_cover` | 随机选推荐封面 |
| `mini_program_link/title/name/type` | 小程序/挂载对象 |
| `who_can_see` | 谁可以看（公开/好友/仅自己） |
| `save_permission` | 保存权限 |
| `hotspot` | 关联热点 |
| `collection` | 合集 |
| `cover_orientation` `cover_file` | 横/竖封面 + 自定义封面 |
| `preview` | 预览模式（绝不真发） |

## 登录（`login_to_douyin`）

扫码登录；有头，二维码展示给用户；登录态写回 account_file。

## 话题与坑

- 富文本话题节点后附加零宽空格(U+200B–200D/FEFF/2060/NBSP)，校验前先去除；话题节点后补一个空格分隔。
- 一次输入完整 `#关键词` 再按空格确认/分隔，避免重复 `##`、换行或把多个话题粘成 `#话题1#话题2`。
- 账号 cookie 文件按 `runtime_home()/cookiesFile/douyin_<account>.json`。
- 其它通用后端/API 见 `docs/hermes-skills/prism-project-layout/SKILL.md` 与 `POST /api/v1/publish/batch`。

## 安全基线

- 抖音 `preview=true` 预览模式跑到「发布」前停，绝不真正发布。
- 禁止在生产使用 `app_new/platforms/douyin_http.py`（纯 HTTP 逆向，仅本地开发）。
- 不提交任何本地数据（cookies、指纹、代理、数据库、日志）到 Git。
