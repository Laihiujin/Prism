# OpenManus 集成指南

## 概述

OpenManus 已成功集成到 SynapseAutomation 后端，作为 AI Agent 提供强大的自动化能力。

## 主要修复

### 1. 浏览器配置修复 ✅

**问题**：OpenManus 的 `browser_use_tool.py` 硬编码了 `headless=False`，导致无法从配置文件读取设置。

**解决方案**：
- 修改 [browser_use_tool.py:172-176](syn_backend/OpenManus-worker/app/tool/browser_use_tool.py#L172-L176)
- 现在从 `config.toml` 的 `[browser]` 部分读取 `headless` 设置
- 支持使用本地 Chrome 实例路径 (`chrome_instance_path`)

```python
# 修复后的代码
browser_config_kwargs = {
    "headless": config.browser_config.headless if config.browser_config and hasattr(config.browser_config, 'headless') else False,
    "disable_security": True
}
```

### 2. 配置文件同步 ✅

**位置**：`syn_backend/OpenManus-worker/config/config.toml`

**当前配置**：
```toml
[llm]
provider = "custom"
model = "Qwen/Qwen2.5-72B-Instruct"
api_key = "sk-***"
base_url = "https://api.siliconflow.cn/v1"
max_tokens = 16384
temperature = 0.6

[browser]
headless = true
chromium_channel = "chromium"
chrome_instance_path = "E:/SynapseAutomation/browsers/chromium/chromium-1161/chrome-win/chrome.exe"
disable_security = true
```

## 可用工具

### 浏览器自动化工具

#### 1. `browser_use` - 网页浏览器工具
**功能**：
- 导航：访问URL、后退、前进、刷新、网页搜索
- 交互：点击元素、输入文本、选择下拉选项、发送键盘命令
- 滚动：上下滚动、滚动到特定文本
- 内容提取：根据目标提取网页内容
- 标签管理：切换、打开、关闭标签页

**配置**：现在正确使用 `config.toml` 中的浏览器设置。

#### 2. `computer_use` - 桌面自动化工具
**功能**：
- 鼠标控制：移动、点击、拖拽、滚动
- 键盘输入：打字、按键、组合键
- 截图：捕获屏幕图像
- 等待：暂停执行

### SynapseAutomation 业务工具

#### 账号管理
- `list_accounts` - 列出账号
- `call_api` - 通用 API 调用

#### 素材管理
- `list_assets` / `list_files` - 列出素材/文件
- `get_file_detail` - 获取文件详情

#### 发布管理
- `publish_batch_videos` - 批量发布视频（支持多平台差异化）
- `use_preset_to_publish` - 使用预设发布
- `create_publish_preset` - 创建发布预设
- `list_publish_presets` - 列出发布预设

#### 矩阵发布
- `generate_matrix_tasks` - 生成矩阵发布任务
- `get_matrix_status` - 获取矩阵任务状态
- `execute_matrix_task` - 执行矩阵任务
- `execute_all_matrix_tasks` - 批量执行所有矩阵任务

#### 任务管理
- `get_task_status` - 获取任务状态
- `list_tasks_status` - 列出任务状态

#### 数据采集

#### 基础设施
- `ip_pool_manager` - IP 池管理
- `cookie_manager` - Cookie 管理

#### 平台操作
- `platform_login` - 平台账号登录
- `check_login_status` - 检查登录状态

#### 数据分析
- `data_analytics` - 数据分析报告
- `get_dashboard_stats` - Dashboard 统计
- `get_system_context` - 获取系统上下文

#### 系统工具
- `execute_python_script` - 执行 Python 脚本
- `run_backend_script` - 运行后端脚本

### 社交媒体数据API工具

#### 抖音 (Douyin) API
- `douyin_fetch_user_info` - 获取抖音用户信息（支持用户链接或 sec_user_id）
- `douyin_fetch_user_videos` - 获取抖音用户视频列表（支持分页）
- `douyin_fetch_video_detail` - 获取抖音单个视频详情（支持视频链接或 aweme_id）

**使用示例**：
```
获取用户信息: https://www.douyin.com/user/MS4wLjABAAAA...
获取用户视频: 直接使用 sec_user_id 或用户链接
获取视频详情: https://www.douyin.com/video/7372484719365098803
```

#### TikTok (国际版) API
- `tiktok_fetch_user_info` - 获取 TikTok 用户信息（支持用户链接或 unique_id）
- `tiktok_fetch_user_videos` - 获取 TikTok 用户视频列表（支持分页）
- `tiktok_fetch_video_detail` - 获取 TikTok 单个视频详情（支持视频链接或 video_id）

**使用示例**：
```
获取用户信息: https://www.tiktok.com/@username
获取用户视频: @username 或完整链接
获取视频详情: https://www.tiktok.com/@username/video/1234567890123456789
```

**特点**：
- ✅ 无需登录即可获取公开数据
- ✅ 支持直接使用用户/视频链接
- ✅ 返回详细的播放量、点赞、评论、分享等数据
- ✅ 适合竞品分析、内容研究、数据采集场景

## API 端点集成

所有工具通过 `MANUS_API_BASE_URL` 环境变量连接到后端 API：

```python
API_BASE_URL = os.getenv("MANUS_API_BASE_URL", "http://localhost:7000/api/v1")
```

### 主要 API 端点

| 功能 | 端点 | 方法 |
|------|------|------|
| 账号列表 | `/accounts` | GET |
| 素材列表 | `/files` | GET |
| 批量发布 | `/publish/batch` | POST |
| 预设列表 | `/publish/presets` | GET |
| 矩阵任务生成 | `/matrix/generate_tasks` | POST |
| 矩阵任务状态 | `/matrix/stats` | GET |
| 任务状态 | `/tasks/{task_id}` | GET |
| 系统上下文 | `/agent/context` | GET |
| 抖音用户信息 | `/douyin/web/fetch_user_detail` | GET |
| 抖音用户视频 | `/douyin/web/fetch_user_post_videos` | GET |
| 抖音视频详情 | `/douyin/web/fetch_one_video` | GET |
| TikTok用户信息 | `/tiktok/web/fetch_user_detail` | GET |
| TikTok用户视频 | `/tiktok/web/fetch_user_post_videos` | GET |
| TikTok视频详情 | `/tiktok/web/fetch_one_video` | GET |

## 使用方法

### 1. 通过 FastAPI 接口调用

```python
from fastapi_app.agent.manus_agent import get_manus_agent

# 获取 agent 实例
agent = await get_manus_agent()

# 执行任务
result = await agent.run_goal(
    goal="帮我列出所有抖音账号，并发布一个视频",
    context={
        "platform": "douyin",
        "video_id": 123
    }
)
```

### 2. 通过 HTTP API 调用

```bash
POST http://localhost:7000/api/v1/openmanus/run
Content-Type: application/json

{
  "goal": "列出所有账号并生成矩阵发布任务",
  "context": {
    "platforms": ["douyin", "xiaohongshu"]
  }
}
```

### 3. 使用社交媒体 API 工具

**通过 OpenManus Agent 调用**：
```python
# 分析竞品账号
result = await agent.run_goal(
    goal="获取抖音用户 https://www.douyin.com/user/MS4wLjABAAAA... 的最近20个视频数据，分析其内容风格和热门视频特征",
    context={"platform": "douyin"}
)

# 批量采集数据
result = await agent.run_goal(
    goal="获取以下TikTok账号的用户信息和最新视频：@user1, @user2, @user3",
    context={"platform": "tiktok", "count": 10}
)
```

**直接调用 API**：
```bash
# 获取抖音用户信息
GET http://localhost:8001/api/douyin/web/fetch_user_detail?sec_user_id=MS4wLjABAAAA...

# 获取抖音用户视频列表
GET http://localhost:8001/api/douyin/web/fetch_user_post_videos?sec_user_id=MS4wLjABAAAA...&count=20

# 获取单个视频详情
GET http://localhost:8001/api/douyin/web/fetch_one_video?aweme_id=7372484719365098803
```

## 配置管理

### 动态更新配置

OpenManus Agent 会在初始化时：
1. 从数据库读取 AI 模型配置（`service_type='function_calling'`）
2. 自动更新 `config.toml` 文件
3. 重新加载配置并初始化 LLM

### 浏览器路径配置

系统会自动检测并配置浏览器路径：
```python
# 自动查找 Chrome 可执行文件
chrome_dirs = list(chromium_path.glob("chromium-*/chrome-win/chrome.exe"))
if chrome_dirs:
    chrome_exe_path = str(chrome_dirs[0].resolve())
```

## 注意事项

1. **浏览器工具**：
   - 现在正确使用配置文件中的 `headless` 设置
   - 支持本地 Chrome 实例
   - 禁用了安全检查以便自动化操作

2. **API 连接**：
   - 确保后端服务运行在 `localhost:7000`
   - 可通过环境变量 `MANUS_API_BASE_URL` 自定义

3. **工具限制**：
   - 已禁用 `ask_human` 工具（会阻塞 Web 服务）
   - 所有工具都是异步的，适合 FastAPI 环境

4. **错误处理**：
   - 所有工具返回 `ToolResult` 对象
   - 包含 `output`（成功）或 `error`（失败）字段

## 故障排除

### 浏览器无法启动
1. 检查 `chrome_instance_path` 是否正确
2. 确认浏览器文件存在
3. 查看 `headless` 设置是否符合需求

### API 调用失败
1. 确认后端服务正在运行
2. 检查 `MANUS_API_BASE_URL` 配置
3. 查看 API 端点是否正确

### 工具未找到
1. 确认 OpenManus Agent 已初始化
2. 检查工具是否正确添加到 `ToolCollection`
3. 查看日志中的工具列表

## 更新历史

- **2026-01-07**: 修复浏览器配置硬编码问题，现在正确从配置文件读取
- **2026-01-06**: 添加 Computer-use 和 Desktop Electron 配置
- **2026-01-06**: 修复数据中心账号筛选功能

## 相关文件

- [manus_agent.py](syn_backend/fastapi_app/agent/manus_agent.py) - Agent 包装器
- [manus_tools.py](syn_backend/fastapi_app/agent/manus_tools.py) - 基础工具定义
- [manus_tools_extended.py](syn_backend/fastapi_app/agent/manus_tools_extended.py) - 扩展工具
- [browser_use_tool.py](syn_backend/OpenManus-worker/app/tool/browser_use_tool.py) - 浏览器工具
- [computer_use_tool.py](syn_backend/OpenManus-worker/app/tool/computer_use_tool.py) - 桌面工具
- [config.toml](syn_backend/OpenManus-worker/config/config.toml) - OpenManus 配置文件
