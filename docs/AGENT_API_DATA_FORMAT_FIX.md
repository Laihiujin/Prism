# Agent 工具 API 数据格式不匹配问题修复指南

## 问题概述

Agent 工具（manus_tools.py）中多个工具在调用后端 API 时，期望的返回数据格式与实际 API 返回格式不一致，导致数据解析错误。

## 根本原因

后端 API 有两种返回格式：

### 格式 1：直接返回数据对象（无 Response 包装）
```python
# 路由定义
@router.get("/{file_id}", response_model=FileResponse)
async def get_file(...):
    return file  # 直接返回 FileResponse 对象

# 实际返回的 JSON
{
  "id": 14,
  "filename": "电锯人.mp4",
  "filesize": 10.5,
  "file_path": "...",
  "upload_time": "2024-01-14T10:00:00",
  ...
}
```

### 格式 2：Response 包装（有 data 字段）
```python
# 路由定义
@router.post("/upload", response_model=Response)
async def upload(...):
    return Response(success=True, data={...})

# 实际返回的 JSON
{
  "success": true,
  "message": "操作成功",
  "data": {
    "id": 14,
    ...
  }
}
```

## 需要修复的具体问题

### 🔴 1. GetFileDetailTool (第 1366-1393 行)

**当前代码（错误）：**
```python
response = await client.get(f"{API_BASE_URL}/files/{file_id}")
result = response.json()
file_data = result.get("data", {})  # ❌ 错误：API 直接返回文件数据，没有 "data" 包装

output = f"- 类型: {file_data.get('file_type')}\n"  # ❌ 字段不存在
output += f"- 大小: {file_data.get('size', 0) / 1024 / 1024:.2f} MB\n"  # ❌ 应该用 filesize
output += f"- 上传时间: {file_data.get('created_at', 'N/A')}\n"  # ❌ 应该用 upload_time
```

**修复方案：**
```python
response = await client.get(f"{API_BASE_URL}/files/{file_id}")
file_data = response.json()  # ✅ API 直接返回文件数据

output = f"📄 文件详情：\n\n"
output += f"- ID: {file_data.get('id')}\n"
output += f"- 文件名: {file_data.get('filename')}\n"
output += f"- 路径: {file_data.get('file_path')}\n"
output += f"- 大小: {file_data.get('filesize', 0):.2f} MB\n"  # ✅ 使用 filesize

if file_data.get('duration'):
    output += f"- 时长: {file_data.get('duration'):.2f}秒\n"

output += f"- 状态: {file_data.get('status', 'unknown')}\n"
output += f"- 上传时间: {file_data.get('upload_time', 'N/A')}\n"  # ✅ 使用 upload_time
```

### 🟡 2. ListAssetsTool (第 200-235 行)

**需要确认：** `GET /api/v1/files/` 返回 `FileListResponse`（直接返回），还是 `Response[FileListResponse]`？

**当前代码：**
```python
result = response.json()
files_data = result.get("data", {})  # ⚠️ 可能错误
files = files_data.get("items", []) if isinstance(files_data, dict) else files_data
```

**如果 API 返回 FileListResponse（直接返回）：**
```python
result = response.json()  # {"total": 10, "items": [...]}
files = result.get("items", [])
total = result.get("total", 0)
```

**如果 API 返回 Response[FileListResponse]（有 data 包装）：**
```python
result = response.json()  # {"success": true, "data": {"total": 10, "items": [...]}}
list_data = result.get("data", {})
files = list_data.get("items", [])
total = list_data.get("total", 0)
```

## API 返回格式确认清单

需要确认以下 API 的实际返回格式：

| API 端点 | 当前工具假设 | 需要确认 | 状态 |
|---------|------------|---------|------|
| GET /files/{id} | `{data: {...}}` | ❌ 实际：`{id, filename, ...}` | 🔴 需修复 |
| GET /files/ | `{data: {items: []}}` | ⚠️ 待确认 | 🟡 待检查 |
| POST /publish/batch | `{data: {...}}` | ⚠️ 待确认 | 🟡 待检查 |
| POST /publish/presets | `{data: {...}}` | ⚠️ 待确认 | 🟡 待检查 |
| GET /publish/presets | `{data: [...]}` | ⚠️ 待确认 | 🟡 待检查 |
| GET /tasks/{id} | `{data: {...}}` | ⚠️ 待确认 | 🟡 待检查 |
| GET /tasks/ | `{data: {items: []}}` | ⚠️ 待确认 | 🟡 待检查 |

## 修复步骤

### 步骤 1：修复 GetFileDetailTool
在 [syn_backend/fastapi_app/agent/manus_tools.py:1366-1393](syn_backend/fastapi_app/agent/manus_tools.py#L1366-L1393) 进行修改。

### 步骤 2：测试 API 返回格式
运行以下测试来确认每个 API 的返回格式：

```python
import httpx
import asyncio

async def test_apis():
    base_url = "http://localhost:7000/api/v1"

    async with httpx.AsyncClient() as client:
        # 测试 GET /files/14
        r = await client.get(f"{base_url}/files/14")
        print("GET /files/14:", r.json())

        # 测试 GET /files/
        r = await client.get(f"{base_url}/files/")
        print("GET /files/:", r.json())

        # 测试 GET /accounts
        r = await client.get(f"{base_url}/accounts")
        print("GET /accounts:", r.json())

asyncio.run(test_apis())
```

### 步骤 3：根据测试结果修复其他工具
根据步骤 2 的测试结果，修复 manus_tools.py 中其他工具的数据访问逻辑。

## 相关文件

- [syn_backend/fastapi_app/agent/manus_tools.py](syn_backend/fastapi_app/agent/manus_tools.py) - Agent 工具定义
- [syn_backend/fastapi_app/schemas/file.py](syn_backend/fastapi_app/schemas/file.py) - 文件数据 Schema
- [syn_backend/fastapi_app/schemas/common.py](syn_backend/fastapi_app/schemas/common.py) - 通用响应 Schema
- [syn_backend/fastapi_app/api/v1/files/router.py](syn_backend/fastapi_app/api/v1/files/router.py) - 文件 API 路由
- [syn_backend/fastapi_app/api/v1/files/services.py](syn_backend/fastapi_app/api/v1/files/services.py) - 文件服务层

## 测试验证

修复后，运行以下测试来验证：

1. 调用 `get_file_detail` 工具，确认能正确显示文件信息
2. 调用 `list_assets` 工具，确认能正确列出文件列表
3. 调用其他发布相关工具，确认数据访问正常

## 注意事项

- 不要修改 `manus_tools_social_api.py`，该文件中的 `.get("data")` 用法是正确的（调用的是外部社交媒体 API）
- Response 模型只在明确使用 `response_model=Response` 的路由中才会包装 data 字段
- 直接使用 Pydantic 模型（如 FileResponse）作为 response_model 的路由会直接返回数据对象
