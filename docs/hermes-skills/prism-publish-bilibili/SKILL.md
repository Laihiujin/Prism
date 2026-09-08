---
name: prism-publish-bilibili
description: "Prism B站发布：多方式登录（扫码/短信/账密/Cookie）、校验、单视频与分P（多P）视频发布、稿件级配置（版权/来源/封面/动态）与 CLI/API/MCP 工具契约。"
version: 1.2.0
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
| 分P（多P）发布 | `publish_multipart_to_bilibili` |
| 图文/笔记发布 | `（B站 不支持图文/笔记发布）` |
| 登录 | `login_to_bilibili`（本地终端）/ `/api/v1/auth/bilibili/*`（短信/账密/Cookie） |
| 校验登录态 | `check_account_bilibili` |

## 视频发布参数（`publish_video_to_bilibili`）

通用：`account_file`（账号 cookie json 路径）、`file_path`（本地视频）、`title`（标题）、
`description`（描述）、`tags`（话题数组）、`schedule`（`YYYY-MM-DD HH:MM`，留空立即发布）、
`thumbnail`（封面）、`headless`（无头/有头）。

B站 专属：

| 参数 | 说明 |
|---|---|
| `tid` | 分区 ID（必填） |
| `tag` | 独立标签（逗号分隔） |
| `copyright` | 1=自制（默认）/ 2=转载（走 python 库） |
| `source` | 转载来源（copyright=2 时建议） |
| `dynamic` | 粉丝动态文案 |
| `cover` | 封面：http URL（CLI）或本地图片路径（库上传，自动 cover_up） |

> 封面传本地路径 / 设置 copyright/source/dynamic 时自动切换 python biliup 库路径；
> 纯 URL 封面 + 默认版权仍走 biliup CLI（历史一致）。

## 分P 发布（`publish_multipart_to_bilibili`）

参数：`account_file`、`title`（稿件主标题）、`tid`（必填）、`files`（数组，顺序 = P1..Pn；
每项 `{path, title?}`，title 缺省 = 主标题 + P序号）、`description`/`tags`/`schedule`/
`copyright`/`source`/`cover`/`dynamic`。走 python biliup 库，一次 submit 整稿；
任一分P失败则不提交（平台不产生残稿）。

## 登录（`login_to_bilibili`）

必须在本机交互终端 `biliup login`；非交互环境返回失败。也可走账号页统一扫码流程
（`/api/v1/auth/qrcode/generate?platform=bilibili&account_id=...`）。短信/账密登录已移除，
B站 脚本发布登录只保留 biliup 终端登录与扫码。

## 风控 / 人工验证码（各平台登录通用）

- 浏览器扫码登录（抖音/快手/小红书/视频号/B站）默认带 `headless=false` 请求
  `/api/v1/auth/qrcode/generate`，会弹出真实浏览器窗口 —— 平台触发风控时
  用户在窗口内手动完成滑块/图形验证即可，前端轮询显示「需要手动验证」横幅
  并**保持会话**（不会 5 分钟超时误杀），完成后自动落库。
- 适配器（`app_new/platforms/*.py`）在 poll 中发现验证码/风控页时返回
  `risk_control` 状态；worker 对 `risk_control` 不清理会话。
- B站短信 `need_recaptcha`：`/sms/send` 返回 `geetest_gt`/`geetest_challenge`，
  前端内嵌 geetest 滑块，通过后自动调 `/sms/recaptcha` 补发验证码，再凭
  `sms_token` 走 `/sms/confirm` 登录（无需手动复制/回填）。
- B站账密 风控（`-105`/`-450`/`-412`）：`/password` 返回 `need_captcha` +
  `geetest_gt/challenge`，前端内嵌极验，滑块通过后以极验值重提 `/password`；
  密码通过但需短信时返回 `need_sms`，走短信链后 `/password/sms-confirm`。
- 前端状态流转：`waiting / scanned / confirmed / expired / failed / risk_control`。

## 话题与坑

- 图文不支持；走独立标签 --tag。走 biliup 命令行（非浏览器自动化）或 python 库。
- 一次输入完整 `#关键词` 再按空格确认/分隔，避免重复 `##`、换行或把多个话题粘成 `#话题1#话题2`。
- 账号 cookie 文件按 `runtime_home()/cookiesFile/bilibili_<account>.json`。
- 定时：B站要求 ≥2h 且 ≤15d；python 库路径同样适用。
- 封面本地图自动裁剪 16:10 后上传（biliup `cover_up`）。
- 其它通用后端/API 见 `docs/hermes-skills/prism-project-layout/SKILL.md` 与 `POST /api/v1/publish/batch`。

## 安全基线

- 抖音 `preview=true` 预览模式跑到「发布」前停，绝不真正发布。
- 禁止在生产使用 `app_new/platforms/douyin_http.py`（纯 HTTP 逆向，仅本地开发）。
- 不提交任何本地数据（cookies、指纹、代理、数据库、日志）到 Git。
