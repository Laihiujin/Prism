# Prism MCP / CLI 契约 / 平台注册表

本页记录三块与「AI 工具 / 智能体接入」相关的能力：

1. **MCP 服务**（`prism mcp`）——暴露给 AI 工具的 4 个动作工具。
2. **CLI 契约**——统一入口 + 语义化退出码 + JSON 输出。
3. **平台注册表**——平台代码→名称→别名→URL→上传器的统一映射。

设计参考 MatrixMedia（`hanliang97/MatrixMedia`）的「外部命令 + argv + 退出码 +
JSON stdout」约定，目标：任何支持 shell 的 AI 编排工具（OpenClaw / Claude Code /
Codex / Dify / n8n / WorkBuddy 等）都能直接接入 Prism，无需业务方耦合。

---

## 1. MCP 服务

这 4 个能力同时登记在**声明式工具注册中心**（`fastapi_app/services/tool_catalog.py`），
因此有三层自动暴露：

| 暴露层 | 入口 |
| --- | --- |
| `prism tool list` / `prism tool invoke` | 命令行 |
| `python -m fastapi_app.agent.mcp_server` | 声明式 MCP（含所有目录工具） |
| `python prism_cli.py mcp` | 专用 MCP 服务（同构 4 工具） |

### 启动（stdio）

```bash
# 项目根目录
python prism_cli.py mcp            # 专用 MCP 服务（4 个工具）
python -m fastapi_app.agent.mcp_server   # 声明式 MCP（68 个工具，含这 4 个）
```

MCP 客户端通过 stdio 拉起上命令即可。后端默认地址 `PRISM_BACKEND_URL`
（默认 `http://127.0.0.1:7000`），发布走 `/api/v1/publish/batch`（Celery +
浏览器模式，不涉及 HTTP 逆向登录）。

### 工具（4 个）

| 工具名                | 说明                            | 关键参数 |
| --------------------- | ------------------------------- | -------- |
| `list_accounts`       | 列出所有平台账号                | `count`  |
| `list_history`        | 查询发布历史（可筛选）          | `platform`/`status`/`limit` |
| `publish_video`       | 按素材批量发布到账号            | `file_ids`/`accounts`/`title`/`platform`/`description`/`topics`/`scheduled_time` |
| `publish_article`     | 图文/文章发布（以素材文件为载体）| `file_ids`/`accounts`/`title`/`content`/`platform`/`scheduled_time` |

返回统一 JSON 信封：`{"ok": bool, "message": str, "data": ...}`。
历史记录中的 `error_message` 会被截断（默认 500 字符），避免返回体积过大。

实现文件：`prism_backend/mcp_server.py`。

---

## 2. CLI 契约

`prism_cli.py` 是统一入口，子命令：

```bash
prism service start|stop|restart|status|logs|list   # 进程管理
prism tool list                                      # 声明式工具注册中心
prism tool invoke <name> --json '<params>'           # 调用某个已声明工具
prism accounts [--count N]                           # 账号列表（JSON）
prism history [--platform N] [--status S] [--limit N] # 发布历史（JSON）
prism mcp                                            # 启动 MCP stdio 服务
prism <platform> login|check|upload-video|upload-note # 平台级操作
```

### 退出码契约

| 码 | 含义 |
| --- | --- |
| `0` | 成功 |
| `1` | 一般异常 |
| `2` | 参数 / 用法错误（argparse、取值校验）|
| `3` | 业务失败（登录失败、上传失败、后端不可达、账号未登录）|

`accounts` / `history` 与 `tool invoke` 均输出 JSON 信封
`{"ok": bool, "message": str, "data": ...}`；平台级操作沿用
`{"success": bool, ...}` 信封。

> `accounts` / `history` 与 MCP 服务、tool 目录都复用 `fastapi_app/services/platform_api.py`
> 这一份 HTTP 客户端，保证三处结果完全一致。

---

## 3. 平台注册表（单一事实来源）

`prism_backend/platforms/registry.py` 是「平台」所有映射的权威来源：

- 平台代码 → 平台名 / 别名 / 登录与发布 URL / 上传实现。
- 任何「平台别名 → 平台代码」或「平台代码 → 上传器」的调用都应从此处获取，
  避免各处散落硬编码（此前 login / uploader / 前端各维护一份编码映射，
  曾导致 6/7 平台显示成裸数字）。

常用函数：

```python
from platforms.registry import (
    normalize_platform_code,  # 别名/代码 -> int（如 normalize_platform_code("tiktok") -> 6）
    get_platform_meta,        # 代码或别名 -> {name, aliases, login_url, publish_url, code}
    list_platforms,           # -> [{code, name, aliases, login_url, publish_url}, ...]
    get_uploader_by_platform_code,  # -> PlatformUploader
)
```

> 生产登录必须走浏览器模式（`platforms/*` + fastapi 登录服务），注册表只负责
> 映射，不负责登录。详见 `prism_backend/AGENTS.md`。
