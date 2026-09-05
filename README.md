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

</div>


## 🟟 产品演示 / Product Demo

**交互演示 / Interaction Walkthrough**

![walkthrough](docs/demos/prism_wrap.gif)


---

**关键词**：抖音自动发布、小红书发布助手、快手、视频号、B站、TikTok 自动化、YouTube 上传、短视频矩阵发布、多账号内容分发、跨平台定时发布、账号身份隔离、浏览器指纹、代理池、AI 智能体、MCP

---


## 功能概览

| 模块 | 已实现 |
|---|---|
| 账号管理 | 抖音/快手/小红书/视频号/B站扫码登录，TikTok/YouTube 本机浏览器登录，可获取用户信息 |
| 身份层 | 集成 Persona Studio 生成相干指纹（OS/UA/GPU/时区/语言一致）； |
| 网络层 | Proxy Manager（健康检测、sticky 绑定、空闲池分配）+ 可选按国 mihomo 网关 |
| 监控 | 任务队列看板、执行日志、账号环境视图（浏览器 × 代理 × 运行时一次返回） |
| 数据回收 | 抖音/B站/tiktok本地采集，视频号/快手/TikTok/YouTube 经 TikHub API |
| AI 编排 | 内置 HermesAgent：自然语言发布指令、标题标签生成、插件/技能/工具箱（`/tools`） |
| 接入 | Web 控制台（Next.js）、Electron 桌面端、`prism` CLI、对外 AI Agent 的 stdio MCP 服务 |

---

## 快速开始

### 零前置：一条命令，什么都不用装，全程只有一条命令。

`deploy.cmd`（Windows）和 `./deploy.sh`（macOS/Linux）是**唯一入口**。
它们**不需要你预装 Python、Node 或 Redis**
PowerShell / shell 会先把缺的运行时自动补齐（Windows 下载便携 Python + Node + Redis；
macOS 用系统自带 python3 或内嵌 micromamba），再交给 `bootstrap.py` 装齐依赖、并用 PM2 拉起整套进程。

| 平台 | 一条命令 | 效果 |
|---|---|---|
| Windows | `deploy.cmd` | 一键部署 + 打开部署 Web UI |
| macOS / Linux | `./deploy.sh` | 一键部署 + 打开部署 Web UI |

日常管理（同样**零前置**，带子命令）：

```bash
./deploy.sh start      # 环境就绪时快速启动（跳过浏览器）
./deploy.sh stop       # 停止（pm2 delete all，保留数据）
./deploy.sh status     # PM2 进程状态
./deploy.sh webui      # 打开部署 Web UI（127.0.0.1:8440）
./deploy.sh check      # 只探测环境，不改动
```

Windows 上把上面的 `./deploy.sh` 换成 `deploy.cmd` 即可（如 `deploy.cmd start`）。

> **给 AI / 任意机器的一条命令**
`deploy.cmd`（Windows）或 `./deploy.sh`（macOS/Linux）。
它能自己搞定 Python/Node/Redis，然后 `bootstrap.py` 装齐依赖、`pm2 start ecosystem.config.js` 拉起整套（自动选后端动态端口、健康检查、失败重试）。

---

## 命令行

`prism` CLI 与 Web 控制台、桌面端共用同一套平台适配器、账号存储和 Patchright 运行时。

```bash
pip install -e .
prism douyin login --account creator
prism douyin check --account creator
prism douyin upload-video --account creator --file ./video.mp4 --title "示例标题" --tags "Prism,自动发布"
prism xiaohongshu upload-video --account creator --file ./video.mp4 --title "示例" --schedule "2026-08-18 20:30"
prism tiktok login --account creator          # 无原生扫码的平台，需真实浏览器登录一次
prism youtube login --account creator
prism accounts            # 列出所有账号（JSON）
prism history             # 发布历史（JSON）
prism mcp                 # 以 MCP stdio 服务方式启动，供外部 AI Agent 接入
```

---

## API

REST API 统一挂在 `/api/v1`，按业务域分组（`accounts`、`matrix`、`publish`、`persona`、`persona_proxy`、`ip_pool`、`analytics`、`tools`、`agent`…）。交互式文档在 `/api/docs`（Swagger）与 `/api/redoc`。

---

## 项目布局

```text
prism_backend/fastapi_app/    30+ 业务域路由 + services/ 业务逻辑 + models/ + tasks/(Celery) + agent/
prism_backend/platforms/      各平台登录/发布/采集适配器
prism_frontend/src/app/       Next.js 路由（dashboard、matrix、accounts、ip-pool、persona、tools、cms）
desktop-electron/             Electron 封装与安装包构建
scripts/                      launchers/、deploy/、maintenance/、ip_pool/、hermes/
deploy/                       本地一键部署引擎 + 部署 Web UI（见 deploy/README.md）
```

---

## 归属及合规

沿用而非重重复造轮子，各自是独立上游、遵循各自许可证（详见 [`NOTICE.txt`](./NOTICE.txt)）：

| 组件 | 上游 | 许可 |
|---|---|---|
| CLI/发布适配器基础 | [social-auto-upload](https://github.com/dreammis/social-auto-upload) | MIT |
| 抖音/TikTok 解析与数据 API | [Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API) | Apache-2.0 |
| 本地 AI Agent 运行时 | [HermesAgent](https://github.com/nousresearch/hermes-agent) | MIT |
| 浏览器身份指纹层 | [Persona Studio](https://github.com/TechQaiser/persona-studio) | MIT |


**合规声明** 
本项目仅在授权/自有账号场景使用，敬请遵守各平台用户协议；
本项目仅限测试、学术研究与技术交流，违反法律法规或平台条款的用途责任自负。

---

## 许可

Apache License 2.0，详见 [`LICENSE`](./LICENSE)。
引入的 MIT/Apache-2.0 上游组件继续适用各自原始许可证，署名要求见 [`NOTICE.txt`](./NOTICE.txt)。

---

## Community

本项目在 [LINUX DO](https://linux.do/) 社区进行交流与开源推广。

感谢 LINUX DO 社区为开发者提供交流与分享的平台。

---

## [BuymeaCoffee](https://buymeacoffee.com/laihiujin3)

| | | |
|-|-|-|
| ![1d1114b7-9c71-4c18-91df-0a462bed5405](https://github.com/user-attachments/assets/f0c38071-f69a-4262-a339-182c090d4c41) | ![dac9dc35-e027-42e8-b6aa-81f3211906da](https://github.com/user-attachments/assets/761ae5f1-8350-49d6-bba6-de2f01f1b73e) | <img width="1284" height="2289" alt="prism" src="https://github.com/user-attachments/assets/3d5234d1-2a85-4eea-8435-5d1642790805" /> |

<div align="right">

</div>
