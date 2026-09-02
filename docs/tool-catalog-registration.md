# 声明式工具注册中心（Tool Catalog）—— 把能力暴露为 MCP/API/CLI

Prism 的能力要暴露给 **Prism MCP / Hermes MCP**（`tools/list` + `tools/call`）、
**HTTP API**、**CLI**，不需要各写一份。只需在**单一事实源**里登记一条
`ToolSpec`，**三层自动覆盖**。

```text
你的能力（handler 函数）
        │  登记一条 ToolSpec
        ▼
prism_backend/fastapi_app/services/tool_catalog.py   ← 唯一要手改的文件
        │  自动生成，全部只读
        ├─► agent/mcp_server.py         —— MCP tools/list + tools/call  （Prism & Hermes MCP）
        ├─► api/v1/tool_catalog/router.py —— GET/POST /api/v1/tool-catalog/<name>
        ├─► prism_cli.py                 —— prism tool list / prism tool invoke <name>
        └─► prism_frontend/app/tools/page.tsx —— 开发者工具页「业务工具」Tab（调 /api/v1/tool-catalog）
```

---

## 一、自动遍历（@prism_tool 标记，推荐）

给任意被扫描目录（`uploader/`、`utils/`、`automation/`、`services/`）里的函数加一个
`@prism_tool` 装饰器，扫描器会**自动遍历代码库**发现它，生成 `ToolSpec` 并暴露到四层，
完全不用手写登记：

```python
from fastapi_app.services.tool_catalog import prism_tool

@prism_tool(description="两个整数相加", category="demo")
def add(a: int, b: int = 1) -> dict:
    """把两个整数相加。

    :param a: 第一个数
    :param b: 第二个数
    """
    return {"sum": a + b}
```

扫描器（`services/tool_auto_scanner.py`）用 **AST 静态分析**，不 import 被扫描模块，
因此不触发重依赖/副作用；只暴露**被 `@prism_tool` 标记**的函数，不会误伤内部 helper。
`name` 缺省用函数名；`description`/`parameters` 缺省时从 docstring 与函数签名自动推导。

> 最短路径：写个函数 + 加 `@prism_tool`，四层（MCP / API / CLI / 前端）自动全部出现。

---

## 二、声明式登记（自己写一条 ToolSpec）

当能力需要更精细的 `parameters`/`output_summary` 控制时，可直接在 catalog 里手写登记。

以登记一个 `douyin_upload` 为例。

### 1. 写 handler（也可复用已有函数）

放在 `tool_catalog.py` 的 handler 区，或用函数内延迟 import 引用别处能力：

```python
async def _douyin_upload_handler(**kwargs) -> dict:
    """真正干活的逻辑——可以是已有模块的函数，也可以是新写的一段。"""
    from uploader.douyin_uploader.main_refactored import DouYinVideo   # 延迟 import，避免顶层拉重依赖
    app = DouYinVideo(...)
    await app.main()
    return {"success": True, "data": kwargs.get("file_path")}
```

> 约定：`handler` 接收 `**kwargs`（与 `parameters` 对齐），返回 `dict`。
> async / sync 均可；抛异常会被 `invoke` 兜成 `{"error": "..."}`，MCP/API/CLI 统一呈现。

### 2. 登记一条 `ToolSpec`

在 `tool_catalog.py` 底部 `TOOLS` 区调用 `_register(...)`：

```python
_register(ToolSpec(
    name="douyin_upload",               # 唯一小写下划线（MCP 工具名 / CLI 子命令 / API 路径共用）
    description="上传一个视频到抖音（真实发布）。",   # 会出现在 MCP / CLI help / API 描述
    parameters={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "本地视频绝对路径"},
            "title": {"type": "string", "description": "标题", "default": ""},
            "headless": {"type": "boolean", "description": "无头", "default": True},
        },
        "required": ["file_path"],
    },
    handler=_douyin_upload_handler,
    category="douyin",                  # 可选分组
    output_summary="发布后返回 success+视频路径",
))
```

### 3. 好了 —— 三层已自动暴露，无需再改任何其他文件

- MCP：`python -m fastapi_app.agent.mcp_server` 的 `tools/list` 会包含 `douyin_upload`
- API：`GET /api/v1/tool-catalog` 列出；`POST /api/v1/tool-catalog/douyin_upload` 调用
- CLI：`prism tool list`；`prism tool invoke douyin_upload --json '{"file_path":"/a.mp4"}'`

---

## 三、三个入口怎么用

### MCP（Prism & Hermes 共用）
```bash
python -m fastapi_app.agent.mcp_server     # stdio，已注册进 tools/hermes-home/config.yaml
```
- `tools/list` → 返回所有登记工具的 `name/description/inputSchema`
- `tools/call` → `{"name":"<tool>","arguments":{...}}`

### API
```
GET  /api/v1/tool-catalog                   所有工具清单
GET  /api/v1/tool-catalog/{name}            单工具详情（含 parameters）
POST /api/v1/tool-catalog/{name}            body 即 kwargs
```

### CLI
```bash
prism tool list
prism tool invoke <name> --json '{"k":"v"}'
```

### 前端（开发者工具页「业务工具」Tab）
`prism_frontend/src/app/tools/page.tsx` 的「业务工具」Tab（`app/tools/catalog-tools.tsx`）
调 `/api/v1/tool-catalog` 列出工具；点卡片「参数」展开动态表单（由 `parameters.properties` 生成），
点「调用」即 `POST /api/v1/tool-catalog/<name>` 执行真实后端能力。登记一个 `ToolSpec` 后无需改前端。

---

## 四、硬性约定（违反会导致工具不出现或调用失败）

1. **`name` 必须唯一**，且小写下划线；重复登记会抛 `ValueError`。
2. **`parameters` 必须合法 JSON Schema**：`{"type":"object","properties":{...},"required":[...]}`。
   会被 MCP 的 `inputSchema`、API 的 body、CLI 的 JSON 传参共用，缺 `properties` 时工具无法取参。
3. **`handler` 返回 dict**（MCP 需 `json.dumps` 序列化）；非 dict 会退化为 `{"output": <value>}`。
4. **重依赖用函数内延迟 import**（如 `from uploader...`）。顶层 import 会拖慢 MCP/API/CLI 启动，
   甚至让 `prism tool list` 因为缺依赖而失败。
5. **不要在 `tool_catalog.py` 顶层 `import fastapi`/`uploader`**；只 import 标准库。

---

## 五、与既有 `BaseTool`（hermes_tools*.py）的关系

`agent/mcp_server.py` 的 `_collect_tools()` 目前收集两类：
- **手写 `BaseTool` 子类**（`hermes_tools*.py` / `tikhub_tools.py`，逐个 `class` 定义）
- **声明式 `tool_catalog`**（本文件，动态包装成 BaseTool）

两者名字冲突时**手写者优先**（`first module wins`），catalog 同名的会被跳过。
所以要用 catalog 覆盖某个手写工具，请改名或删掉手写的那个。

新能力**优先用 catalog 登记**（改一行即可全暴露）；只有需要复杂内部逻辑/状态时才手写 `BaseTool`。
