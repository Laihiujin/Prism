# 抖音创作者中心·发布页 可交互功能 DOM 规格（实测，2026-09）

> 本文档由 **真实浏览器 + 已登录账号**（`cookiesFile/douyin_Siuyechu_.json`，Playwright/Patchright 驱动系统 Chrome）
> 打开发布表单页 `https://creator.douyin.com/creator-micro/content/post/video?enter_from=publish_page` 后，
> 从**实际得到的 DOM**（`prism_backend/_edu_obs/PUBLISH_PAGE.html`）逐项反推。**所有选择器均来自真实 DOM，未凭空编造。**
> 无法在本轮复现/确认的项，明确标注 **「未确认」**，不硬写选择器。
>
> 备注：class 名（如 `radio-d4zkru`、`title-content-oaqcSp`、`coverControl-CjlzqC`）是抖音前端构建的
> CSS-Module 哈希名，可能随版本变化；下列选择器**同时**给出【稳定文本/结构锚点（推荐）】与【哈希 class（记录用）】，
> 工程上用 **文本语义 + 半通用的 Semi/结构容器** 优先，哈希名作为兜底。

---

## 页面统一结构（每个功能一「行」）

发布设置区每个功能都是一行固定结构：

```html
<div class="content-obt4oA new-layout-sLYOT6">          <!-- 行 -->
  <div>
    <div class="title-dS7kae">
      <span class="title-content-oaqcSp">功能名</span>     <!-- 标题文本，推荐锚点 -->
      <span class="icon-J5CkaA"><svg>…</svg></span>       <!-- 问号 ICON（hover 提示） -->
    </div>
  </div>
  <div class="content-child-V0CB7w content-limit-width-zybqBW">  <!-- 控件容器 -->
    <div> <实际控件> </div>
  </div>
</div>
```

> 工程惯例：定位一行 = `page.locator("div.content-obt4oA").filter(has_text="<功能名>")`，再进其控件。
> 标题文本唯一，`filter(has_text=...)` 不会误中。


## 行控件明细（抓到的真实 DOM）

| 功能 | 行标题文本 | 控件容器（哈希 class） | 控件真实结构 |
|---|---|---|---|
| 谁可以看 | `谁可以看` | `div.container-OZ8FUX` | 3 个 `label.radio-d4zkru`（value 公开=0/好友=2/自己=1） |
| 保存权限 | `保存权限` | `div.download-content-Lci5tL` | 2 个 `label.radio-d4zkru`（允许 value=1 / 不允许 value=0） |
| 关联热点 | `关联热点` | `div.semi-select…semi-select-filterable` | 可输入筛选下拉，占位 `点击输入热点词` |
| 添加标签（挂载内容） | `添加标签` | `div.anchor-container-hgj7gj div.semi-select`（class `select-lJTtRL`） | 单选下拉，当前值 `位置`（data-code=-11） |
| 添加合集 | `添加合集` | `div.mix-sel-wrap-X7ee1N` 内 `div.semi-select.select-collection-nkL6sA` | 下拉，占位 `请选择合集`；同级另一下拉 `select-mix-type-G9iqb2`（值 `合集`） |
| 自主声明 | `自主声明`（`section.wrapper` 内 `title-cnbkZe`） | `controlWrapper-Kt_9Xm` 内 `div.selectBox-buZRzi` | 占位 `请选择自主声明`；弹窗「对作品内容添加声明」单选 |
| 位置（POI） | （无行标题） | `div.semi-select.select-PJBSlx...semi-select-no-arrow` | 占位 `输入地理位置`（可输入筛选） |
| 视频封面 | （封面卡片区） | `div.coverControl-CjlzqC` ×2 | 横封面 `cover-tip-YkBvmu"横封面4:3"`；竖封面 `"竖封面3:4"`；`recommendContainer-xwwJ2i`「Ai智能推荐封面生成中...」 |
| @好友 | 编辑器内 `@好友` | 真实表单 AX 文本 `@好友`（输入后搜索浮层选择项） | 实际好友搜索结果需按当前账号实时观察，账号名不硬编码；选择器未确认 |
| 发布时间 | `发布时间` | — | `立即发布 / 定时发布` 两个 `label.radio-d4zkru`；定时时间 `input.semi-input[placeholder="日期和时间"]` |

---

## 一、功能 → 入口 → 选择器 → 弹窗 → 边界 → 落点

### 1. 谁可以看（whoCanSee）

- **入口**：发布设置区「谁可以看」行，三个单选 `公开 / 好友可见 / 仅自己可见`。
- **精确选择器**（真实 DOM）：
  - 行：`page.locator("div.content-obt4oA").filter(has_text="谁可以看")`
  - 选项：`label.radio-d4zkru`，内部 `<span>` 文本 `公开` / `好友可见` / `仅自己可见`。
    - 单选锚点（推荐）：`label.radio-d4zkru:has-text("<选项>")`（这三个文本全局唯一，直接点也可）
    - 结构锚点（记录）：`div.container-OZ8FUX label.radio-d4zkru`
  - `data-checked="true"` 表示当前选中；公开为默认（value=0）。
- **弹窗/浮层**：无弹窗，纯行内单选。切换即生效。
- **边界**：
  - `公开`（默认选中）→ 无需操作，直接跳过。
  - 文案映射：`公开/好友可见/仅自己可见`（与前端面板文案一致）。
- **落点**：`main_refactored.py` 新增 `set_who_can_see(page, who_can_see)`；`upload()` 在「保存权限」前调用。

### 2. 保存权限（savePermission）

- **入口**：「保存权限」行，两个单选 `允许 / 不允许`。
- **精确选择器**：
  - `label.radio-d4zkru:has-text("允许")` / `:has-text("不允许")`（全局唯一）。
  - 结构锚点：`div.download-content-Lci5tL label.radio-d4zkru`。
  - 允许默认 `data-checked="true"`（value=1），不允许 value=0。
- **弹窗/浮层**：无。
- **边界**：默认「允许」→ 目标为「允许」时跳过；`savePermission` 中文按 `允许/不允许` 传。
- **落点**：`set_save_permission(page, save_permission)`；`upload()` 在「谁可以看」后调用。

### 3. 关联热点（hotspot）

- **入口**：「关联热点」行，占位文本 `点击输入热点词` 的可输入筛选下拉。
- **精确选择器**：
  - 下拉容器：`div.semi-select.semi-select-single.semi-select-filterable`（`style="width:100%"`）。
  - 锚点（推荐）：`page.locator("div.semi-select").filter(has_text="点击输入热点词")`（位置下拉占位是 `输入地理位置`，二者不冲突）。
  - 输入：`<该容器> input`（filterable 型自带隐藏 input，点击后 `fill` 即触发搜索）。
  - 结果项：`[role="listbox"] [role="option"]`（实测输入「热点」后返回 POI/门店类候选，每项=标题+地址两行）。
- **弹窗/浮层**：点输入后自动浮出筛选项列表；`Escape` 关闭，或点一条即收起。
- **边界**：无结果时 `[role="option"]` 数量为 0 → 跳过（best-effort）；建议选第一条。
  - **注意**：实测候选是「门店/地点」（如“热点(东门町广场店)”），并非纯“热点话题”，**接口数据面未确认**，按「选第一条」策略处理。
- **落点**：`set_hotspot(page, hotspot)`；`upload()` 在「挂载内容」后调用。

### 4. 添加合集（collection）

- **入口**：「添加合集」行，占位 `请选择合集` 的下拉（外层容器 `div.mix-sel-wrap-X7ee1N`；类型下拉 `select-mix-type-G9iqb2` 当前值 `合集`）。
- **精确选择器**：
  - 合集下拉：`div.semi-select.select-collection-nkL6sA`（唯一，推荐锚点）。
  - 点击后选项：`[role="listbox"] [role="option"]`；实测含 `不选择合集`（以及账号自己的合集名）。
- **弹窗/浮层**：下拉浮层；`Escape` 关闭。
- **边界**：
  - `collection` 为空 / 值 `不选择合集` / `不加入合集` → 选 `不选择合集`（保持无合集）。
  - 指定合集名：先 `filter(has_text=name).first`，找不到再 `get_by_text(name, exact=True)` 兜底。
  - 具体合集名单是**账号相关的**，无法硬编码（「未确认具体合集名」，按文本命中）。
- **落点**：`set_collection(page, collection)`；`upload()` 在「位置/权限」后调用。

### 5. 添加标签 → 挂载内容（miniProgram 作为「对象」选择）

- **入口**：「添加标签」行下拉，当前值 `位置`（`data-code="-11"`）。
- **精确选择器**：
  - 下拉：`page.locator("div.anchor-container-hgj7gj div.semi-select").first`（class `select-lJTtRL`）。
  - 点开后的选项（实测抓到）：`位置 / 影视演艺 / 小程序 / 标记万物`（`[role="option"]`）。
  - 选「小程序」：`page.locator('[role="listbox"] [role="option"]').filter(has_text="小程序").first`（`小程序` 文本唯一，不会误中「标记万物/影视演艺」）。
- **弹窗/浮层**：
  - 本轮真实页面选中「小程序」后，表单直接显示 `粘贴抖音小程序链接`；点击后 AX 出现 `文本栏 (settable)`。
  - ⚠️ 未提供真实小程序链接时没有候选列表，不能凭空填入或声称已确认对象。
  - 影视演艺才进入对象搜索浮层；其内部可确认的兜底为：
    `input[placeholder*="搜索"], input[placeholder*="小程序"], input[placeholder*="名称"]` 搜索，再点 `[role="option"], [class*="item"]` 中 `has_text(对象名)` 的首项；命不中就记录日志跳过，**不阻断发布**。
- **边界**：`miniProgram` 为空 / 无 name → 跳过；找不到「小程序」选项 → 记日志跳过。
- **真实资格边界（本轮确认）**：填写用户提供的链接后，真实候选显示为「羊了个羊：星球」，点击候选后页面提示：`不满足视频有效粉丝数门槛500，无法使用小程序标签。标签要求可在“抖音APP创作者中心-设置-标签使用要求”查看`。上传器必须把该提示视为平台资格失败并记录，不得当作挂载成功。
- **删除与替换（本轮确认）**：清空已填写链接后重新输入第二个真实链接，候选变为「疯狂水世界」，副标题为「一款未来水世界题材的海上末日模拟生存手游」；点击候选后同样出现有效粉丝数门槛 500 的资格提示。说明链接替换和候选刷新均生效，但当前账号不能最终启用小程序标签。

#### 5.2 标记万物（真实补测）

- **入口**：点击「添加标签」当前类型下拉，选择「标记万物」。本次真实页面确认下拉项为：`位置 / 影视演艺 / 小程序 / 标记万物`。
- **输入控件**：选择后出现可编辑字段，AX 实际文案为 `请输入或选择标记的物品`；点击该字段展开候选浮层。这里暂不写未经 DOM 复核的 CSS 选择器，自动化应优先按该占位文案定位，并在失败时截图确认。
- **候选浮层实测**：浮层提示为 `标记同款好物，有机会享现金和流量激励`，本次抓到的候选为：
  `大疆Osmo Pocket 3`（摄影设备 · 5887人讨论）、
  `影石GO 3S复古玩家限定版`（摄影设备 · 669人讨论）、
  `富士一次性胶卷相机`（胶卷相机 · 782人讨论）、
  `摩可纳8号咖啡`（咖啡 · 7937人讨论）、
  `东方树叶茉莉花茶`（饮料 · 3.0万人讨论）、
  `大疆Osmo Action4`（运动相机 · 3571人讨论）、
  `大疆 Osmo Action 5 Pro`（运动相机 · 1204人讨论）、
  `三养火鸡面`（方便速食 · 1.4万人讨论）、
  `iPhone 16 Pro`（手机 · 3692人讨论）、
  `被讨厌的勇气:自我启发之父阿德勒的哲学课`（社会科学 · 2507人讨论）。
- **预选记录**：已实际点击并选中 `大疆Osmo Pocket 3`；候选浮层收起，字段值变为 `大疆Osmo Pocket 3`。本次未触发资格失败提示。
- **删除/替换**：本次已确认候选选择成功，但尚未对「标记万物」的删除 X 和替换流程做完整复测；实现前不得假定删除按钮的固定位置或选择器。
- **上传器落点**：当前 `set_mount_object(page, mini_program)` 只覆盖小程序链接/对象流程；应新增独立的 `set_mark_anything(page, mark_anything)` 分支，在 `upload()` 的挂载内容阶段调用。候选匹配可复用现有文本相似度策略，但必须以真实候选文本确认点击结果；无候选时记录并跳过，不伪报挂载成功。

#### 5.3 关联热点与发布设置（真实补测）

- **关联热点**：点击「关联热点」后，真实 AX 控件变为可编辑文本栏，当前占位为 `点击输入热点词`。输入 `科技` 后本次未出现可确认候选，已记录为“无候选/未选中”，不能把推荐内容当作热点绑定成功。
- **发布设置入口**：真实页面顺序为「同时发布」→「谁可以看」→「保存权限」→「发布时间」。本次逐项操作后均重新读取状态：
  - 「同时发布」：`不同时发布` / `同时发布到`，真实 AX 为复选框，Value 分别为 `1 / 0`。
  - 「谁可以看」：`公开` / `好友可见` / `仅自己可见`，Value 分别为 `1 / 0 / 0`；实测切换到「好友可见」后为 `0 / 1 / 0`。
  - 「保存权限」：`允许` / `不允许`，Value 分别为 `1 / 0`；实测切换到「不允许」后为 `0 / 1`。
  - 「发布时间」：`立即发布` / `定时发布`，Value 分别为 `1 / 0`；实测切换到「定时发布」后出现日期时间输入栏，AX 占位为 `日期和时间`，并显示提示 `支持2小时后及14天内的定时发布`。
- **恢复状态**：测试结束已恢复为「不同时发布、公开、允许、立即发布」，没有点击最终「发布」。
- **同时发布到（本次补测）**：切换到「同时发布到」后，真实页面展开两个独立平台开关：`番茄小说` 与 `红果短剧`；另有 `记住我的选择` 开关及说明 `开启后，每次发布作品将自动同时发布到指定产品`。实测点击「番茄小说」后 AX 状态为 `切换 on`，`红果短剧`保持 `切换 off`，说明平台选择不是静态文案。该组合也会影响后续发布配置，必须纳入状态机并在发布前校验。
- **记住选择与独立性说明（原文实测）**：`记住我的选择` 开启后，页面明确说明 `开启后，每次发布作品将自动同时发布到指定产品`；下方明确说明 `作品发布到其他应用后与抖音相互独立，遵循该应用平台规则与内容限制，且不受抖音内变更（如设置隐私、删除等）影响`。本轮进一步实测：番茄小说与红果短剧均可切换为 `on`，再分别切回 `off`；`记住我的选择` 也可切换为 `on`。最终已关闭同步平台，未执行发布。
- **上传器落点**：关联热点接入 `set_hotspot`；可见性接入 `set_who_can_see`；保存权限接入 `set_save_permission`；定时接入既有 `set_schedule_time_douyin`。所有入口都应按当前页面重新获取的 AX/文本定位，不复用旧索引。

#### 5.4 发布设置排列组合复现矩阵

四组设置不能只按单控件实现，实际状态空间为 `2 × 3 × 2 × 2 = 24` 组：

| 维度 | 取值 |
|---|---|
| 同时发布 | 不同时发布、同时发布到 |
| 谁可以看 | 公开、好友可见、仅自己可见 |
| 保存权限 | 允许、不允许 |
| 发布时间 | 立即发布、定时发布 |

实现要求：进入上传页后先读取当前状态；按配置依次设置四个维度；每次设置后重新读取并校验选中值；定时发布必须额外校验日期时间输入值；任何一个维度失败都不能继续到最终发布按钮。测试覆盖默认组合、每个维度的单项切换、`好友可见 + 不允许保存 + 定时发布`、`仅自己可见 + 允许保存 + 定时发布` 两组边界组合，剩余组合由同一状态机参数化覆盖。测试完成恢复 `不同时发布 / 公开 / 允许 / 立即发布`。

#### 5.5 AI 智能推荐封面（三选一真实补测）

- **入口**：发布页「设置封面」区域的 `Ai智能推荐封面`；无需上传自定义封面即可使用。
- **检测状态**：AI 推荐封面区域上方可能显示 `封面效果检测通过`；这是可选状态提示，有则记录，没有也不阻断后续流程，不能把它作为硬门槛。
- **候选**：真实页面显示 3 张推荐封面缩略图，截图中第一张带 AI 字样，第二张为无文字版本，第三张为无文字版本。
- **交互**：三张候选均可直接点击；本次按第 1 → 第 2 → 第 3 的顺序逐一点击，最后第 3 张显示红色边框和白色勾选，说明选择状态以最后一次点击为准。
- **DOM/定位边界**：本次确认的是页面真实 AX 图片节点与视觉状态；缩略图没有稳定可读的独立名称，因此不编造 CSS/nth 选择器。实现应按「Ai智能推荐封面」区域重新抓取 3 个可点击缩略图，点击后重新读取红框/勾选状态；数量不是 3 时记录异常并停止该步骤。
- **上传器落点**：`handle_auto_video_cover` / `set_thumbnail` 的 AI 推荐分支；当 `useAIRandomCover=true` 且没有 `coverFile` 时进入，选择一个候选并验证最终选中状态，不应要求先上传封面文件。横/竖封面切换后需要重新抓取候选，不能复用旧缩略图索引。
- **落点**：`set_mount_object(page, mini_program)`；`miniProgram.url/link` 填入真实链接，`upload()` 在「合集」后调用。

#### 5.1 影视演艺对象搜索（真实补测）

- **入口**：先点击当前标签「位置」，再从下拉菜单选择「影视演艺」；不能点击旁边的说明图标代替。
- **真实状态**：选择后出现输入框，占位 `输入IP名称, 如 “少年的你”`。
- **搜索测试**：输入 `沙丘` 后真实返回：`沙丘 电影10.6亿次播放`、`沙丘 电影289.1亿次播放`、
  `沙丘2 电影25.3亿次播放`、`沙丘魔蚁 电影9.9亿次播放`、`沙丘虫暴 电影23.3亿次播放`。
- **选择结果**：点击真实结果列表后，表单回填为 `沙丘`；候选列表容器在 AX 中显示为 `列表框`。
- **奥德赛补测**：输入「奥德赛」真实返回 `奥德赛 · 电影 · 3.3亿次播放`、`奥德赛 · 电影 · 3.0亿次播放`、
  `刺客信条：奥德赛 · 剧情臻享 · 1.3亿次播放`；已选择首个精确标题「奥德赛」。
- **匹配规则**：优先精确标题，再结合前缀、字符序列、中文 n-gram 与热度排序；不得硬编码候选名称。
- **落点**：扩展 `set_mount_object(page, mini_program)`，影视演艺应使用对象搜索流程，而不是小程序链接流程。

### 6. 视频封面：选择封面 / 横竖封面 / AI 推荐（coverOrientation + coverFile）

真实操作补充：竖屏视频进入封面弹窗后可见「设置横封面」「设置竖封面」以及「完成」；
上传横封面时会触发“推荐竖封面”类提示。上传横屏视频后是否出现完全对称的“推荐横封面”
本轮未在真实账号中复现，代码已按两类推荐按钮做兼容，但该反向文案仍标记为未确认。

- **入口**：左侧封面区两张卡片，`div.title-wA45Xd"选择封面"`；卡片类 `coverControl-CjlzqC`。
  - 横封面卡：`cover-tip-YkBvmu"横封面4:3"`（第 1 张，width:90px）。
  - 竖封面卡：`cover-tip-YkBvmu"竖封面3:4"`（第 2 张）。
  - AI 推荐区：`div.recommendContainer-xwwJ2i` → `recommendTitle-aEUy6n"Ai智能推荐封面生成中..."` → `recommendCoverContainer-S5XRoQ`。
- **精确选择器（封面弹窗）**：
  - 点卡片（或 `text="选择封面"` force）打开 `div.dy-creator-content-modal` / `div.dy-creator-content-modal-wrap`。
  - 封面上传隐藏输入：`div.dy-creator-content-modal input.semi-upload-hidden-input` 的 **`nth(1)`**（index 0/1 是「AI 生成参考图」上传/替换，2/3 才是「上传封面/替换」——既有 `set_thumbnail` 已正确用 nth(1)）。
  - 横/竖封面切换按钮文案：`设置横封面(4:3)` / `设置竖封面(3:4)`（兜底 `设置竖封面/设置横封面/竖版封面/横版封面`）。
  - 竖屏视频传完横封面后会弹「设置两张封面获得更多曝光」推荐框（按钮：`设置竖封面` / `暂不设置`/`完成`）。
  - 应用封面：`button[role]primary …:has-text("完成")`（`exact`，避免误中「完成编辑」）。
- **弹窗/浮层**：封面弹窗 + 「推荐竖封面」确认框 + `div.dy-creator-content-modal-wrap/mask`（必须真正关闭，否则遮罩后续点击；既有 `_force_close_cover_modal` 处理）。
- **边界**：
  - 未传封面时发布会提示 `请设置封面后再发布` → `handle_auto_video_cover` 兜底选推荐封面（random_cover=True 随机一帧）。
  - `coverOrientation`：`landscape`→传横封面卡并 `设置横封面`；`portrait`→传竖封面卡并 `设置竖封面`。`coverFile` 对应镜像文件路径（横/竖由 orientation 决定）。
- **落点**：
  - `set_thumbnail(page)`（既有，横/竖分文件）新增 `cover_orientation` 分支决定用哪个文件。
  - `upload()` 在位置/权限**之前**调用（顺序：封面 → 位置/权限）。

### 7. 位置（POI）——已实现，确认选择器

- **入口**：占位 `输入地理位置` 的筛选下拉（`div.semi-select.select-PJBSlx...semi-select-no-arrow`）。
- **精确选择器**：`page.locator('div.semi-select span:has-text("输入地理位置")').click()` → `keyboard.type(location)` → `[role="listbox"] [role="option"]` 首项。
- **弹窗/浮层**：点输入后浮出候选列表。
- **边界**：`location` 为空则跳过；浏览器会弹定位权限询问（`允许/仅本次/不允许`）→ `_handle_browser_permission` 处理（有位置→允许，无位置→不允许）。既有 `set_location` + `_handle_browser_permission`。
- **落点**：既有（不改）。

### 8. 自主声明（declaration）——已实现，确认选择器

- **入口**：`section.wrapper-MLZdnB` → `controlWrapper-Kt_9Xm` → `div.selectBox-buZRzi`，占位 `请选择自主声明`。
- **精确选择器**：`page.get_by_text("请选择自主声明")` → 弹窗「对作品内容添加声明」(`.semi-modal-content`) → 单选 `dialog.locator(".semi-radio").filter(has_text=declaration)`，兜底 force 精确文本 → `get_by_role("button","确定")`。
- **落点**：既有 `set_self_declaration` / `apply_self_declaration`（不改）。

### 9. 商品链接/购物车（productLink/productTitle）——存在但待核对

- **入口**：旧实现 `set_product_link` 走「添加标签」下拉 → 选项 `购物车` → 粘贴商品链接 → 完成编辑。
- ⚠️ **实测**：本轮「添加标签」下拉抓到的选项是 `位置 / 影视演艺 / 小程序 / 标记万物`，**没有 `购物车`**。
  → 既有 `set_product_link` 依赖的 `[role="option"]:has-text("购物车")` 在本版发布页**未命中**，判定为 **「未确认/文案变更」**。
  - 建议：商品挂载可能已改走「标签」侧栏的其它 tab（商品/购物车），需再点开「标记万物」或侧栏进一步确认。
  - 兼容：保持既有 `set_product_link` 不变（不破坏），但文档标注存在失效风险；发布时若命中失败记日志跳过。

### 10. 定时/立即发布（timing/publishDatetime）——已实现，确认选择器

- **入口**：「发布时间」行，`立即发布 / 定时发布` 两个 `label.radio-d4zkru`。
- **精确选择器**：`page.locator("[class^='radio']:has-text('定时发布')").click()` → `.semi-input[placeholder="日期和时间"]` → Ctrl+A 输入 `%Y-%m-%d %H:%M` → Enter。
- **落点**：既有 `set_schedule_time_douyin`（不改）。

---

## 二、建议的 `upload()` 落点顺序

封面、（位置/权限）、合集、挂载内容、关联热点、谁可以看、保存权限、自主声明、商品/小程序、定时。

```
await self.set_thumbnail(page)                 # 封面（含 cover_orientation 分支）
await self.set_location / _handle_browser_permission   # 位置/权限（既有）
await self.set_collection(page, self.collection)       # 合集（新）
await self.set_mount_object(page, self.miniProgram)     # 挂载内容（新，对象选择）
await self.set_hotspot(page, self.hotspot)               # 关联热点（新）
await self.set_who_can_see(page, self.who_can_see)       # 谁可以看（新）
await self.set_save_permission(page, self.save_permission)  # 保存权限（新）
await self.apply_self_declaration(page)                 # 自主声明（既有）
await self.set_product_link(...) / set_miniprogram_link(...)  # 商品/小程序（既有）
await self.set_schedule_time_douyin(page, self.publish_date)  # 定时（既有）
```

---

## 三、字段名对齐（前端 `platformSettings.douyin` ↔ 上传器/链路）

| 前端面板字段 | 上层扁平字段（payload 顶层） | 链路/上传器读取 |
|---|---|---|
| `poi.name` | `location` | `DouYinVideo.location` / `DouyinUpload location` |
| `useAIRandomCover` | `random_cover` | `DouYinVideo.random_cover` |
| `declaration` | `declaration` | `apply_self_declaration` → `set_self_declaration` |
| `collection` | —（仅 platform_settings） | `set_collection(page, collection)`（新） |
| `hotspot` | —（仅 platform_settings） | `set_hotspot(page, hotspot)`（新） |
| `whoCanSee` | —（仅 platform_settings） | `set_who_can_see(page, who_can_see)`（新） |
| `savePermission` | —（仅 platform_settings） | `set_save_permission(page, save_permission)`（新） |
| `miniProgram{name,type}` | —（面板写 `miniProgram`，非 `miniprogramLink`） | `set_mount_object(page, mini_program)`（新） |
| `coverOrientation` / `coverFile` | —（仅 platform_settings） | `cover_orientation` 决定横/竖；`cover_file` → 对应 thumbnail 路径 |
| `timing` / `publishDatetime` | `publish_date`（时间戳） | `publish_strategy` + `set_schedule_time_douyin`（既有） |

> 注意：前端 `matrix/page.tsx` 目前只把 `declaration/location/random_cover/miniprogram_link/title` 写入顶层；
> `collection/hotspot/whoCanSee/savePermission/miniProgram/coverOrientation/coverFile` **只存在于
> `platform_settings.douyin`**。因此必须在 `handle_single_publish`（`batch_publish_service.py`）解包
> `platform_settings.douyin`，并把上述字段透传给上传器，否则这几个新字段**到不了后端上传端**。

---

## 四、实测佐证的 DOM 片段（关键）

```
谁可以看:
<div class="container-OZ8FUX">
  <label class="radio-d4zkru" data-checked="true"...><input type="checkbox" class="radio-native-p6VBGt" value="0"><svg.../><span>公开 </span></label>
  <label class="radio-d4zkru" data-checked="false"...><input type="checkbox" class="radio-native-p6VBGt" value="2"><span>好友可见 </span></label>
  <label class="radio-d4zkru" data-checked="false"...><input type="checkbox" class="radio-native-p6VBGt" value="1"><span>仅自己可见 </span></label>

保存权限:
<div class="download-content-Lci5tL">
  <label class="radio-d4zkru" data-checked="true"...><input ... value="1"><span style="color:var(--color-primary);">允许 </span></label>
  <label class="radio-d4zkru" data-checked="false"...><input ... value="0"><span>不允许 </span></label>

关联热点:
<div class="semi-select semi-select-single semi-select-filterable" ...>
  <span class="semi-select-selection-text semi-select-selection-placeholder">点击输入热点词</span>

添加标签(挂载内容) → 选项实测: 位置 / 影视演艺 / 小程序 / 标记万物
<div class="anchor-container-hgj7gj"><div class="semi-select select-lJTtRL semi-select-single"...><span class="semi-select-selection-text"><div data-code="-11" class="select-dropdown-option-video">位置</div></span>...

添加合集:
<div class="mix-sel-wrap-X7ee1N">
  <div class="sel-area-uXj3oO">
    <div class="semi-select select-mix-type-G9iqb2 semi-select-single"...><span class="semi-select-selection-text">合集</span>
    <div class="semi-select select-collection-nkL6sA semi-select-single"...><span class="semi-select-selection-text"><div>请选择合集</div></span>

封面卡片:
<div class="coverControl-CjlzqC" style="margin-right: 8px; width: 90px;"><div class="cover-Jg3T4p"><div class="title-wA45Xd">选择封面</div></div><div class="controlContainer-psV7_j"><div class="cover-tip-YkBvmu">横封面4:3</div></div></div>
<div class="coverControl-CjlzqC" ...><div class="cover-tip-YkBvmu">竖封面3:4</div></div>  (第2张)
<div class="recommendContainer-xwwJ2i"><div class="recommendTitle-aEUy6n">Ai智能推荐封面生成中...</div><div class="recommendCoverContainer-S5XRoQ">...
```

> 观测产物（真实 DOM/截图）保留在 `prism_backend/_edu_obs/`
> - `PUBLISH_PAGE.html`（完整发布页 DOM，1.8MB）
> - `PUBLISH_PAGE_full.png` / `PUBLISH_PAGE_top.png`（整页/首屏截图）
> - `obs_anchor_options.html` / `obs_collection_options.html` / `obs_hotspot_options.html`（各下拉展开后的 DOM）
#### 5.6 视频预览功能提示（真实补测）

- **提示文案**：`视频素材已按原始分辨率上传，为保证预览体验，视频会被压缩预览，实际播放时根据环境自动选组最佳分辨率播放。`
- **关闭入口**：真实页面按钮 `我知道了`，AX 实测为 `按钮 我知道了`；本次点击后提示从可访问性树消失。该提示只负责说明预览策略，不应阻断上传或发布流程。

#### 5.7 话题确认键盘语义（补正）

- **正确流程**：点击 `#添加话题`，在简介富文本编辑区输入 `#` 加关键词；候选出现后，必须按空格或回车确认候选，页面才会把它变成真正的话题节点。
- **错误流程**：直接把包含 `#麦田` 的字符串写入富文本值，只是普通字符，不代表话题已绑定；自动化不得用普通 `set_value` 代替点击、输入和确认键。

#### 5.8 视频上传失败与重新上传

- **流程要求**：检测到 `上传失败` 后不能继续填表或发布，必须进入「重新上传」分支，重新选择同一个视频，等待上传完成后再继续标题、话题、封面和扩展信息。
- **现有落点**：`main_refactored.py` 的 `handle_upload_error(page)` 已通过上传控件重新设置 `self.file_path`，并由 `upload()` 的视频上传等待循环调用。
- **状态校验**：失败态只记录为失败；重新上传后必须再次看到上传完成标志（当前实现使用真实页面的「重新上传」控件出现作为完成信号），否则超时退出，不能伪报成功。

#### 5.9 图文发布入口（真实页面补测）

- 首页顶部黑色「作品发布」按钮展开后，真实可选入口为：`发布视频`、`发布图文`、`发布全景视频`、`发布文章`。
- 点击 `发布图文` 后进入真实地址 `/creator-micro/content/upload?default-tab=3`，页面显示页签 `发布视频 / 发布图文 / 发布全景视频 / 发布文章`，当前选中 `发布图文`。
- 图文页提供两种进入上传动作：点击中央上传区域，或点击 `上传图文`；页面同时支持把图片文件直接拖入上传区域。最多支持上传 35 张图片，支持 jpg/jpeg/png/webp，不支持 gif；单张图片文件大小不超过 50MB。
- 另有未完成草稿提示：`你还有上次未发布的图文，是否继续编辑？`，入口为 `继续编辑`，放弃入口为 `放弃`。这些入口必须在图文自动化开始前处理，不能误覆盖草稿。
- 创作者中心主页也有独立的「作品发布」区域，其中包含卡片 `发布图文`；本次真实点击后进入同一地址 `/creator-micro/content/upload?default-tab=3`，并重新显示图文上传页与草稿提示。由此确认：下拉菜单、上传页页签、主页发布卡片是多个入口版本，最终落到同一图文上传流程。
- **入口回退规则**：若直链 `/creator-micro/content/upload?default-tab=3` 不能访问或页面主体未加载，回退到创作者中心主页，点击左上方黑色 `作品发布` 按钮，在下拉中点击 `发布图文`；若只进入上传容器，再点击顶部 `发布图文` 页签。主页卡片 `发布图文` 也可作为等价回退入口。每一步都必须重新读取页面状态，确认已出现图文上传区域后才继续。
- **入口失败记录**：不能把 URL 可输入当作访问成功；必须确认页面出现 `图片格式`、`图片大小`、`图片比例` 或 `上传图文` 等图文页内容。未出现这些内容时记为“入口未加载”，继续使用主页菜单回退，不填写或发布。

#### 5.10 图文发布页当前实测记录（2026-09-02）

- 已用登录态进入真实地址：`https://creator.douyin.com/creator-micro/content/upload?default-tab=3`。
- 首屏真实可见控件：`发布视频`、`发布图文`、`发布全景视频`、`发布文章`；上传入口文字为 `点击上传 或直接将图片文件拖入此区域`，按钮为 `上传图文`。
- 真实页面提示：`图片格式 推荐jpg、jpeg、png、webp格式，不支持gif格式`、`图片大小 图片文件大小不超过50MB`、`图片比例 不建议宽高比例超过1:2，推荐图片宽高比例：3:4、4:3`。
- 页面出现过草稿提示：`你还有上次未发布的图文，是否继续编辑？`，操作为 `继续编辑` / `放弃`；这是页面状态，不应自动误选。
- **尚未确认**：本轮 Computer Use 运行时未暴露可用点击/文件选择器接口，因此未声称已上传图片，也未把图文表单内部选择器写成确定规格。后续必须从真实上传成功后的 DOM 继续记录标题、正文、话题、BGM、封面/排序、位置、挂载内容、合集、声明、热点、可见性、保存权限、定时及商品。
- 图文上传器已接入与视频页同名的 best-effort 配置阶段；图文页的实际 DOM 若不一致，只记日志并跳过，不能记录为成功，待真实 DOM 补测后再收紧选择器。
- **话题输入硬约束**：禁止把 `#麦田 #影像记录 #深圳` 作为一整串复制/粘贴或一次性 `type_text`。必须对每个话题分别执行：逐字输入 `#麦田` → 按一次空格确认 → 逐字输入下一个话题 → 再按一次空格；不得按 Enter、不得等待或点击候选。
- **空格前置校验**：输入后必须先读取编辑器文本，确认当前话题完整出现（例如末尾确实是 `#麦田`）；若只出现 `#` 或中文字符缺失，立即停止，不得按空格。

##### 图文话题最终实测输入协议（严格）

图文页已验证成功的操作协议如下，后续实现不得偏离：

1. 直接点击作品描述编辑框；严禁点击 `#添加话题`，该入口会自动插入井号并导致重复。
2. 用正常键盘输入一个 `#`。
3. 只粘贴当前话题文字，不带井号，例如只粘贴 `麦田`。
4. 重新读取编辑器内容，必须确认出现完整的 `#麦田`；未出现完整话题时禁止按空格，禁止继续下一个话题。
5. 确认后只按一次空格，再重复步骤 2–4 输入下一个话题。
6. 禁止一次性粘贴多个话题；禁止把 `#` 与中文话题文字作为一整串粘贴；禁止按 Enter；禁止等待或点击候选。

本次真实验证结果：`#麦田`、`#影像记录`、`#深圳` 均按上述协议成功确认，页面显示为 `# 麦田 # 影像记录 # 深圳`。

#### 5.11 图文表单真实点击补测

使用测试图 `wheat-cover.jpg` 完成真实文件选择后，页面进入：
`/creator-micro/content/post/image?default-tab=3&enter_from=publish_page&media_type=image&type=new`。

| 功能 | 真实入口/控件 | 真实结果 |
|---|---|---|
| 标题 | 文本栏 `添加作品标题` | 成功填写 `麦田里的风景`，显示 `6 / 20` |
| 正文/话题 | 文本输入区；页面显示 `#添加话题`、`@好友` | 成功写入 `#麦田 #影像记录 #深圳`；页面出现真实推荐话题列表 |
| 图片 | `已添加1张图片`、`继续添加`、`编辑图片` | 上传成功，页面显示 `已添加1张图片` |
| 位置 | 点击 `输入相关位置，让更多人看到你的作品` 后出现文本栏 | 输入 `深圳市南山区腾讯`，真实候选为 `南山区腾讯滨海大厦` 等；点击后页面显示该地点 |
| 封面 | `编辑封面` → `设置封面`，标签 `选择封面 / 上传封面` | 点击 `上传封面` 后真实占位为 `点击上传 或直接将文件拖入此区域`；按钮为 `确定 / 取消` |
| 合集 | `添加合集` / `不选择合集` | 入口已在表单真实出现，本轮未强选合集 |
| 自主声明 | `请选择自主声明` | 入口已在表单真实出现，本轮未强选 |
| 音乐 | `选择音乐`、`点击添加合适作品风格音乐` | 入口已在表单真实出现 |
| 关联热点 | `关联热点` → `点击输入热点词` | 入口已在表单真实出现 |
| 谁可以看 | `公开`、`好友可见`、`仅自己可见` | 三个真实复选控件均出现，默认 `公开` |
| 保存权限 | `允许`、`不允许` | 两个真实复选控件均出现，默认 `允许` |
| 发布时间 | `立即发布`、`定时发布`、`快速填写` | 真实控件均出现，默认 `立即发布` |

本轮停在发布按钮之前，没有提交公开发布。图文页真实 DOM 已确认；尚未确认的字段仍不得用视频页选择器冒充。

补充：本轮点击图文页 `不选择合集` 后，真实下拉列表只返回 `不选择合集`，没有可选合集候选；这应记录为“当前账号无可用合集”，不能用 mock 候选填充。

#### 5.12 图文自主声明与扩展音乐真实补测

- 点击 `自主声明 / 请选择自主声明` 后，真实弹窗标题为 `对作品内容添加声明`，说明为 `可在作品发布前添加声明，帮助他人减少困惑`。
- 真实单选项完整枚举：`内容由AI生成`、`内容为个人观点或见解`、`内容为转载信息`、`内容含营销推广信息`、`虚构演绎，仅供娱乐`、`无需添加自主声明`。按钮为 `取消`、`确定`；未选择时 `确定` 为 disabled。
- 本轮点击并确认 `内容由AI生成`，返回表单后真实显示 `自主声明 内容由AI生成`。
- 点击扩展信息 `选择音乐` 后，真实音乐面板出现：`搜索音乐`、`推荐`、`热门榜`、`收藏`、`飙升榜`、`原创榜`，分类包括 `卡点`、`纯音乐`、`旅行`、`DJ`、`搞笑`、`流行`、`伤感`；候选包含 `自带流量的音乐 🌈越努力，越幸运` 等，并显示时长与使用人数。
- 音乐面板底部真实提示：`音乐封面以发布后播放页面展示为准`。本轮记录了候选和面板入口，未把候选名称写成已应用状态。
