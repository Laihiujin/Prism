# 抖音发布页功能补全 —— 工作记录（2026-09-02）

> 本文件是本次「用真实浏览器观察抖音创作者中心发布页 → 补全上传器发布功能」的工作报告。
> 与规格文档 `docs/douyin-publish-features.md`（功能→选择器→落点）配套。
> **修正：** 文中所有浏览器会话均使用**真实登录账号**（`cookiesFile/douyin_Siuyechu_.json` 的 storage_state），
> **并非隔离的临时 profile**。每次会话都是以该真实号身份进入创作者中心，并上传了测试视频（草稿，未发布）。

---

## 一、目标
把抖音视频发布页的可互动功能（谁可以看、保存权限、关联热点、合集、挂载内容、横竖封面/封面上传、发布时机）从真实界面还原成可执行自动化，接入抖音上传器，并产出 DOM 规格文档。

## 二、实际做了什么

### 真实浏览器观测
- 引擎：Patchright（项目自带）+ **系统 Chrome**（`LOCAL_CHROME_PATH`），`headless=False` 有头。
- 登录态：`new_context(storage_state=cookiesFile/douyin_Siuyechu_.json)` → **真实账号**。
- 页面：`https://creator.douyin.com/creator-micro/content/upload` → 上传测试视频 → 进入 `.../content/post/video?enter_from=publish_page`（version_2 发布表单）。
- 取回：`PUBLISH_PAGE.html`（1.8MB 发布页完整 DOM）+ 多张截图。

> ⚠️ **真实副作用：** 这次观测为让发布表单渲染，用真实账号上传了测试视频。每次会话各上传 1 次，共约 **6 次**，都是
> `videoFile/60d455f2-8501-4488-bedc-3b58bc8767db.MP4`。全部只是 **上传到草稿**（preview_only / 未点「发布」），
> 未真正发布到公开内容；但这些**草稿会真实出现在该账号后台（作品/草稿）**。需你到创作者中心手动删除。

### 打开的下拉/弹窗（真实 DOM）
- 「添加标签」下拉选项：`位置 / 影视演艺 / 小程序 / 标记万物`
- 合集下拉：`请选择合集` + `不选择合集`
- 关联热点下拉：占位 `点击输入热点词`，点击后有 1 个 input、预载约 55 项（门店/POI 类）
- 谁可以看 / 保存权限：`label.radio-d4zkru` 单选
- 封面卡片：横封面4:3 / 竖封面3:4 / Ai智能推荐封面

## 三、交付物（文件改动）

| 文件 | 改动 | 说明 |
|---|---|---|
| `docs/douyin-publish-features.md` | **新增** | 功能→入口→精确选择器→弹窗→边界→落点 规格文档 |
| `prism_backend/uploader/douyin_uploader/main_refactored.py` | 增改 | 新增 `set_who_can_see / set_save_permission / set_hotspot / set_collection / set_mount_object`；`set_thumbnail` 按 `cover_orientation` 分横竖；`DouYinVideo.__init__` 增加对应字段；`upload()` 按「封面→位置→合集→挂载→热点→谁可以看→保存权限→自主声明→商品/小程序→定时」接入 |
| `prism_backend/myUtils/batch_publish_service.py` | 增改 | 解包 `platform_settings.<平台>`（新增 `PLATFORM_SETTINGS_KEY_BY_CODE` 与 `_platform_settings_for`），把 whoCanSee/savePermission/hotspot/collection/coverOrientation/coverFile/miniprogramObject 透传给上传器 |
| `prism_backend/platforms/douyin/upload.py` | 增改 | `DouyinUpload.upload()` 增加同名参数并 best-effort 应用；新增 `_set_who_can_see/_set_save_permission/_set_hotspot/_set_collection/_set_mount_object` |
| `prism_backend/fastapi_app/services/tool_catalog.py` | 增改 | `douyin_preview` handler 解包 `platform_settings.douyin` 并传入 `DouYinVideo` |

## 四、验证结果（真实跑通，未发布）
`DouYinVideo(main → preview_only=True)` 全流程跑到发布按钮前停住、无崩溃，日志确认：
- 视频上传 ✓ / 标题/描述/话题 ✓ / 位置权限处理 ✓
- 横版封面已上传到预览 ✓ / 封面设置完成 ✓
- **关联热点已选「热点」** ✓（改 two 倍 emoji 为单倍，纯日志）
- **谁可以看已设「仅自己可见」** ✓
- **保存权限已设「不允许」** ✓
- preview_only 停在「发布」前，未真正发布 ✓
- 全部文件 `ast.parse` + 关键模块 `import` 通过。

## 五、未确认 / 风险（已同步标注在规格文档）
1. **关联热点候选语义**：实测候选是门店/POI 类（非纯“热点话题”），接口数据面未确认，按「选第一条」处理。
2. **挂载内容「对象」浮层**：选中「小程序」后进入的搜索选对象面板，其**内部选择器未展开确认**，用了兜底搜索，命不中记日志跳过。
3. **商品/购物车**：本轮「添加标签」选项只有 位置/影视演艺/小程序/标记万物，**没有「购物车」**；既有 `set_product_link` 依赖的 `购物车` 选项大概率失效，未改既有实现，文档标注风险。
4. 未传封面时的兜底 `请设置封面后再发布` 由既有 `handle_auto_video_cover` 处理。

## 六、观测/证据产物（`prism_backend/_edu_obs/`）
- `PUBLISH_PAGE.html`：发布页完整 DOM（1.8MB）
- `PUBLISH_PAGE_full.png` / `PUBLISH_PAGE_top.png`：整页/首屏截图
- `obs_anchor_options.html|.png`：挂载内容下拉展开
- `obs_collection_options.html|.png`：合集下拉展开
- `obs_hotspot_options.html|.png`：关联热点下拉展开
- `run_obs*.py / run_preview.py / run_hotspot*.py`：观测/验证脚本（可删）
- 预览截图路径：`prism_backend/logs/douyin_preview_screenshot.png`

## 七、需要你处理的真实副作用
- 该真实账号后台有约 **6 条测试视频草稿**（同一测试视频），请到创作者中心删除。
- 浏览器会话均由系统 Chrome 启动、关闭即消失，未改动系统 Chrome 的登录态（登录态在 `cookiesFile/douyin_Siuyechu_.json` 中）。

## 八、未发布 & 未登录状态
未点击任何「发布」；登录用的是既有 storage_state，没有触发扫码/验证码流程，因此没有产生二维码/验证图需要向你展示。
