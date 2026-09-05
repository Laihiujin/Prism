# Prism 本地一键部署（命令 + Web UI）

把 Prism 从「一堆手工步骤」压成**一条命令**。哪怕是一台什么都没装的新机器，
只要给它一个终端（cmd / PowerShell / bash），就能把环境补齐、把整套服务跑起来，
并打开一个**部署 Web UI** 来驱动与监控。**不需要预装 Python / Node / Redis**——
入口会自己把缺的运行时补齐。

## 一条命令（零前置）

| 平台 | 入口 | 效果 |
|---|---|---|
| macOS / Linux | `./deploy.sh` | 一键部署 + 打开部署 Web UI（`http://127.0.0.1:8440`） |
| Windows | `deploy.cmd` | 一键部署 + 打开部署 Web UI |

日常管理（同为零前置，**子命令**，不带参数 = 完整部署）：

```bash
./deploy.sh            # 完整部署（缺什么补什么 + PM2 启动整套）
./deploy.sh start      # 环境就绪时快速启动（跳过浏览器）
./deploy.sh stop       # 停止（pm2 delete all，保留数据）
./deploy.sh status     # PM2 进程状态
./deploy.sh webui      # 打开部署 Web UI
./deploy.sh check      # 只探测环境，不改动
```

Windows 上把 `./deploy.sh` 换成 `deploy.cmd` 即可（如 `deploy.cmd start`）。

> 已经装了 Python 的话也能用快捷形式 `python3 bootstrap.py`（同上子命令）——
> 这只是捷径，不是前置；没装 Python 时直接跑 `./deploy.sh` / `deploy.cmd` 即可。
> 引擎级无界面一键部署：`python3 deploy/deploy.py full`。

## Web UI 能干的事

- **一键部署**：一个按钮跑完整条链路（探测→补齐工具→引导运行时→启动→健康检查），日志实时流到面板。
- **分步操作**：`探测` / `补齐工具` / `引导运行时` / `启动` / `停止`，可单独点。
- **状态看板**：所有端点存活（前端 3000 / 后端 7000 / Worker 7001 / Persona 8787 /
  Hermes 9119,9131 / DeepSeek 3080 / 代理 7771）+ PM2 进程表。
- 同一时间只允许一个动作在跑，防止并发互相踩。

## 它是怎么做到「新机器也能部署」的

`deploy/deploy.py`（纯标准库，无第三方依赖，为「机器上还没有 Python」而设计）：

1. **Python**：没有系统 Python → macOS/Linux 用内嵌 `micromamba` 自给运行环境；
   Windows → `deploy.ps1` 自动下载一份便携 CPython 到 `.tools\python`。
2. **Node / npm**：没有 → 从 nodejs.org 解析最新 LTS 官方包，下载到 `.tools/node`。
3. **Redis**：Windows → 下载 tporadowski 便携包到 `.tools\redis`；
   macOS/Linux → 检测到未运行就尝试拉起（brew/apt 由用户视需要装）。
4. **Prism 运行时**：优先复用已有 `prismenv`；否则 `provision.py --all` 用 micromamba 供给。

每一步都**幂等**（已就绪就跳过），所以随时可以重跑。

## 常用 CLI 子命令

```
python3 deploy/deploy.py plan            # 只探测 + 打印计划（不改动）
python3 deploy/deploy.py status          # 进程 + 端点快照
python3 deploy/deploy.py install-tools   # 补齐缺失的 Node/Redis/便携 Python
python3 deploy/deploy.py bootstrap       # 引导 Prism 运行时（需已 install-tools）
python3 deploy/deploy.py start           # PM2 启动整套
python3 deploy/deploy.py stop            # 停止整套
python3 deploy/deploy.py full            # 一键（上面全流程）
python3 deploy/deploy.py plan --json     # 机器可读输出
```

## 目录

```
deploy/
  deploy.py          核心编排器（plan/install-tools/bootstrap/start/stop/status/full/webui）
  webui_server.py    部署 Web UI（纯标准库 HTTP + SSE 日志流）
  webui/index.html   面板页面
deploy.sh            macOS/Linux 入口
deploy.cmd           Windows 入口（转发到 deploy.ps1）
deploy.ps1           Windows PowerShell 引导器（含便携 Python 自给）
```

## 安全

- Web UI 默认仅绑定 `127.0.0.1`，只在本机可访问；它可启停进程，**勿改绑定到 0.0.0.0**。
- 部署只在仓库根目录与本机运行，不写系统全局（except 用户显式 `brew/apt` 装 Redis）。

## 已知边界

- 未内置 Windows 的 `micromamba`（仓库内嵌的是 macOS 二进制）；Windows 走
  `deploy.ps1` 的便携 CPython + tporadowski Redis 路径。
- macOS/Linux 的 Redis 仍要求 `brew/apt` 或由你放入 PATH（脚本只检测/启动，不自动装系统包）。
- 门户/账号登录（抖音/小红书等）首次仍需要浏览器扫码,部署本身不涉及。
