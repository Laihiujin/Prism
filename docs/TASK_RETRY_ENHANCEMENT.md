# 任务重试增强 - SQLite记录 + Redis处理

## 改进概述

实现了**方案A：SQLite记录 + Redis处理**架构，解决了任务管理的双重存储问题。

### 核心改进

1. **SQLite 永久保存完整任务数据**
   - 新增 `task_data` 字段（JSON格式）保存完整的任务参数
   - 新增 `priority` 字段保存任务优先级
   - 任务数据永久保存，不会过期

2. **Redis 仅用于临时队列处理**
   - 继续作为 Celery broker 和 result backend
   - 任务状态保留 7 天 TTL（临时状态查询）
   - 不再作为主要的任务历史记录存储

3. **三层任务重试恢复机制**
   - **优先级1**：从 Redis 恢复（完整数据，7天内）
   - **优先级2**：从 SQLite publish_tasks 恢复（完整数据，永久）
   - **优先级3**：从 SQLite task_queue 恢复（备用方案）

---

## 文件修改清单

### 1. 数据库 Schema (`fastapi_app/db/schema.py`)

**变更**：
```python
publish_tasks_required: Dict[str, str] = {
    "celery_task_id": "ALTER TABLE publish_tasks ADD COLUMN celery_task_id TEXT",
    "completed_at": "ALTER TABLE publish_tasks ADD COLUMN completed_at DATETIME",
    "task_data": "ALTER TABLE publish_tasks ADD COLUMN task_data TEXT",  # 新增
    "priority": "ALTER TABLE publish_tasks ADD COLUMN priority INTEGER DEFAULT 5",  # 新增
}
```

**作用**：
- `task_data`：保存完整的任务数据（JSON 格式），包括 platform, account_id, file_id, title, description, tags 等所有字段
- `priority`：保存任务优先级，用于任务重试时保持原有优先级

---

### 2. 任务保存逻辑 (`fastapi_app/tasks/publish_tasks.py`)

**函数**：`CallbackTask._save_to_publish_tasks()`

**变更**：
```python
# 新增：保存完整的 task_data（JSON 格式）
task_data_json = json.dumps(task_data, ensure_ascii=False)

# INSERT 时包含 task_data 和 priority
INSERT INTO publish_tasks (
    celery_task_id, platform, account_id, material_id, title, tags,
    status, error_message, task_data, priority, created_at, updated_at, published_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

**作用**：
- 每次任务完成（成功或失败）时，将完整的 `task_data` 保存到 SQLite
- 确保任务可以从 SQLite 完整恢复，无需依赖 Redis

---

### 3. 任务重试逻辑 (`fastapi_app/api/v1/tasks/router.py`)

#### 3.1 新函数：`_retry_task_from_sqlite()`

**功能**：
- 从 SQLite `publish_tasks` 表恢复任务
- **优先使用** `task_data` 字段（完整数据）
- **向后兼容**：如果 `task_data` 不存在，从 platform/account_id/material_id 等字段重建

**代码逻辑**：
```python
# 1. 查询 SQLite，包含 task_data 字段
SELECT celery_task_id, platform, account_id, material_id,
       title, tags, cover, schedule_time, publish_mode,
       status, error_message, priority, task_data, created_at
FROM publish_tasks
WHERE celery_task_id = ?

# 2. 优先解析完整的 task_data
if task_data_json:
    task_data = json.loads(task_data_json)  # 完整数据
else:
    # 向后兼容：从其他字段重建
    task_data = {
        "platform": platform,
        "account_id": account_id,
        "file_id": material_id,
        "title": title,
        "tags": tags,
        "description": "",  # 缺失
    }

# 3. 重新提交到 Celery
result = publish_single_task.apply_async(
    kwargs={"task_data": task_data},
    priority=priority or 5
)
```

#### 3.2 增强函数：`retry_failed_task()`

**三层重试恢复机制**：
```python
@router.post("/retry/{task_id}")
async def retry_failed_task(task_id: str, request: Request):
    # 方案1: 优先从 Redis 恢复（完整数据，7天内）
    redis_result = _retry_task_from_redis(task_id)
    if redis_result:
        return redis_result

    # 方案2: 从 SQLite publish_tasks 历史恢复（完整数据，永久）
    sqlite_result = _retry_task_from_sqlite(task_id)
    if sqlite_result:
        return sqlite_result

    # 方案3: 从 SQLite task_queue 恢复（备用方案）
    tm = _get_task_manager(request)
    # ... 原有的备用逻辑
```

**日志优化**：
- 使用 `logger` 替代 `print`
- 记录恢复来源（redis/sqlite/task_queue）
- 详细的调试日志

---

## 使用方法

### 1. 数据库迁移

运行应用时，新字段会自动添加到现有的 `publish_tasks` 表：

```bash
# 启动应用，自动执行迁移
python main.py
```

迁移日志示例：
```
[DB] Adding column to table publish_tasks: task_data
[DB] Adding column to table publish_tasks: priority
[DB] Added 2 columns
```

### 2. 任务重试 API

**端点**：`POST /api/v1/tasks/retry/{task_id}`

**请求示例**：
```bash
curl -X POST http://localhost:8000/api/v1/tasks/retry/abc123-def456
```

**响应示例（从 SQLite 恢复）**：
```json
{
  "success": true,
  "message": "Task resubmitted to Celery from SQLite history",
  "new_task_id": "xyz789-uvw012",
  "original_task_id": "abc123-def456",
  "source": "sqlite"
}
```

**响应示例（从 Redis 恢复）**：
```json
{
  "success": true,
  "message": "Task resubmitted to Celery from Redis",
  "new_task_id": "xyz789-uvw012",
  "original_task_id": "abc123-def456",
  "source": "redis"
}
```

**响应示例（向后兼容，字段重建）**：
```json
{
  "success": true,
  "message": "Task resubmitted to Celery from SQLite history",
  "new_task_id": "xyz789-uvw012",
  "original_task_id": "abc123-def456",
  "source": "sqlite",
  "warning": "Task data rebuilt from individual fields (may be incomplete)"
}
```

---

## 架构优势

### ✅ 解决的问题

1. **任务数据永不过期**
   - 之前：Redis 7天过期后无法恢复
   - 现在：SQLite 永久保存完整数据

2. **完整的任务数据**
   - 之前：SQLite 只保存部分字段（platform, account_id, title, tags）
   - 现在：保存完整的 task_data（包括 description, schedule_time 等）

3. **无缝的任务重试**
   - 支持任意时间重试（不受7天限制）
   - 重试数据完整，成功率更高

4. **向后兼容**
   - 自动兼容旧数据（没有 task_data 字段的记录）
   - 不影响现有功能

### 📊 数据流图

```
任务提交
    ↓
[Celery Worker 执行]
    ↓
成功/失败回调 (CallbackTask.on_success / on_failure)
    ↓
┌─────────────────────────────────────────────┐
│ _save_to_publish_tasks()                    │
│  - 保存完整的 task_data (JSON)              │
│  - 保存到 SQLite publish_tasks 表          │
│  - 永久保存，不过期                          │
└─────────────────────────────────────────────┘
    ↓
[任务历史记录]
    ↓
任务重试请求 (POST /api/v1/tasks/retry/{task_id})
    ↓
┌─────────────────────────────────────────────┐
│ 三层重试恢复机制                             │
│ 1. Redis (7天内，完整数据)                  │
│ 2. SQLite publish_tasks (永久，完整数据)    │
│ 3. SQLite task_queue (备用)                │
└─────────────────────────────────────────────┘
    ↓
重新提交到 Celery 队列
    ↓
新任务执行
```

---

## 注意事项

### 1. 数据库升级

- **自动迁移**：启动应用时自动添加新字段
- **安全**：使用 `ALTER TABLE ADD COLUMN`，不会删除数据
- **兼容性**：旧数据仍然可用（向后兼容逻辑）

### 2. 性能考虑

- **SQLite 写入性能**：每个任务完成时写入一次，影响极小
- **JSON 序列化**：使用 `json.dumps(ensure_ascii=False)` 保持中文可读性
- **查询性能**：`celery_task_id` 字段有 UNIQUE 约束，查询速度快

### 3. 存储空间

- **task_data 大小**：通常 <1KB（JSON 格式）
- **预计增长**：每天100个任务 ≈ 100KB/天 ≈ 36MB/年
- **清理策略**（可选）：可以定期归档或删除超过1年的成功任务

---

## 测试建议

### 1. 测试新任务保存

```python
# 提交一个发布任务
POST /api/v1/publish
{
  "platform": 1,
  "account_id": "test_account",
  "file_id": 123,
  "title": "测试视频",
  "description": "这是描述",
  "tags": ["测试", "视频"]
}

# 等待任务完成后，检查 SQLite
SELECT celery_task_id, task_data FROM publish_tasks
WHERE celery_task_id = 'xxx';

# 应该看到完整的 JSON 数据
```

### 2. 测试任务重试（7天内）

```bash
# 任务 ID 在 Redis 中存在
POST /api/v1/tasks/retry/{recent_task_id}

# 应返回 "source": "redis"
```

### 3. 测试任务重试（7天后）

```bash
# 模拟：手动从 Redis 删除任务状态
redis-cli DEL celery:task:{task_id}

# 重试任务
POST /api/v1/tasks/retry/{task_id}

# 应返回 "source": "sqlite"（从 SQLite 恢复）
```

### 4. 测试向后兼容

```bash
# 重试一个旧任务（没有 task_data 字段）
POST /api/v1/tasks/retry/{old_task_id}

# 应返回 "source": "sqlite" 和 warning 提示
```

---

## 未来优化建议（可选）

### 1. 移除 Redis 任务状态持久化（简化架构）

如果完全信任 SQLite 作为唯一的任务历史来源，可以：
- 移除 `TaskStateManager` 的 Redis 持久化逻辑
- Redis 仅用于 Celery broker（任务队列）
- 所有查询都从 SQLite 读取

**优点**：
- 架构更简单
- 无双重存储问题
- SQLite 是唯一的 source of truth

**缺点**：
- SQLite 查询性能略低于 Redis（但对于当前规模足够）
- 实时任务状态查询依赖 SQLite

### 2. 增加任务归档功能

定期将超过 N 天的成功任务移动到归档表：

```python
# 每月执行一次
INSERT INTO publish_tasks_archive
SELECT * FROM publish_tasks
WHERE status = 'success' AND created_at < date('now', '-90 days');

DELETE FROM publish_tasks
WHERE status = 'success' AND created_at < date('now', '-90 days');
```

### 3. 批量任务重试

支持批量重试失败任务：

```python
POST /api/v1/tasks/batch/retry
{
  "task_ids": ["abc", "def", "ghi"],
  "filter": {
    "status": "failed",
    "platform": 1,
    "created_after": "2026-01-01"
  }
}
```

---

## 总结

这次改进实现了：
- ✅ **SQLite 永久保存完整任务数据**（不再依赖 Redis 7天 TTL）
- ✅ **三层任务恢复机制**（Redis → SQLite publish_tasks → SQLite task_queue）
- ✅ **向后兼容**（自动处理旧数据）
- ✅ **详细的日志记录**（便于调试和监控）

现在你可以：
1. 重启应用以应用数据库迁移
2. 测试任务重试功能
3. 验证新任务是否保存了完整的 task_data
