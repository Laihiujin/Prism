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
    <name>/env.yaml           # 隔离组件环境的 micromamba environment.yml
  micromamba/                 # 内嵌 micromamba 二进制（.exe / 无后缀），按平台放置
  .mamba/                     # 自包含 repodata 缓存根（运行时生成）
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

# 实际供给共享运行时（prismenv = conda 环境 + requirements + person/hermes 入口）
python3 scripts/packaging/provision/provision.py --mirror tuna

# 供给全部隔离组件环境（components/<name>/env.yaml）
python3 scripts/packaging/provision/provision.py --all

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

1. 放源码到 `tools/<name>/`（或任意路径）。
2. **注入型**（兼容共享 Python，入口进 `prismenv`）：在 `components.json` 的
   `inject` 加一条 `{"name": ..., "src": "...", "entrypoints": ["<name>"]}`。
   「注入」= 以可编辑方式 `pip install -e <src>`，从而生成 console-script 入口。
3. **隔离型**（需要不同 Python 版本 / 冲突原生依赖）：新建
   `components/<name>/env.yaml`（含 `{{CHANNELS}}` 占位，会被替换成镜像通道），
   并在 `components.json` 的 `isolated` 登记。
4. 运行 `--verify` 确认全绿。

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
这些目前**委托现有 `bootstrap.py` / `scripts/packaging`**：Redis（`which
redis-server`，缺失给安装指引）、浏览器（`patchright install chromium` /
`install_hibbiki_chromium.ps1`）、前端（`npm install` + `next build`）、
mihomo 二进制、`.env`（从 `env.example` 复制）。本模块负责 Python 运行时与入口，
系统依赖步骤建议在 `bootstrap.py` 侧保留或单独成 stage。

## 生产化待办

- 将 `requirements.prism.lock.txt` 换成真正 lockfile（`uv pip freeze` /
  `conda list --explicit`），锁定精确版本消除“依赖坑”。
- `conda-deps.txt` 若取消注释原生包（numpy/opencv/ffmpeg 等），要从
  `requirements.prism.lock.txt` 删除同名项，避免 pip 覆盖 conda 版本。
- 内嵌 `micromamba/` 二进制 + 首次运行供给钩子（安装后进度提示）。
- 弱网/离线兜底：离线 wheels 包，`pip install` 与 conda pkgs 走本地源。
