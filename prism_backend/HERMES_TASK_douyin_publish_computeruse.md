# Hermes 指令：用 Computer-Use 观察抖音创作者中心发布页，补全发布功能

> 交给 Hermes 执行。核心：**不要凭空猜 DOM**——用 computer-use（真实浏览器）+ 已登录账号
> 打开抖音创作者中心的视频发布页，逐项把真实 UI 的交互规律抓下来，再把【发布界面全部功能】
> 补进 Prism 的抖音上传器。

---

## 一、目标
把抖音**视频/图文发布页的所有可互动功能**，从"真实界面"逐项还原成可执行的自动化步骤，
接入现有抖音上传器，并产出每项功能的 DOM 交互规格文档。

做完后：前端「抖音配置」面板的每个字段，发布时都能真实生效。

## 二、背景（先说清楚，别重复做）
- 前端面板字段在 `prism_frontend/src/app/publish/components/PlatformConfigs.tsx`（`DouyinConfig`）。
  字段：`miniProgram`、`poi`、`coverOrientation`、`useAIRandomCover`、`coverFile`、`collection`、
  `declaration`、`hotspot`、`whoCanSee`、`savePermission`、`timing`、`publishDatetime`、`productLink/title`。
- 发布链路：面板 → `plan.platformSettings.douyin` → 发布 payload `platform_settings` →
  后端 `task_data["platform_settings"]` → `myUtils/batch_publish_service.py` 的 `handle_single_publish`
  → 上传器 `prism_backend/uploader/douyin_uploader/main_refactored.py` 的 `upload()`。

## 三、抖音上传器已有（不要重写，在其基础上补）
文件：`prism_backend/uploader/douyin_uploader/main_refactored.py`；主流程 `upload()` 在**第 935 行**。

| 功能 | 方法 | 行号 | 状态 |
|---|---|---|---|
| 话题补全精确选择 | `_select_topic_exact` | 359 | ✅已有 |
| 版本提示遮挡清理 | `dismiss_version_prompt` | 562 | ✅已有 |
| 浏览器定位权限 | `_handle_browser_permission` | 585 | ✅已有 |
| 设置定位 | `set_location` | 386 | ✅已有 |
| 随机封面 | `handle_auto_video_cover` | 768 | ✅已有 |
| 封面上传(横/竖) | `set_thumbnail` + `_handle_cover_recommend_modal` + `_force_close_cover_modal` | 830/793/894 | ✅已有 |
| 自主声明 | `set_self_declaration` + `apply_self_declaration` | 469/715 | ✅已有 |
| 小程序链接 | `set_miniprogram_link` | 631 | ✅已有 |
| 定时发布 | `set_schedule_time_douyin` | 325 | ✅已有 |

**本次要补的（无实现/待补全）：** `whoCanSee`(谁可以看)、`savePermission`(保存权限)、
`hotspot`(关联热点)、`collection`(合集)、`coverFile`(自定义封面文件)、`coverOrientation`(横竖封面精细控制)、
`miniProgram`(作为「挂载内容」对象选择，而非链接)、`productLink/productTitle`(商品挂载，已在 upload() 有但确认)。

## 四、执行步骤（必须用 computer-use + 已登录账号）

### Step 1 — 打开真实发布页
以 computer-use 模式，利用已登录的抖音账号访问：
`https://creator.douyin.com/creator-micro/content/upload`
选好一个视频上传到发布页（`/creator-micro/content/publish?enter_from=publish_page` / `post/video`），
停留在**发布表单页**。

### Step 2 — 逐项枚举发布页所有可互动控件
顺着界面上到下，把每一个功能/开关/弹窗记下来。至少覆盖：
标题、简介/描述、话题、BGM、视频封面(上传封面/随机/AI推荐/横竖封面)、**位置(POI)**、
**挂载内容(小程序/游戏/应用)**、**合集**、**自主声明**、**关联热点**、**谁可以看**、
**保存权限**、**定时发布**、**商品链接/购物车**、**可见性/更多设置**。

### Step 3 — 对每个功能产出「实现规格」（这是核心交付物）
对每一项，记录：
1. **入口**：触发它要点的按钮/标签文字（如"选择封面/添加位置/添加标签→小程序/添加到合集/添加声明/关联热点/谁可以看/保存权限"）。
2. **精确选择器**：实际抓到的元素（如 `.semi-modal-content`、`input.semi-upload-hidden-input`、`[role="option"]` 等），并标注 `nth()` 索引/是否需 `force`、`exact`。
3. **弹窗/浮层**：点开后的容器、选项文字、关闭按钮（如"暂不设置/设置竖封面/我知道了/跳过"）。
4. **边界**：无该选项时的占位文案（如"请选择自主声明""请设置封面后再发布"）、失败时的兜底。
5. **写进上传器的落点**：在 `main_refactored.py` 补哪个方法、在 `upload()`（935 行起）哪个阶段调用。

> 禁止编造选择器。看不准就改成"重试/截图确认"，返回实际 DOM 片段。

### Step 4 — 把每个功能接入上传器 `upload()`
按规格在 `main_refactored.py` 新增方法并挂到 `upload()` 对应阶段（建议顺序）：
封面 → 位置/权限 → 合集 → 挂载内容 → 关联热点 → 谁可以看 → 保存权限 → 自主声明 → 商品/小程序 → 定时。
保持已有 7 个功能**不回归**。改完跑语法校验，能跑 `douyin_upload_video` 到不崩。

## 五、交付物
1. **`docs/douyin-publish-features.md`（规格文档）**：上面 Step 3 的完整表格（功能→入口→选择器→弹窗→落点）。
2. **`main_refactored.py` 的改动**：新增功能方法 + 挂进 `upload()`。
3. **如需前端对齐**：`platformSettings.douyin` 的字段名与上传器读取保持一致（`poi→location`、`useAIRandomCover→random_cover`、`declaration`、`collection`、`whoCanSee`、`savePermission`、`hotspot`、`miniProgram`、`coverFile`、`coverOrientation`、`timing/publishDatetime`）。

## 六、约束
- **禁用** `prism_backend/app_new/platforms/douyin_http.py` 用于发布链路；生产登录走浏览器模式（`DouyinAdapter` / `PlaywrightLoginManager`）。
- 不要动已有 e205652 的 7 个功能实现（除非补参数）。
- 不要改 `platforms/douyin/upload.py` 里已有的 `location/declaration/random_cover/miniprogram_*` 签名语义。
- computer-use 里产生的二维码/验证图，展示给用户，不要只回路径。
- 每步用真实 DOM 片段佐证；无法复现的要明确标注"未确认"，不要硬写选择器。
