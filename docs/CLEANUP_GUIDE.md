# 项目文件清理指南

## 🗑️ 可以安全删除的文件

### 1. 日志文件（运行时产生，可重新生成）
```
backend.log
celery-worker.log
playwright-worker.log
dump.rdb                    # Redis 数据库快照
```

**删除命令**：
```batch
del /q *.log
del /q dump.rdb
```

### 2. 临时文件和占位符
```
temp/                       # 临时文件夹
tests/                      # 测试文件夹（如果为空或不需要）
nul                         # Windows 占位符文件
_nul                        # 占位符文件
__init__.py                 # 根目录不需要（如果为空）
```

**删除命令**：
```batch
rd /s /q temp 2>nul
rd /s /q tests 2>nul
del /q nul _nul __init__.py 2>nul
```

### 3. 压缩包（已解压的资源）
```
python-3.11.9-embed-amd64.zip    # Python 嵌入式版本（已解压到 synenv）
```

**删除命令**：
```batch
del /q python-3.11.9-embed-amd64.zip
```

### 4. 诊断和修复脚本（一次性使用）
```
diagnose-supervisor.bat           # 诊断脚本，问题解决后可删除
fix_agent_tools.py               # 修复脚本，已执行完可删除
manual_fix_instructions.py       # 手动修复说明，问题解决后可删除
kill-all-processes.bat           # 紧急清理脚本，保留或删除都可以
```

**建议**：移动到 `scripts/maintenance/` 或 `scripts/archived/`
```batch
mkdir scripts\maintenance 2>nul
move diagnose-supervisor.bat scripts\maintenance\
move fix_agent_tools.py scripts\maintenance\
move manual_fix_instructions.py scripts\maintenance\
```

### 5. 旧的启动脚本（与 scripts/launchers 重复）

根目录下这些脚本与 `scripts/launchers/` 中的脚本功能重复：
```
start_all_services_synenv.bat     → scripts/launchers/start_backend_synenv.bat
start_all_services.bat            → 使用 start_all_with_supervisor.bat
start_celery_worker_synenv.bat    → scripts/launchers/start_celery.bat
start_celery_worker.bat           → scripts/launchers/start_celery.bat
start_supervisor_synenv.bat       → start_all_with_supervisor.bat 更好
```

**建议**：移动到 `scripts/archived/`
```batch
mkdir scripts\archived 2>nul
move start_all_services_synenv.bat scripts\archived\
move start_all_services.bat scripts\archived\
move start_celery_worker_synenv.bat scripts\archived\
move start_celery_worker.bat scripts\archived\
move start_supervisor_synenv.bat scripts\archived\
```

### 6. 文档文件（根据需要保留）

**可以保留的重要文档**：
```
BUILD_PACKAGE_README.md          # 打包说明 - 保留
INNO_SETUP_FIX.md               # Inno Setup 修复说明 - 保留
VERSION_MANAGEMENT.md            # 版本管理 - 保留
SUPERVISOR_AUTO_CLEANUP.md       # Supervisor 清理说明 - 保留
```

**可以删除或归档的文档**：
```
AGENT_API_DATA_FORMAT_FIX.md    # 已修复的问题说明
FIX_SUMMARY.md                  # 修复总结
PATH_FIX_SUMMARY.md             # 路径修复总结
```

**建议**：移动到 `docs/fixes/`
```batch
mkdir docs\fixes 2>nul
move AGENT_API_DATA_FORMAT_FIX.md docs\fixes\
move FIX_SUMMARY.md docs\fixes\
move PATH_FIX_SUMMARY.md docs\fixes\
```

---

## ✅ 必须保留的文件

### 核心构建脚本
```
build-package.bat               # 主打包脚本
build-supervisor.bat            # Supervisor 构建
upgrade-pyinstaller.bat         # PyInstaller 升级
```

### 环境修复脚本
```
fix-synenv-paths.bat            # 修复 synenv 路径
fix-synenv.bat                  # 修复 synenv 环境
rebuild-quick.bat               # 快速重建
clean-dist.bat                  # 清理构建产物
```

### 启动和管理脚本
```
start_all_with_supervisor.bat   # 使用 Supervisor 启动所有服务（推荐）
START_REDIS.bat                 # 启动 Redis
stop_all_services.bat           # 停止所有服务
kill-all-processes.bat          # 紧急停止（可选保留）
```

### 配置文件
```
.env                            # 环境变量（不要删除！）
.gitignore                      # Git 忽略配置
.lintstagedrc.cjs              # 代码检查配置
package.json                    # Node.js 项目配置
requirements.txt                # Python 依赖
ecosystem.config.js             # PM2 配置
build_exclude.txt               # 构建排除列表
```

### 其他
```
index.js                        # 入口文件
deploy.sh                       # 部署脚本
LICENSE.txt                     # 许可证
```

---

## 📁 scripts/launchers 目录清理建议

该目录包含：
```
force_kill_backend.bat          # 强制结束后端
install_playwright.bat          # 安装 Playwright
kill_port_7000.bat             # 结束端口 7000
kill_port_7001.bat             # 结束端口 7001
restart_backend.bat            # 重启后端
setup_browser.bat              # 设置浏览器
start_backend.bat              # 启动后端
start_backend_synenv.bat       # 使用 synenv 启动后端
start_celery.bat               # 启动 Celery
start_frontend.bat             # 启动前端
start_worker.bat               # 启动 Worker
start_worker_synenv.bat        # 使用 synenv 启动 Worker
stop_celery.bat                # 停止 Celery
```

**建议保留**：这些都是有用的脚本，建议全部保留。

**可选优化**：创建子目录分类
```
scripts/launchers/
  ├── services/        # 服务启动脚本
  │   ├── start_backend_synenv.bat
  │   ├── start_frontend.bat
  │   ├── start_celery.bat
  │   └── start_worker_synenv.bat
  ├── maintenance/     # 维护脚本
  │   ├── restart_backend.bat
  │   ├── force_kill_backend.bat
  │   ├── kill_port_7000.bat
  │   └── kill_port_7001.bat
  └── setup/           # 设置脚本
      ├── install_playwright.bat
      └── setup_browser.bat
```

---

## 🚀 推荐的清理脚本

创建一个一键清理脚本：

```batch
@echo off
echo ============================================
echo   SynapseAutomation Cleanup Script
echo ============================================
echo.

:: 1. 删除日志文件
echo [1/5] Cleaning log files...
del /q *.log 2>nul
del /q dump.rdb 2>nul
echo OK: log files cleaned

:: 2. 删除临时文件
echo.
echo [2/5] Cleaning temporary files...
rd /s /q temp 2>nul
del /q nul _nul 2>nul
echo OK: temporary files cleaned

:: 3. 归档修复文档
echo.
echo [3/5] Archiving fix documentation...
mkdir docs\fixes 2>nul
move AGENT_API_DATA_FORMAT_FIX.md docs\fixes\ 2>nul
move FIX_SUMMARY.md docs\fixes\ 2>nul
move PATH_FIX_SUMMARY.md docs\fixes\ 2>nul
echo OK: fix docs archived

:: 4. 归档旧脚本
echo.
echo [4/5] Archiving old scripts...
mkdir scripts\archived 2>nul
move start_all_services_synenv.bat scripts\archived\ 2>nul
move start_all_services.bat scripts\archived\ 2>nul
move start_celery_worker_synenv.bat scripts\archived\ 2>nul
move start_celery_worker.bat scripts\archived\ 2>nul
echo OK: old scripts archived

:: 5. 归档维护脚本
echo.
echo [5/5] Archiving maintenance scripts...
mkdir scripts\maintenance 2>nul
move diagnose-supervisor.bat scripts\maintenance\ 2>nul
move fix_agent_tools.py scripts\maintenance\ 2>nul
move manual_fix_instructions.py scripts\maintenance\ 2>nul
echo OK: maintenance scripts archived

echo.
echo ============================================
echo Cleanup complete!
echo ============================================
pause
```

保存为 `cleanup-project.bat`

---

## 📊 清理后的根目录结构

```
E:\demo_account\SynapseAutomation\
├── .env                              # 环境变量
├── .gitignore                        # Git 配置
├── package.json                      # Node.js 配置
├── requirements.txt                  # Python 依赖
├── index.js                          # 入口文件
├── build-package.bat                 # 打包脚本
├── build-supervisor.bat              # Supervisor 构建
├── start_all_with_supervisor.bat     # 启动所有服务
├── START_REDIS.bat                   # 启动 Redis
├── stop_all_services.bat             # 停止服务
├── clean-dist.bat                    # 清理构建
├── docs/                             # 文档目录
│   ├── BUILD_PACKAGE_README.md
│   ├── INNO_SETUP_FIX.md
│   ├── VERSION_MANAGEMENT.md
│   └── fixes/                        # 归档的修复文档
├── scripts/                          # 脚本目录
│   ├── launchers/                    # 启动脚本
│   ├── maintenance/                  # 维护脚本
│   └── archived/                     # 归档脚本
├── syn_backend/                      # 后端代码
├── syn_frontend_react/               # 前端代码
└── desktop-electron/                 # 桌面应用
```

---

## ⚠️ 注意事项

1. **不要删除 `.env` 文件** - 包含重要的环境变量配置
2. **不要删除 `synenv/` 目录** - Python 虚拟环境
3. **不要删除 `browsers/` 目录** - 浏览器资源
4. **清理前建议先备份** - 以防误删重要文件

---

## 日期
2026-01-15
