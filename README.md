# Prism 棱镜/映射
> 创作一次，映射全平台。

Prism一个 AI 驱动的多平台内容编排与自动化发布系统；
面向多账号、多素材、多平台的内容分发场景，提供从计划生成、任务调度到执行监控与数据回收的全链路能力；

---

## 目录
- [项目定位](#项目定位)
- [核心能力（矩阵投放闭环）](#核心能力矩阵投放闭环)
- [功能截图](#功能截图)
- [支持平台](#支持平台)
- [架构概览](#架构概览)
- [部署开始](#部署开始)
- [命令行](#命令行)
- [矩阵投放流程（SOP）](#矩阵投放流程sop)
- [API 示例](#api-示例)
- [目录结构](#目录结构)
- [合规提示](#合规提示)
- [项目支持与采用](#项目支持与采用)
- [许可](#许可)

---

## 项目定位

Prism 是一个“矩阵投放 / 分发中台”，把「账号、素材、计划、排期、执行、监控、回收」统一到可编排的任务系统中：
- 适合多平台、多账号的规模化分发与运营底座；
- 不强行覆盖剪辑/混剪/内容工厂，可作为外部生产链路的对接层；
- 设计参考行业常见“编-投-管-回”闭环，但项目更聚焦于“投 + 管 + 回”；

---

## 核心能力（矩阵投放闭环）

### 投：矩阵发布与调度
- 多平台、多账号、多素材组合发布；
- 批量生成任务、统一入队、并发调度；
- 定时发布、结果回传、失败重试；

### 管：账号与任务运营
- 账号绑定、状态监控、异常提醒；
- 任务队列看板、执行日志可视化；

### 回：数据回收（复盘输入）
- 当前支持：抖音、B 站；
- 预留可扩展：快手、小红书、视频号等（按平台适配器扩展）；

### 编：AI 编排加速（投前准备）
- 内置 HermesAgent AI 助手；
- 自然语言生成/润色标题、标签、话题等投放配置；
- 支持“一句话投放”（示例见下）；

### 可扩展 / 可自托管
- FastAPI + Next.js + Celery/Redis + Patchright；
- 平台适配器模块化扩展；
- Web 控制台 + Electron 桌面端，可本地或私有化部署；

---

## 功能截图

### 1) 账号管理——登录账号
支持平台「抖音、快手、小红书、视频号、B 站、TikTok、YouTube」；扫码或本机浏览器登录后，账号自动入库并持续维护；

![login](https://github.com/user-attachments/assets/98d0025d-e706-4edc-8233-3bf5bcb33257)

### 2) 素材管理——AI 标题/标签润色 + 批量上传
支持 AI 自动补全标题、标签，支持批量拖拽上传；

![upload](https://github.com/user-attachments/assets/bb406b66-a8ff-4099-8f80-2f667f4627ee)

### 3) 多平台多账号同步发布
支持「抖音、快手、小红书、视频号、B 站」同步发布；支持 AI 一句话发布：
“帮我把素材库刚上传的视频，生成标题、标签并定时发布 23:55，发布到五个平台；”

![publish](https://github.com/user-attachments/assets/658c874a-0518-4ab7-a815-ed3d63363a2a)

### 4) 访问不同平台/账号的创作者后台

![creator](https://github.com/user-attachments/assets/0e8bf623-478f-4ef3-978d-74946962635d)

### 5) 视频数据回收与复盘
当前支持：抖音、B 站（可扩展快手、小红书、视频号）；

![Data](https://github.com/user-attachments/assets/a5635b75-a4ae-4698-b0ae-aaa2aebd6da6)

---

## 支持平台

内置平台适配器（可扩展）：
- 抖音
- 快手
- 小红书
- 视频号
- B 站
- TikTok（本机浏览器登录）
- YouTube（本机浏览器登录）

### 登录运行时状态

- 抖音、快手、小红书、视频号、B 站：当前正式登录路径为本机浏览器 / Patchright 登录态复用。
- 抖音纯 HTTP 二维码登录：实验分支已完成二维码创建与扫码状态轮询；扫码确认换取登录态仍依赖平台设备证明，当前不作为正式功能或发布链路使用。
- TikTok、YouTube：本机浏览器登录后保存 storage state，供任务队列复用。

---

## 命令行

安装项目后可以直接使用 `prism` 命令。CLI 与 Web、桌面端共用同一套平台适配器、账号文件和 Patchright 运行时：

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
```

定时发布使用本地时间，格式为 `YYYY-MM-DD HH:MM`：

```bash
prism xiaohongshu upload-video \
  --account creator \
  --file ./video.mp4 \
  --title "示例标题" \
  --schedule "2026-08-18 20:30"
```

国际平台首次使用需在运行 Prism 的本机浏览器中完成账号登录；登录态会以 storage state 保存并供任务队列复用：

```bash
prism tiktok login --account creator
prism youtube login --account creator
prism youtube upload-video --account creator --file ./video.mp4 --title "Example" \
  --description "Video description" --tags "Prism,automation" --visibility unlisted
```

### Gemini Computer Use 受控恢复（可选）

Gemini Computer Use 仅用于在 Patchright 定位失败时收集截图与候选动作，辅助生成可审查的平台适配器代码补丁；
它不在正式发布任务中执行点击、填写或提交。正式发布始终使用版本化、可测试的 Patchright 平台适配器。

---

## 架构概览

技术栈：FastAPI、Next.js、Celery/Redis、Patchright、Electron；

```text
prism_frontend/    # Next.js 控制台（计划/任务/看板）
prism_backend/           # FastAPI 后端（矩阵调度 + AI 服务）
scripts/               # 启动与运维脚本
desktop-electron/      # Electron 客户端与打包
```

---

## 部署开始

采用本地部署：适合开发、调试，可单独查看 Redis / Celery / Automation Worker / FastAPI / HermesAgent 的运行状态。

### 1) 本地部署

#### 1.1 安装依赖

方式 A：`prismenv`（默认推荐）

```powershell
python -m venv prismenv
prismenv\Scripts\activate
pip install -r requirements.txt

cd prism_frontend
npm install
cd ..
```

也可以直接运行 `start.bat`。它会优先检测 `prismenv`，不存在时自动创建并安装根 `requirements.txt`。

方式 B：`conda`

```powershell
conda create -n prism python=3.11.4
conda activate prism

pip install -r requirements.txt
cd prism_frontend
npm install
cd ..
```

#### 1.2 配置环境

必须检查两类配置：

- 根目录 `.env`：端口、Redis、浏览器路径、前后端连接地址。
- `prism_backend\config\hermes_agent.toml`：HermesAgent 的 provider / model / api_key / base_url。

浏览器依赖：

```powershell
scripts\launchers\setup_browser.bat
```

桌面版支持在“系统设置”页管理 `Chromium` / `Firefox`；所有平台自动化统一由 `Patchright` 执行。

#### 1.3 启动方式

方式 A：一键拉起完整本地栈

```powershell
start.bat
```

等价于默认 `prismenv` 模式，会按顺序启动：

1. Redis
2. Celery Worker
3. Automation Worker
4. FastAPI Backend
5. Frontend

重要说明：

- 本地后端进程缺一不可。少起任意一个进程，前端页面可能能打开，但任务调度、浏览器执行、异步回调、HermesAgent 调用链都会不完整。
- HermesAgent Dashboard / WebUI 由 FastAPI 在非 Supervisor 模式下自动托管；前提是 `prism_backend\config\hermes_agent.toml` 已正确配置，且本地 Hermes 运行时已通过 `scripts\hermes\setup-local-hermes.ps1` 安装完成。

方式 B：Supervisor 模式

```powershell
start.bat supervisor
```

该模式会启动：

- Redis
- Supervisor
- Frontend

再由 Supervisor 托管：

- FastAPI Backend
- Celery Worker
- Automation Worker
- HermesAgent 相关界面与网关

方式 C：手动逐个进程启动（仅调试时使用）

```powershell
scripts\launchers\start_redis.bat
scripts\launchers\start_celery_prismenv.bat
scripts\launchers\start_worker_prismenv.bat
scripts\launchers\start_backend_prismenv.bat
scripts\launchers\start_frontend.bat
```

#### 1.4 本地访问地址

- 控制台：http://localhost:3000
- 后端 API：http://localhost:7000/api/docs
- Automation Worker：http://localhost:7001
- Supervisor API：http://localhost:7002（仅 `start.bat supervisor`）
- HermesAgent Dashboard：http://localhost:9119
- HermesAgent WebUI：http://localhost:9131

---

## 矩阵投放流程（SOP）

1. 绑定账号（多平台账号矩阵）；
2. 素材入库（批量上传 / AI 标题标签润色）；
3. 创建矩阵计划（平台、账号、素材、话题、封面、定时策略）；
4. 生成矩阵任务并调度执行（队列化、并发、失败重试）；
5. 看板监控与日志审计（异常提醒 / 人工介入点）；
6. 数据回收（抖音、B 站）并复盘迭代；

---

## API 示例

生成矩阵任务：

```http
POST /api/v1/matrix/generate_tasks
Content-Type: application/json
```

```json
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

---

## 目录结构

- `prism_backend/fastapi_app`：API、矩阵调度、任务队列与服务逻辑；
- `prism_frontend/`：矩阵投放控制台（Next.js）；
- `desktop-electron/`：桌面客户端与打包脚本；
- `scripts/`：启动、调试、维护脚本；
- `scripts/tests/`：手动与集成验证脚本（原 `Test/` 目录已收纳至此）；
---

## 合规提示

本项目用于自动化流程与效率提升，请在合法合规、遵守平台规则的前提下使用；
涉及账号体系与内容发布的规模化运营，建议建立团队内部内容审核与风险控制流程；

---

## 项目支持与采用

Prism 的能力建设受益于开源生态；下列项目的代码、架构或实现思路被采用、移植或作为实现参考：

- [social-auto-upload](https://github.com/dreammis/social-auto-upload)：上游 CLI 自动发布基础；MIT License。
- [Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API)：抖音 / TikTok 解析与数据能力参考；Apache License 2.0。
- [HermesAgent](https://github.com/nousresearch/hermes-agent)：本地 AI Agent 运行时与集成参考；MIT License。

对应第三方归属和许可证说明保留在 [NOTICE.txt](NOTICE.txt)。

---

## 许可
Prism 自身代码基于 Apache License 2.0 开源。项目中保留的 MIT 与 Apache-2.0 上游组件继续分别适用其原始许可证；Apache-2.0 与 MIT 组件可共同分发，但必须保留上游版权、许可证和 NOTICE 归属。

## [BuymeaCoffee](https://buymeacoffee.com/laihiujin3)

| | | |
|-|-|-|
| ![1d1114b7-9c71-4c18-91df-0a462bed5405](https://github.com/user-attachments/assets/f0c38071-f69a-4262-a339-182c090d4c41) | ![dac9dc35-e027-42e8-b6aa-81f3211906da](https://github.com/user-attachments/assets/761ae5f1-8350-49d6-bba6-de2f01f1b73e) | <img width="1284" height="2283" alt="prism" src="https://github.com/user-attachments/assets/752d43a3-093a-4361-a2ee-4fc24c8789c3" /> |
