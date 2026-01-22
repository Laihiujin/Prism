# SynapseAutomation（AI 矩阵投放 / 自动化发布）
SynapseAutomation 是一个 AI 驱动的多平台矩阵投放与自动化发布系统;
面向多账号、多素材、多平台的内容分发场景，提供从计划生成、任务调度到执行监控与数据回收的全链路能力；

---

## 目录
- [项目定位](#项目定位)
- [核心能力（矩阵投放闭环）](#核心能力矩阵投放闭环)
- [功能截图](#功能截图)
- [支持平台](#支持平台)
- [架构概览](#架构概览)
- [部署开始](#部署开始])
- [矩阵投放流程（SOP）](#矩阵投放流程sop)
- [API 示例](#api-示例)
- [目录结构](#目录结构)
- [合规提示](#合规提示)
- [项目支持与采用](#项目支持与采用)
- [许可](#许可)

---

## 项目定位

SynapseAutomation 是一个“矩阵投放 / 分发中台”，把「账号、素材、计划、排期、执行、监控、回收」统一到可编排的任务系统中：
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
- 内置 OpenManus Agent AI 助手；
- 自然语言生成/润色标题、标签、话题等投放配置；
- 支持“一句话投放”（示例见下）；

### 可扩展 / 可自托管
- FastAPI + Next.js + Celery/Redis + Playwright；
- 平台适配器模块化扩展；
- Web 控制台 + Electron 桌面端，可本地或私有化部署；

---

## 功能截图

### 1) 账号管理——登录账号
支持平台「抖音、快手、小红书、视频号、B 站」；扫码后无需频繁点击，账号自动入库并持续维护；

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

规划可扩展：TikTok（如需国际化平台可按适配器扩展）；

---

## 架构概览

技术栈：FastAPI、Next.js、Celery/Redis、Playwright、Electron；

```text
syn_frontend_react/    # Next.js 控制台（计划/任务/看板）
syn_backend/           # FastAPI 后端（矩阵调度 + AI 服务）
scripts/               # 启动与运维脚本
desktop-electron/      # Electron 客户端与打包
```

---

## 部署开始

### 1) 安装依赖

方式 A：Python venv
```powershell
python -m venv synenv
synenv\Scripts\activate
pip install -r requirements.txt

cd syn_frontend_react
npm install
```

方式 B：conda
```powershell
conda create -n syn python=3.11.4
conda activate syn

pip install -r requirements.txt
cd syn_frontend_react
npm install
```

### 2) 配置环境

编辑根目录 `.env`（端口、Redis、浏览器路径等）；

浏览器依赖（Playwright）：
```powershell
# venv
browsers\install_playwright.bat
# conda
scripts\launchers\setup_browser.bat
```

### 3) 启动服务

使用 venv：
```powershell
start_all_services_synenv.bat
```

使用 conda：
```powershell
start_all_services.bat
```

### 4) 访问

- 控制台：http://localhost:3000
- 后端 API：http://localhost:7000/api/docs

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

- `syn_backend/fastapi_app`：API、矩阵调度、任务队列与服务逻辑；
- `syn_frontend_react/`：矩阵投放控制台（Next.js）；
- `desktop-electron/`：桌面客户端与打包脚本；
- `scripts/`：启动、调试、维护脚本；
---

## 合规提示

本项目用于自动化流程与效率提升，请在合法合规、遵守平台规则的前提下使用；
涉及账号体系与内容发布的规模化运营，建议建立团队内部内容审核与风险控制流程；

---

## 项目支持与采用

本项目在能力建设上受益于开源生态，以下项目提供了启发或参考：
- [social-auto-upload](https://github.com/dreammis/social-auto-upload)
- [Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API)
- [OpenManus](https://github.com/FoundationAgents/OpenManus)

---

## 许可
本项目基于 Apache License 2.0 开源；

## [支持一下](https://buymeacoffee.com/laihiujin3)

| | |
|-|-|
| ![1d1114b7-9c71-4c18-91df-0a462bed5405](https://github.com/user-attachments/assets/f0c38071-f69a-4262-a339-182c090d4c41) | ![dac9dc35-e027-42e8-b6aa-81f3211906da](https://github.com/user-attachments/assets/761ae5f1-8350-49d6-bba6-de2f01f1b73e) |
