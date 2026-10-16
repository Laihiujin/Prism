# Prism runtime

## 首次启动与桌面构建

Windows 双击根目录 `start.bat`，macOS 执行 `./start-mac.sh`。
启动器会补齐 Node、micromamba、Python、Redis、Hermes、Persona、Chromium。
启动日志在 `logs/startup.log` 和 `logs/startup-error.log`，完整安装日志在运行数据目录的 `installation.log`。

安装包不含虚拟环境；Electron 首次启动在用户数据目录的 `runtime/` 创建环境。
源码使用 `runtime-data/envs/shared`，已有 micromamba `prismenv` 可继续使用。
`PRISM_ENV_DIR`、`PRISM_COMPONENT_ENV_DIR`、`PRISM_HERMES_PYTHON` 指向实际解释器，
`runtime-manifest.json` 记录共享环境位置。组件按 pyproject.toml 的 requires-python
并优先采用其 `.python-version`，选择 3.11/3.12/3.13/3.14，独立安装，不升级后端解释器。

下载依次尝试国内镜像、官方源；GitHub 源码使用固定 commit 的 codeload、archive、API 链路。
可通过 `PRISM_GITHUB_MIRRORS` 配置经自己审核的镜像前缀（`|` 分隔），
`PRISM_MAMBA_DOWNLOAD_URLS` 配置 micromamba 镜像（`{target}` 表示平台）。
保留 TLS 验证；Windows Redis 和 Node 校验 SHA256。镜像无法保证所有网络都可访问，
全部失败会停止安装、记录原因，下一次启动重试。

PM2 管理已启用的服务和 prism-recovery。短时间重复重启时先重启一次，
再次失败仅对明确的 Python 依赖错误重装依赖；每小时最多两轮恢复，随后熔断停止。
主动停止的进程不会被自动拉起。恢复动作写入 runtime 数据目录的 recovery-state.json。

在 `desktop-electron/` 执行 `npm run build` 构建当前 OS/CPU 安装包，
`npm run build:dir` 构建可运行目录。构建不会复制 Python 环境、账号、Cookie、日志或数据库。
