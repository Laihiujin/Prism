# AGENTS 指令：跨平台可复用的浏览器 DOM / 弹窗 / 上传处理逻辑

> 面向 Prism 各平台 Agent。目标：把已提炼的**浏览器内可复用逻辑**（关引导遮罩、处理定位权限弹窗、自动选封面、话题精确选择、上传失败重试等）应用到其它平台（tiktok / youtube / kuaishou / xiaohongshu / channels…），并据此规划各平台发布页面的功能更新方向。

## 一、为什么做这件事

抖音上传器（`uploader/douyin_uploader/main_refactored.py`）里长出了一套**与平台无关的浏览器 DOM 处理逻辑**，但它们是内嵌在抖音类里的。其它平台各自重写相似逻辑（或用更脆弱的方式），导致：

- 每个平台的「关引导遮罩 / 处理位置弹窗 / 选封面 / 上传重试」实现不一，
- 一个平台踩过的坑（如 `arguments is not defined`、`set_thumbnail` 选错 file input）其它平台会再踩一次，
- 布局变化时要逐平台修。

**目标**：把这套逻辑收敛到共享工具 `prism_backend/utils/browser_dom.py`，各平台上传器只保留**平台自己的选择器**，DOM 操作委托给共享函数。

## 二、共享工具模块（已具备）

`prism_backend/utils/browser_dom.py` —— 所有函数 `async`、接收 playwright `Page`、**best-effort**（失败记录日志返回，不抛异常）。

| 函数 | 用途 | 关键参数 / 平台可定制点 |
|---|---|---|
| `remove_overlays(page, selectors)` | 移除会拦截点击的引导遮罩容器 | `selectors`：每平台的遮罩候选（默认可覆盖） |
| `dismiss_version_prompt(page, dismiss_texts, overlay_selectors)` | 关「官方新版本/新功能」提示层 | `dismiss_texts`：关闭按钮文案；`overlay_selectors` |
| `handle_browser_permission(page, allow_location, has_location)` | 处理浏览器定位权限弹窗（仅本次/允许/不允许/关闭） | `allow_location` / `has_location` 决定点允许还是关闭 |
| `wait_upload_complete(page, poll_interval, max_polls)` | 轮询等上传完成（出现「重新上传」/「上传失败」） | `poll_interval`；检测文案集中在函数内 |
| `handle_auto_cover(page, random_cover, cover_selector, prompt_text, confirm_text)` | 发布前自动选推荐封面（随机选帧可选） | `cover_selector` / `prompt_text` / `confirm_text` 每平台定制 |
| `select_topics_exact / select_topics_exact_with_editor(page, tags, editor_selector, topic_item_selectors, tag_prefix, clear_on_fail, topic_wait_selector)` | 输入话题 + 精确选择「文本一致且字符数一致」的人气话题项 | `editor_selector` / `topic_item_selectors` / `clear_on_fail` / `topic_wait_selector` 每平台定制（`clear_on_fail=True` 清除未成词 `#tag`；`topic_wait_selector` 等候选容器出现，适配慢速联想平台） |
| `handle_upload_error(page, file_path, upload_input_selector)` | 上传失败触发重新上传 | `upload_input_selector` |

### 已踩过并要注意的坑（务必遵守）

1. **`page.evaluate` 的回调不要用 `arguments[0]`**。patchright 的 evaluate 里 `arguments` 未定义（报 `ReferenceError: arguments is not defined`）。统一用命名形参接收：`"(crit) => { const [a, b] = crit; ... }"`，参数经 evaluate 第二个位置传入。
2. **`list, 尾部逗号会变成 tuple`**：`dismiss_texts = [...],` 会让它变成 `(list,)`，遍历时把整个 list 当文本去匹配。**不要写尾部逗号**。
3. **`remove_overlays` 用宽泛选择器会误删业务 DOM**（实测最严重）。`[class*='guide']` / `[class*='mention-wrapper']` / `[class*='popup']` / `[class*='version']` 会删掉**标题输入框、内容编辑区（div.zone-container）**，导致后续 `fill` 找不到元素超时。处理弹窗**只点关闭按钮**（`dismiss_version_prompt` 只点按钮、不删 DOM）；删容器只用于 shepherd/coachmark 这类**明确引导浮层**。
4. **填表前必须先等视频上传完成**。抖音 version_2 发布页要等视频上传完才渲染表单（标题/描述/话题）；若在等上传之前就 `wait_for(标题框)`，视频慢时必超时。先 `wait_upload_complete`（等「重新上传」出现）再 `fill`。
5. **`preview_only` 调试模式**：跑完上传+填表+封面+定位等所有前置步骤后，在点「发布」前停下（不真发布），用于安全验证。调试时用 `--headed` 可见窗口，或 `debug=True` 截图到 `logs/`。

## 三、在其它平台落地的步骤（给 agent 的迁移指令）

对每个平台上传器（`uploader/<platform>_uploader/main_refactored.py`）执行：

1. **接入遮罩/引导清理**：在进入发布页后、填表前调用 `remove_overlays(page, <该平台遮罩选择器>)` 和 `dismiss_version_prompt(page, <该平台文案>)`。
2. **接入定位权限弹窗**：
   - 有「位置」入口的平台：填位置后 `handle_browser_permission(page, allow_location=True, has_location=True)`；
   - 无位置入口的平台：`handle_browser_permission(page, allow_location=False, has_location=False)`（兜底关闭）。
3. **接入自动选封面**：发布循环里替换旧的「选第一张」逻辑为 `handle_auto_cover(page, random_cover=<是否随机>)`。
4. **接入上传失败重试**：把各平台的「检测上传失败 → 重传」抽成 `handle_upload_error(page, file_path, <该平台上输入框选择器>)`。
5. **接入话题精确选择**：把「在补全下拉里选第一个」改为 `select_topics_exact_with_editor`（按文本+字符数精确命中，必要时下滑重试）。
6. **校验**：改完先 `python3 -c "import ast,..."` 解析语法，再在**可见窗口 / preview_only** 模式跑一遍（不真正发布），确认每个回调真实命中。

## 四、页面功能更新方向（各平台据此规划）

- **统一「移除拦截层」策略**：抖音用 `.shepherd-*`，其它平台用各自 guide / toast / popup 选择器；平台页面更新后，优先维护共享 `overlay_selectors`，而不是在每个角落散落 `page.evaluate(...remove...)`。
- **统一「上传完成」判定**：以「出现可发布态 / 重新上传 / 但列表」等强信号为准，避免用固定 sleep 猜测，提升稳定性。
- **统一「封面缺失兜底」**：发布按钮灰时自动选一帧推荐封面 + 确认弹窗，降低"只取第一张"/“不选封面被拒”的容错率。
- **给定位权限/引导弹窗做"静默兜底"**：有头模式真实弹窗、无头模式直接授权；把「命中即决策（允许/关闭）」做成幂等的 best-effort，避免阻塞主流程。
- **抽公共选择器常量**：把各平台通用遮罩选择器（shepherd、mention、guide、popup 等）、权限文案（仅本次/允许/不允许）汇到共享模块顶部常量，改一处全平台生效。

## 五、验收清单（agent 实现完成后逐项勾）

- [ ] 共享模块 `utils/browser_dom.py` 可 import，函数签名与文档一致。
- [x] **快手** `uploader/ks_uploader/main_refactored.py` 已接入共享模块：`dismiss_version_prompt`（关「我知道了」）、`handle_upload_error`（失败重传）、`remove_overlays`（react-joyride 引导层）。因快手上传完成的判定信号是「上传中」文案消失（而非抖音的「重新上传」出现）、封面走显式 `set_thumbnail`，故不强行套用共享 `wait_upload_complete` / `handle_auto_cover`（保留平台自身逻辑）。
- [x] **小红书** `uploader/xiaohongshu_uploader/main_refactored.py` 已接入共享模块：`handle_upload_error`（失败重传）、`select_topics_exact_with_editor`（话题精确选择，`clear_on_fail=True` + `topic_wait_selector` 适配小红书慢速联想下拉）。小红书上传完成的判定信号是预览区文本（上传成功/分辨率/已选择/100%），与共享 `wait_upload_complete` 的「重新上传」信号不同，故保留自身判定；封面走显式 `set_thumbnail`，不套用 `handle_auto_cover`。
- [ ] 至少一个平台（建议先 tiktok 或 youtube）已接入 `dismiss_version_prompt` / `handle_browser_permission` / `handle_auto_cover`。
- [ ] 目标平台用 preview_only（或可见窗口）跑通一遍，无 `arguments is not defined`、无尾部逗号 tuple 问题。
- [ ] 未引入对抖音登录/HTTP 逆向的依赖（保持抖音生产登录走浏览器模式，遵循 `prism_backend/AGENTS.md`）。
