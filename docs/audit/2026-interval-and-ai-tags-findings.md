# 功能落实审计：发布间隔控制 & AI 多组标签/话题

- 审计日期：2026-02（工作分支 `feature/prism-update`）
- 范围：`prism_backend`（FastAPI + Celery）与 `prism_frontend`（矩阵发布页 / 素材库）两端到端核查
- 结论速览：

| # | 审计项 | 前端 UI | 请求 Schema / 入参 | 后端计算 | **真正执行延时** | 判定 |
|---|--------|:---:|:---:|:---:|:---:|:---:|
| A | 间隔方式/矩阵节奏/发布间隔控制（发布即间隔） | ✅ | ✅ | ✅（仅算出+打日志） | ❌ **未生效** | **需修复** |
| B | AI 为一个视频生成多组标签/话题的配置后段 | ❌ 无入口 | ❌ 无字段 | ❌ 只生成一组 | ❌ 无存储 | **需补充**（整条缺失） |

---

## A. 发布间隔控制 —— 后端计算了，但从未真正生效（需修复）

### A.1 前端已落实的部分

- `prism_frontend/src/app/publish/matrix/page.tsx`：
  - 「间隔方式 / 矩阵节奏 / 发布间隔控制 / 关闭状态：默认同时发布」UI 完整（L1430-1454）。
  - 两种节奏 `INTERVAL_OPTIONS`：`account_first`（按账号&视频间隔发布）、`video_first`（按视频间隔发布）（L77-105）。
  - 开关 `plan.intervalControlEnabled` → payload `interval_control_enabled`（L813）；关闭时 `interval_mode/interval_seconds` 传 `undefined` → 后端默认同时发布（语义正确）。
- Schema 层：`fastapi_app/schemas/publish.py` `BatchPublishRequest` 有 `interval_control_enabled / interval_mode(account_first|video_first) / interval_seconds(默认300) / random_offset`，并兼容 camelCase 别名（L54-76）。

### A.2 后端"计算"存在

`fastapi_app/api/v1/publish/services.py` `_create_batch_tasks`：

- `video_first`：`base_offset = file_idx * interval_s`（L719）
- `account_first`：`base_offset = account_idx*interval_s + file_idx*interval_s*账号数`（L723）
- 随机偏移：`±random_offset_s`（L732-739）
- 算出绝对时间并写入 `task_data["not_before"] = scheduled_time.isoformat()`（L748-749），日志 `[IntervalControl] Scheduled: ...`。

### A.3 ❌ 断裂点：执行路径从不等待

| 环节 | 现状 | 问题 |
|---|---|---|
| Celery 提交 | `publish_single_task.apply_async(kwargs=..., priority=..., task_id=...)`（L762-766） | **没有 `eta=` / `countdown=`** → 任务立即进入就绪队列 |
| Celery 任务体 | `fastapi_app/tasks/publish_tasks.py::publish_single_task`（L192） | 从不读取 `task_data["not_before"]`；拿到即运行 |
| 旧队列 worker | `myUtils/task_queue_manager.py::worker`（L~375-399）确实会按 `not_before` 重新排队等待 | 但该 manager **从未被 start**：`main.py` L241-245 只 `get_task_manager(...)` 构造供 tasks 只读 API 使用，全仓无任何 `.start()` 调用（`main.py` L275-279 注释已明示"批量发布不再依赖任务队列 / Celery 已加载"） |
| `publish_date` 字段 | `task_data["publish_date"] = timer_config.scheduled_time or 0`（L614）→ 上传器用它做**平台侧定时发布**（douyin upload.py L253-289 定时规则） | 仅当用户在页面填了定时时间才存在；`interval` 场景下未填定时 → `0`，上传器立即发布 |

**结论**：开启「发布间隔控制」提交批量任务后，所有任务实际都会被 Celery **立即并发执行**。偏移计算、`not_before`、日志均为"纸面工作"。只有另外满足两个条件才会出现间隔：① 每个任务都带 `publish_date`（即平台侧定时），且 ② 平台上传器支持定时——这与「发布间隔」是两回事。

### A.4 前端另外两个硬编码

- `matrix/page.tsx` L815：`interval_seconds: plan.intervalControlEnabled ? 300 : undefined` —— **用户没有输入间隔的控件**，写死 300 秒。
- `IntervalTimelinePreview.tsx`：`intervalSeconds=300`、`randomOffset=0` 默认硬编码（页面 L1529 传参），预览与真实提交值可能不一致。

### A.5 修复方案（推荐最小改动）

1. **后端（关键修复）**：在 `services.py` 提交处把已算好的 `not_before` 转成 Celery `eta`：
   ```python
   eta_dt = None
   nb = task_data.get("not_before")
   if nb:
       try:
           eta_dt = datetime.fromisoformat(str(nb).replace("Z", ""))
       except Exception:
           eta_dt = None
   # 若按当前时间已过期则不传 eta（立即执行）
   if eta_dt and eta_dt <= now_beijing_naive():
       eta_dt = None
   result = publish_single_task.apply_async(
       kwargs={'task_data': task_data},
       priority=priority,
       task_id=task_id,
       eta=eta_dt,          # ← 关键：让 Celery 真正延时投递
   )
   ```
   - `celery_app.py` 已是 `timezone="Asia/Shanghai", enable_utc=False`（与 `now_beijing_naive()` 一致），naive datetime 可直接作为 eta。
   - 备选方案二：把 `not_before` 判断下放到 `publish_single_task` 内部（`self.retry(countdown=...)` 或 `self.request.eta`），好处是连"从旧队列/重试接口进 Celery"的任务也统一收敛；推荐在任务体开头加一道兜底（见 A.6）。
2. **前端**：矩阵页「间隔方式」面板内加「间隔时长（秒/分钟）」数字输入，去掉 `300` 硬编码；`IntervalTimelinePreview` 同步接收真实 `intervalSeconds`。
3. **校验**：`interval_control_enabled=true` 但 `interval_seconds` 为空/≤0 时后端应回退为同时发布或报参数错误（当前默认 300 掩盖了"没填"）。

### A.6 兜底建议（防再次断裂）

在 `publish_tasks.py::publish_single_task` 开头加统一调度兜底，使无论从哪条路进 Celery 的任务都尊重 `not_before`：

```python
nb = (task_data or {}).get("not_before")
if nb:
    try:
        s = str(nb).replace("T", " ").replace("Z", "")
        nb_dt = datetime.fromisoformat(s)
    except Exception:
        nb_dt = None
    if nb_dt and nb_dt > now_beijing_naive():
        logger.info(f"[Celery] {task_id} 未到发布时间，countdown 重投: {nb_dt}")
        raise self.retry(countdown=max(int((nb_dt - now_beijing_naive()).total_seconds()), 1))
```

---

## B. AI 为一个视频生成多组标签/话题 —— 后端配置完全缺失（需补充整条链路）

### B.1 现状核查（端到端确认）

**后端**
- 请求：`schemas/file.py::AIMetadataGenerateRequest` 只有 `file_ids / force_regenerate / platform / language` —— **无组数/多组相关字段**（L82-87）。
- 服务：`ai_service/metadata_generation_service.py::_generate_one`（L18-114）—— 生成 **一组** `title+tags`，`apply_platform_limits` 后写入单列；返回 `{ai_title, ai_tags}`。
- 存储：`file_records` 只有 `ai_title / ai_tags / ai_description / ai_generated_at` 单值列（见 files/router.py `update_ai_content` 的 `PRAGMA`/`ALTER TABLE` 逻辑，L~865-905）。**无任何"多组"列/表**。
- Prompt：`title_topic_generator.py::build_metadata_prompt` 只要求输出单个 `title + tags` 对象（L196-199）；`ai_prompts_unified.yaml` 中标题模块虽输出 `best_title + 3 candidates`（L42），但那是**标题候选**，且 `_generate_one` 只取单一 `title`，candidates 被丢弃 —— 更不是"多组标签/话题"。
- 调用链：`files/router.py POST /files/batch-generate-metadata`（L1041）→ `generate_metadata_for_files`。此接口**全前端无人调用**（grep 源码无 `batch-generate-metadata` 调用点），仅 Hermes agent 工具 `hermes_tools.py::generate_ai_metadata`（L319）会打。
- 素材编辑侧的 AI（`matrix/page.tsx` 批量 AI 生成 L420-495、单条 L498+；`MaterialMetadataEditor.handleAIGenerate` L184-203）走的是 `/api/v1/ai/chat`，每次也只回 `{title, tags}` 一组。

**前端**
- 「素材库 / 元数据面板 / AI 生成弹窗」均无「生成组数 / 多组标签」配置入口；发布页 items 只有单一 `title/tags/topics` 语义。
- 数据库/API/Schema/服务/Prompt 全链路搜索 `多组|标签组|话题组|变体|variant` → 无一命中业务实现（仅 tikhub/浏览器候选等无关命中）。

### B.2 结论

「为同一个视频生成多组不同的标签/话题」从 **配置入口 → 入参 → 生成 → 存储 → 发布侧使用** 整条后端链路都不存在，属于全新功能，需**整段补充**而非修复。

### B.3 补充方案（推荐落地路径）

1. **请求参数**（`schemas/file.py`）：
   ```python
   group_count: int = Field(1, ge=1, le=5, description="为每个视频生成的标签/话题组数（每组独立 title+tags）")
   group_tags_only: bool = Field(False, description="True 表示每组仅换标签/话题、标题可复用（默认每组标题也独立生成）")
   ```
2. **Prompt**（`title_topic_generator.py` 新增 `build_metadata_groups_prompt` 或给 `build_metadata_prompt` 加 `group_count`）—— 要求模型输出 N 组差异明显的 `{title?, tags[]}`，每组话题角度不同（泛流量 / 垂直品类 / 细分话题 / 场景人群 等），且每组都过平台上限。
3. **存储**：给 `file_records` 增 `ai_tag_groups TEXT`（JSON 数组 `[{title, tags:[...]}, ...]`）；保留现有 `ai_title/ai_tags` 作为第 1 组/兼容字段（写库时同步第一组），避免破坏现有一切读取方。
   - 或新建 `material_tag_groups(file_id, group_index, title, tags, platform, language)` 表 —— 需要支持"按平台分别存多组"时用表更干净。
4. **响应/读取接口**：`AIMetadataGenerateResponse.results[]` 每项返回 `ai_tag_groups`；`GET /files/{id}/ai-content` 透出该字段。
5. **发布侧消费**（端到端闭环的关键）：发布 `BatchTaskItem` / 每个 task 增加可选的 `tag_group_index`；`services.py` 组 task 时按账号/平台/视频轮转取第 N 组（`account_first`/`video_first` 之外的第 3 种"话题差异化"维度）——否则多组生成结果无处使用。
6. **前端**：
   - 素材库/矩阵页批量 AI 生成面板加「生成组数」下拉（1/2/3）；
   - 结果以分组卡片展示（第 1 组/第 2 组…），可勾选"本账号用第 N 组"或按发布目标自动轮转；
   - 素材详情编辑器允许在组间切换预览。

### B.4 补充时的注意点

- 复用现有 `apply_platform_limits` 对每组做 title 截断/话题去重与上限（douyin 标题≤xx/话题≤4、kuaishou/xhs 4、bilibili 5 等红线必须逐组执行，见 `title_topic_generator.py::PLATFORM_META`）。
- 与 B.3-5 联动：如果只做到"生成+存储多组"而发布侧仍只取单组，则对用户而言依旧"没落实"——本审计建议把**发布任务按组分配**作为该功能的验收标准之一。
- 现有 `/api/v1/ai/chat` 交互式生成（matrix 页 L435-460）也应支持 `group_count`，保持两条 AI 出口行为一致。

---

## C. 其它相关发现（非本次两问，供参考）

1. `matrix_scheduler.py`（投放计划/矩阵任务文件队列路径）的 `scheduled_time` 只在 `pop_next_tasks`/`dispatch` 被消费，而**仓库内没有任何调用方轮询 `/matrix/tasks/dispatch`**（前端只有 execute_now 建任务、无 dispatch 触发）；campaigns 的「矩阵节奏」若仍在使用，其定时与间隔同样依赖外部手动触发，建议确认投放计划是否仍为活跃功能、或将其 `scheduled_time` 同样迁移到 Celery eta。
2. 投放计划（campaign）后端 `interval_mode` 取值是 `account_video|video`（与矩阵页 `account_first|video_first` 不同），两套语义/命名不统一，迁移或维护时易混淆。
3. 旧的 `task_queue_manager` 保留 `not_before` 实现可视为历史参照，但当前不生效且易误导，建议在代码注释中标注"已停用，调度语义以 Celery eta 为准"。

---

## D. 实施状态（本审计后已落地修复/补充）

> 基于上面 A/B 两节的结论，以下修改已在 `feature/prism-update` 工作区完成（均为增量修改，未触碰用户未提交的 B站/auth 在途改动）。后端全部通过 AST 语法校验；前端 tsc 无新增错误（与基线一致）。

### D.1 A（发布间隔/矩阵节奏）— 已修复

| 层 | 文件 | 改动 |
|---|---|---|
| 调度落地 | `fastapi_app/api/v1/publish/services.py` | `apply_async` 前解析 `not_before`，若为未来时间则 `apply_kwargs['eta'] = eta_dt`（真正延时投递）；已过/解析失败则移除 `not_before` 立即执行 |
| Celery 兜底 | `fastapi_app/tasks/publish_tasks.py` | `publish_single_task` 开头（`update_task_state` 之前）解析 `not_before`，未到点 `self.retry(countdown=剩余秒, max_retries=12)` 重投（任务装饰器 `max_retries=0`，必须显式覆盖） |
| 前端 | `prism_frontend/src/app/publish/matrix/page.tsx` | 「发布间隔控制」开启时新增 间隔时长（秒≥10）与 随机偏移（±秒）输入；时间轴预览改为读取用户实际输入（原先写死 300/0） |

说明：`publish_batch` 内 `_create_batch_tasks` 依据 `scheduled_time`/`now_beijing_naive()` 生成 `base_time`，计算 `offset`（`video_first` 用 file_idx；`account_first` 用 account_idx 主序），叠加随机偏移后得到绝对时间并写入 `not_before` → 现在通过 `eta` 真正生效。关闭间隔控制 = 不写 `not_before` → 不设 eta → 高并发同时提交，与页面文案一致。

### D.2 B（AI 多组标签/话题）— 已整段补充

| 层 | 文件 | 改动 |
|---|---|---|
| 请求参数 | `fastapi_app/schemas/file.py` | `AIMetadataGenerateRequest` 增加 `group_count`(1-5) 与 `tags_only_groups` |
| DB | `db/schema.py` + `db/sa_models.py` | `file_records` 增 `ai_tag_groups TEXT`；SQLite 建表/`file_records_required` 补列语句 + SQLAlchemy Table 均含该列 |
| Prompt | `ai_service/title_topic_generator.py` | `build_metadata_prompt(..., group_count, tags_only_groups)`：多组时输出 `{"groups":[{title,tags}...]}` 且逐组满足平台上限；新增 `build_metadata_groups_prompt` 便捷包装 |
| 生成+解析 | `ai_service/metadata_generation_service.py` | 新增 `_extract_json_object`（括号配平，可解析嵌套 `groups` + markdown 围栏）；`_generate_one` 解析 `groups`、逐组 `apply_platform_limits`、`tags_only_groups` 时第2组起复用第1组标题；写库同时存 `ai_tag_groups` 并保持 `ai_title/ai_tags` = 第1组（兼容旧读取方）；`generate_metadata_for_files` 透传新参 |
| 批量接口 | `fastapi_app/api/v1/files/router.py` | `/batch-generate-metadata` 转发 `group_count/tags_only_groups`；入口 PRAGMA 确保 `ai_tag_groups` 列存在（旧库升级） |
| 读取 | 同上 | `GET /files/{id}/ai-content` 返回 `ai_tag_groups`（列缺失时优雅降级为空数组） |
| Hermes 工具 | `fastapi_app/services/tool_catalog.py` | `generate_ai_metadata` 工具 schema 增加 `group_count`/`tags_only_groups` 并透传 |
| 发布侧消费 | `schemas/publish.py` + `api/v1/publish/services.py` + `router.py` | `BatchTaskItem.tag_group_index`(1-5 指定第N组) / `use_ai_tag_group`(本素材轮转) / `BatchPublishRequest.use_ai_tag_groups`(整批轮转)；`_create_batch_tasks` 解析素材 `ai_tag_groups`，优先级：显式 `tag_group_index` > 自动轮转 `(account_idx+file_idx)%N` > 单组默认；组标题/话题仅让位于 platform_titles/platform_topics 显式覆盖；task_data 记录 `ai_tag_group_index` 便于追踪 |
| 前端 | `prism_frontend/src/app/publish/matrix/page.tsx` | `PublishPlan` 增 `aiGroupCount/tagsOnlyGroups/useAiTagGroups`；「AI 标签/话题 · 多组分发」配置卡（启用开关默认 3 组、组数 2-5、只换话题开关、发布自动轮转开关）；批量 AI 生成在 `aiGroupCount>1` 时改走 `/files/batch-generate-metadata`（持久化多组）并回填编辑态第1组；发布 payload 携带 `use_ai_tag_groups` |

闭环验收路径（前端）：
1. 矩阵发布页 → 选素材 → 「AI 标签/话题 · 多组分发」开启（组数 3）；
2. 点击「批量AI生成」→ 后端为每个素材生成 3 组差异化 标题+话题 并写入 `ai_tag_groups`；
3. 「发布间隔控制」开启（可选，账号/视频节奏）；
4. 选多个账号 + 「发布时自动轮转不同组」开启 → 提交 → 后端按 `(账号序号+视频序号) % 组数` 为每个任务取组，同一视频在不同账号上使用不同标题/话题。

### D.3 遗留/说明（非阻塞）

- `_generate_one` 的「已有 AI 内容跳过」判定仅看 `ai_title`：若素材此前只生成过单组、现在要补多组，需传 `force_regenerate=true`（前端多组分支已强制 true）。
- 平台级双覆盖（`platform_titles/platform_topics`）仍优先于组内容；按账号粒度"手选第 N 组"可通过 API `items[].tag_group_index` 直接指定（当前前端未暴露逐条选择 UI，以整批自动轮转为默认交互）。
- 发布页批量 AI 生成在单组模式（默认 1 组）仍走旧 `/api/v1/ai/chat`，行为零变化。
