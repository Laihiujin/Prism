---
name: douyin-publish-computeruse
description: "用 Computer-Use（真实浏览器）+ 已登录抖音账号访问创作者中心发布页，抓取并补全抖音发布界面的全部功能到 Prism 上传器；含浏览器/登录态触发方式、官方遮挡提示与位置权限处理。"
version: 1.0.0
author: Prism
license: MIT
platforms: [macos, windows, linux]
metadata:
  hermes:
    tags: [Prism, douyin, publish, uploader, computer-use, browser-automation, creator-center]
    related_skills: [prism-project-layout]
prerequisites:
  commands: [prism, python]
---

# 抖音发布功能补全（Computer-Use 探索）

Prism 的抖音上传器（`prism_backend/uploader/douyin_uploader/main_refactored.py`）已实现部分发布功能，
但前端「抖音配置」面板仍有若干字段**无后端实现**。本技能用 **Computer-Use（真实浏览器）+ 已登录账号**
打开抖音创作者中心发布页，逐项把真实 UI 交互抓下来，再补进上传器。**核心原则：不要凭空猜 DOM。**

## 1. Computer-Use 触发方式（先看这里）

### 1.1 浏览器与登录态
- 运行时用 **patchright 的 chromium**（项目封装，见 `config.conf` 的 `LOCAL_CHROME_PATH` / `LOCAL_CHROME_HEADLESS`）。
- **登录态 = 账号的 storage_state JSON（即 `account_file`）**。上传器/登录器都是
  `browser.new_context(storage_state=account_file, ...)` 直接复用登录态。
- 取账号对应的 cookie 文件：账号对象里的 `cookie_file` 字段（`myUtils/batch_publish_service.py` 里
  `cookie_file = resolve_cookie_file(data.get('cookie_file'))`）。

### 1.2 打开流程（合并现有 `douyin_setup` 与 `upload()` 的做法）
```python
launch_kwargs = {"headless": False}           # 关键：Computer-Use 要**有头**，人可协助/扫码
if LOCAL_CHROME_PATH:
    launch_kwargs["executable_path"] = LOCAL_CHROME_PATH
else:
    launch_kwargs["channel"] = "chromium"
browser = await playwright.chromium.launch(**launch_kwargs)
context = await browser.new_context(
    storage_state=account_file,               # 复用已登录态；失效则先走 QR 登录
    permissions=["geolocation"],              # 定位权限（见 §3）
)
context = await set_init_script(context)
page = await context.new_page()
await page.goto("https://creator.douyin.com/creator-micro/content/upload",
                wait_until="domcontentloaded", timeout=90000)
```

### 1.3 登录态失效时的 QR 登录
先 `await cookie_auth(account_file)` 判断（检测"手机号登录/扫码登录"文案）。失效则调用
`douyin_cookie_gen(account_file, qrcode_callback=..., headless=False)`：
- **有头**里二维码可见→直接在浏览器扫码；或 `qrcode_callback` 把 `image_path/data_url` 回传给用户展示。
- 登录成功会**把 storage_state 写回 `account_file`**，供后续复用。
- B 站 QR 登录必须交互终端；**抖音 QR 确认需要浏览器会话信任**，不能用纯 HTTP 逆向（`douyin_http.py` 生产禁用）。

## 2. 官方遮挡/版本提示如何关闭
发布页每次都可能弹「官方新版/新增功能/视频预览提示」浮层。已有方法 `dismiss_version_prompt(page)`（`main_refactored.py` 第 **562** 行）：
1. 先点关闭按钮（`我知道了` / `立即体验` / `跳过` / `暂不`）——用 `page.get_by_text(...).first.click(timeout=, force=True)` 兜底。
2. 再移除**纯遮挡容器**（覆盖整页、无可见关闭按钮的那种）：委托 `utils/browser_dom` 移除。
3. 每次进发布页、以及可能弹窗的关键步骤前都调一遍（`upload()` 已在第 **985** 行进页后调用）。
> 新增的遮挡提示同理：找不到明确按钮就先找并移除全屏遮挡容器再重试，**不要硬写**未确认的选择器。

## 3. 位置权限（定位/POI）
- context 已 `permissions=["geolocation"]`；无头一般直接授权，有头可能弹**原生权限框**（允许/仅本次/不允许）。
- 已有方法 `_handle_browser_permission(page, allow_location, has_location)`（第 **585** 行）：
  `has_location=True` → 点「本次允许」；否则关闭/选「不允许」。
- 填 POI 用 `set_location(page, location)`（第 **386** 行）；发布页位置入口文案「添加位置」。
- 无位置时不调 POI，但一定要兜底处理权限框（防止它拦截后续封面/声明点击）。

## 4. 抖音发布界面功能 → 现状

**已实现（不要重写，在其基础上补）：**

| 功能 | 方法 | 行号 |
|---|---|---|
| 话题补全精确选择 | `_select_topic_exact` | 359 |
| 官方遮挡/版本提示清理 | `dismiss_version_prompt` | 562 |
| 浏览器定位权限 | `_handle_browser_permission` | 585 |
| 设置位置 POI | `set_location` | 386 |
| 随机封面 | `handle_auto_video_cover` | 768 |
| 封面上传（横/竖） | `set_thumbnail`+`_handle_cover_recommend_modal`+`_force_close_cover_modal` | 830/793/894 |
| 自主声明 | `set_self_declaration`+`apply_self_declaration` | 469/715 |
| 小程序链接 | `set_miniprogram_link` | 631 |
| 定时发布 | `set_schedule_time_douyin` | 325 |

**本次待补（无后端实现，需 Computer-Use 观察还原）：** `whoCanSee`(谁可以看)、`savePermission`(保存权限)、
`hotspot`(关联热点)、`collection`(合集)、`coverFile`(自定义封面文件)、`coverOrientation`(横竖精细控制)、
`miniProgram`(作为「挂载内容」对象，而非链接)、`productLink/title`(商品挂载确认)。

## 5. 执行步骤

### Step 1 — 打开真实发布页
按 §1 用有头浏览器 + 已登录 storage_state 打开 creator 上传页，选一个视频进入发布表单。

### Step 2 — 枚举发布页全部可互动控件
从上到下记录：标题、简介/描述、话题、BGM、视频封面(上传/随机/AI推荐/横竖)、位置(POI)、
挂载内容(小程序/游戏/应用)、合集、自主声明、关联热点、谁可以看、保存权限、定时发布、商品链接/购物车、更多设置。

### Step 3 — 每项产出「实现规格」（核心交付物）
对每项记录：①入口按钮文字 ②精确选择器（含 `nth()`/`force`/`exact`）③弹窗/浮层（容器、选项文字、关闭按钮）④无该选项时占位文案 ⑤写进 `main_refactored.py` 的落点（方法 + 挂进 `upload()` 的哪一阶段）。
> 禁止编造选择器；看不准就重试/截图，返回真实 DOM 片段。

### Step 4 — 接入上传器 `upload()`
建议顺序：封面 → 位置/权限 → 合集 → 挂载内容 → 关联热点 → 谁可以看 → 保存权限 → 自主声明 → 商品/小程序 → 定时。
保持 §4 已有 9 项**不回归**；改完跑语法校验。

## 5. 官方全组件测试算法

每次执行都必须建立一份真实浏览器测试记录，不能只验证代码调用成功：

1. 使用已登录的 Patchright 有头浏览器，上传一个真实视频，确认进入
   `/creator-micro/content/post/video?enter_from=publish_page`。
2. 从上到下扫描并记录所有可互动控件：标题、简介、话题、`@好友`（可搜索并选择任意结果）、官方活动、BGM、封面、合集、声明、
   位置、热点、挂载内容、同时发布、谁可以看、保存权限、立即/定时发布、商品和更多设置。
3. 每个控件至少执行一次“打开→观察→选择或关闭→重新读取页面状态”；记录入口文字、AX role/index、
   真实 DOM 片段、弹窗文案、空数据占位和失败提示。AX index 每次操作后必须重新获取，禁止复用旧 index。话题采用真实富文本语义：一次性输入完整 `#关键词`，直接按空格确认；不等待、不点击候选、不按回车，避免重复 `##` 或换行。
4. 封面必须执行方向交叉测试：
   - 竖视频 + 横封面：验证推荐竖封面弹窗，分别测试保留横封面和切换竖封面。
   - 横视频 + 竖封面：验证推荐横封面弹窗；若账号未出现该文案，记录“未确认”，不得伪造通过。
   - 自定义封面上传、AI 推荐封面、完成、关闭和遮罩清理分别记录结果。
5. 位置权限必须覆盖“访问该网站时允许”“仅这次访问时允许”“一律不允许”和关闭四种结果；
   有 POI 时优先验证仅本次允许，无 POI 时验证拒绝/关闭不阻塞后续控件。
6. 不点击最终“发布”作为测试结束条件。只有在用户明确要求真实发布并再次确认时，才允许提交；
   普通回归以“字段已填、选项状态已变、弹窗已关闭、页面未被遮罩、发布按钮可用”为通过。
7. 将实际结果写入 `docs/douyin-publish-features.md`，把未观察到的官方功能标为“未确认”，
   然后运行 Python 语法检查、上传器 dry-run/preview 检查和前端构建。
8. 视频上传出现“上传失败”时，必须点击/触发“重新上传”，重新选择原视频并重新等待完成；失败重试未完成前不得填标题、话题或继续发布。

## 6. 交付物
1. `docs/douyin-publish-features.md`（Step 3 完整规格表）。
2. `main_refactored.py` 的新增方法 + 挂进 `upload()`。
3. 前端 `platformSettings.douyin` 字段名与上传器读取一致（`poi→location`、`useAIRandomCover→random_cover`、`declaration`、`collection`、`whoCanSee`、`savePermission`、`hotspot`、`miniProgram`、`coverFile`、`coverOrientation`、`timing/publishDatetime`）。

## 7. 约束
- **禁用** `app_new/platforms/douyin_http.py` 生产链路；登录必须走浏览器模式（`DouyinAdapter`/`PlaywrightLoginManager`）。
- 不改 e205652 已有 7 项功能实现（除非补参数）；不改 `platforms/douyin/upload.py` 已有 `location/declaration/random_cover/miniprogram_*` 签名语义。
- 二维码/验证图展示给用户，不只回路径。
- 无法复现的交互明确标注「未确认」，不要硬写选择器。
