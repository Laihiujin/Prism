# OpenClaw 迁移说明

## 当前状态

本次改造将 `OpenClaw` 作为对外公开名称接管主流程：

- 新增后端兼容层：`syn_backend/fastapi_app/agent/openclaw_agent.py`
- 新增 API 路由别名：
  - `/api/v1/agent/openclaw-run`
  - `/api/v1/agent/openclaw-stream`
  - `/api/v1/agent/openclaw-stop`
  - `/api/v1/agent/openclaw-confirm`
- 前端主聊天入口已切到 `openclaw-*` 路由

旧的 `manus-*` 路由仍保留，避免现有页面和历史客户端立即失效。

## 为什么这次不是直接删除 `OpenManus-worker`

当前自定义工具仍直接继承 `OpenManus-worker` 里的 `BaseTool` / `ToolResult`：

- `syn_backend/fastapi_app/agent/manus_tools.py`
- `syn_backend/fastapi_app/agent/manus_tools_extended.py`
- `syn_backend/fastapi_app/agent/manus_tools_social_api.py`

在这些工具彻底改写前，直接删目录会导致：

- Agent 初始化失败
- 工具调用失败
- 流式执行和任务编排失效

## 下一阶段建议

1. 在 `fastapi_app/agent/` 下抽出项目内自己的 `BaseTool`、`ToolResult`。
2. 把 `manus_tools*.py` 改为依赖本地基类，不再 import `OpenManus-worker/app/...`。
3. 将 `manus_agent.py` 重命名/重构为真正的 `openclaw_agent.py` 实现。
4. 最后再删除 `syn_backend/OpenManus-worker` 目录与相关 requirements。
