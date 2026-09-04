# Prism Runtime Self-Provisioning（micromamba 版）

让 Prism 在目标机器上**全权接管自己的 Python runtime**：用内嵌 micromamba
创建 conda 环境（conda-forge + 中国镜像），一次装齐 FastAPI / Celery /
Persona / Patchright 等依赖，并生成 `persona`、`hermes` 这些 console-script
入口，使 `persona-api`、`hermes-dashboard` 能被 PM2 拉起。**不依赖用户机器上
预装的 Python**，且**数据驱动、可扩展**——以后新增开源组件 = 放源码 + 登记一行配置。

仅用标准库实现（供应脚本运行在目标环境存在之前，需自包含）。

## 目录结构

```
scripts/packaging/provision/
  provision.py                # 主供给器
  mirror.json                 # 镜像提供方（tuna / aliyun / official，默认 tuna）
  conda-deps.txt              # conda 层依赖（python=3.11 + 原生包候选）
  requirements.prism.lock.txt # pip 层依赖（当前为 requirements.txt 拷贝；生产应换 lockfile）
  components.json             # 组件清单：inject（装进共享 env） / isolated（独立 env）
  components/
    <name>/env.yaml           # 隔离组件环境的 micromamba environment.yml（persona / hermes …）
  micromamba/                 # 内嵌 micromamba 二进制（.exe / 无后缀），按平台放置
  .mamba/                     # 自包含 repodata 缓存根（运行时生成）
prismenv/                     # 共享运行时环境（仅 Prism 本体 + 被后端 import 的库）
prism_components/<name>/      # 每个隔离组件的独立 conda 环境（运行时生成）
```

## 用法

在仓库根目录（或打包后的 resources 下）执行：

```bash
# 只检查配置，不安装
python3 scripts/packaging/provision/provision.py --check

# 只打印将执行的命令，不安装（含当前 env kind 的决策）
python3 scripts/packaging/provision/provision.py --dry-run

# 完整 runtime 就绪性报告（PM2 健康自检）
python3 scripts/packaging/provision/provision.py --verify

# 实际供给共享运行时（prismenv = conda 环境 + requirements + persona/hermes 入口）
python3 scripts/packaging/provision/provision.py --mirror tuna

# 只跑系统依赖 stage（.env / Redis / 本机浏览器检测 / 前端）
python3 scripts/packaging/provision/provision.py --system

# 只有用户明确要求时才下载 Prism 管理的 Chromium
python3 scripts/packaging/provision/provision.py --system --install-browser chromium

# 供给全部隔离组件环境（components/<name>/env.yaml）
python3 scripts/packaging/provision/provision.py --all

# 一键：共享环境 + 全部隔离组件环境 + 系统依赖 stage（等价于依次 --mirror + --all）
python3 scripts/packaging/provision/provision.py --all --mirror tuna

# 只供给一个隔离组件
python3 scripts/packaging/provision/provision.py --component persona

# 只注入指定组件（不注入其它）
python3 scripts/packaging/provision/provision.py --with persona --with hermes

# 只打印共享环境 python 路径（供壳捕获）
python3 scripts/packaging/provision/provision.py --print-python

# 把已有旧 venv 迁移为 micromamba conda 环境（先备份为 prismenv.venv.bak）
python3 scripts/packaging/provision/provision.py --force
```

## 关键行为

- **环境识别**：目标目录若是旧 venv（`pyvenv.cfg`），默认**不破坏**——仅注入
  组件入口（`bin/persona`、`bin/hermes`），不重建 conda；`--force` 才迁移。
- **幂等**：`<env>/`.prism-provision-ready 记录镜像 + 输入散列，未变则跳过。
- **镜像**：`--mirror tuna|aliyun|official`，或环境变量 `PRISM_PROVISION_MIRROR`;
  pip 层走对应 pypi 镜像。
- **micromamba 解析**：内嵌 `provision/micromamba/` → `PRISM_MICROMAMBA` → `PATH`。
- **入口路径**：Unix = `bin/<ep>`，Windows conda = `Scripts/<ep>.exe`（自动兼容）。

## 新增一个开源组件

判据：**它是独立进程/独立入口，还是被 prism_backend 进程直接 import？**

- **独立进程组件**（persona / hermes / deepseek-harness / 未来的 MCP、插件）→ **isolated**，
  每个组件一个自己的 conda env（`prism_components/<name>`），入口 `bin/<name>`；来了装一套、
  卸载删一套。互不污染共享 `prismenv`。
- **被后端 import 的库 / 内嵌子应用**（`biliup`、`douyin_tiktok_api`）→ **留在 `prismenv`**，
  不隔离（隔离会让后端进程 import 不到）。这类冲突靠 `requirements.prism.lock.txt` 锁版本解决。

新增一个独立进程组件：

1. 放源码到 `tools/<name>/`（或任意路径）。
2. 建 `components/<name>/env.yaml`：只写 conda 层（`python` + `pip`），组件本体由 provision 以
   `pip install -e` 安装。模板见 `components/persona/env.yaml`。
3. 在 `components.json` 的 `isolated` 登记一条：
   `{"name": ..., "src": "tools/<name>", "pip": "tools/<name>", "extras": [...], "entrypoints": ["<name>"]}`。
   - `pip`：组件本体目录（缺省用 `src`）；`extras`：安装时附加的 PEP 508 extras（如 persona 的 `[api,launch]`）。
4. 运行 `python3 scripts/packaging/provision/provision.py --component <name> --mirror tuna` 建环境，
   `--verify` 确认该组件入口为 `[ok]`。卸载 = 删除 `prism_components/<name>/`（留出空间给下一个组件）。

## 运行时清单（供壳 / supervisor 读取）

供给完成后写出 `prismenv/prism-runtime.json`：

```json
{ "manager": "micromamba", "mirror": "tuna", "envDir": "...", "python": ".../bin/python", "component": null }
```

**Electron 壳接入**：`desktop-electron/src/main/index.js` 的 `getPythonRuntime()`
应改为优先读此文件拿真实 python 路径，缺失则先触发一次供给再启动；去掉原
「探测 venv + 运行时拼 PYTHONPATH 注入 site-packages」逻辑，仅在运行时保留
`PYTHONPATH=<后端/tools 源码>`（与 `ecosystem-mac.config.js` 一致）。
注意 conda 入口在 Windows 是 `Scripts/<ep>.exe`，非 `bin/<ep>`。

## 非 Python 运行时（“还有其他的”）

`--verify` 会一并报告 Redis / Chromium / frontend 依赖 / mihomo / `.env`。
这些由 `--system`（或 `--all` 末尾）统一步骤供给：`.env`（从 `env.example`
复制）、Redis（`which redis-server`，缺失给安装指引）、浏览器（默认只检测本机
Chrome/Edge/Firefox 等；显式 `--install-browser chromium` 才下载组件）和前端
依赖及构建。
mihomo 二进制从 `tools/persona-studio/proxies/` 已知路径检测。Python 运行时与
入口由本模块（micromamba）负责；`--system` 是一次性补齐系统/前端依赖的 stage。

## 生产化待办

- 将 `requirements.prism.lock.txt` 换成真正 lockfile（`uv pip freeze` /
  `conda list --explicit`），锁定精确版本消除“依赖坑”。
- `conda-deps.txt` 若取消注释原生包（numpy/opencv/ffmpeg 等），要从
  `requirements.prism.lock.txt` 删除同名项，避免 pip 覆盖 conda 版本。
- 内嵌 `micromamba/` 二进制 + 首次运行供给钩子（安装后进度提示）。
- 弱网/离线兜底：离线 wheels 包，`pip install` 与 conda pkgs 走本地源。
