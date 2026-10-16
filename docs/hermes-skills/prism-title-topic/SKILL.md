---
name: prism-title-topic
description: "Prism 标题/话题/封面文案生成技能：给出抖音、小红书、视频号、B站 四个平台的「网感」标题钩子、字数红线、话题组合、语气基调与封面文案规则，含生成调用方式与自检清单，让发布内容符合各平台调性。"
version: 2.0.0
author: Prism
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Prism, title, 标题, topic, 话题, 平台调性, douyin, xiaohongshu, channels, bilibili]
    related_skills: [prism-project-layout, prism-publish-douyin, prism-publish-xiaohongshu, prism-publish-channels, prism-publish-bilibili]
prerequisites:
  commands: [prism]
---

# Prism 标题/话题/封面文案生成（网感 · 平台差异化）

Prism 是多平台内容编排与发布项目。本技能给出 **抖音 / 小红书 / 视频号 / B站** 四个平台的
标题钩子、字数红线、话题组合、语气基调与封面文案规则，让同一份素材在四个平台各自「像人话」。

> 先读 `prism-project-layout`（项目布局 / API / CLI / MCP 工具），再按本技能的规则生成。
> 本技能**只产出文案**；发布仍走 `prism <platform> ...`（见 §10）。

## 0. 三条硬约束

1. **字数与个数红线不可超**（§2 表），超了会卡发布或触发上传器截断。
2. **不编造**：不虚构数字、排名、评价、资质、来源；不做「货不对板」的标题党。
3. **多平台同素材标题不得完全相同**，结构或信息点至少换一个（§8）。

## 1. 生成入口

标题 + 话题由 AI 生成并写入素材。调用方式：

- **后端 API**：`POST /api/v1/files/batch-generate-metadata`
  - body：`{ "file_ids": [..], "force_regenerate": false, "platform": "douyin" | "xiaohongshu" | "channels" | "bilibili" | ..., "language": "zh" | "en" | "bilingual" | 空 }`
  - 返回每条的 `ai_title` / `ai_tags`（**只出标题+标签，无描述**；描述是发布时独立字段）。
- **Hermes MCP 工具**：`generate_ai_metadata`（`file_ids` + `force_regenerate` + `platform` + `language`）。
- **交互生成**：`POST /api/v1/ai/chat`，请求体带 `platform` 与 `language`。

`platform` 传空时走通用生成；传具体值时启用本技能的平台规则（见
`prism_backend/ai_service/title_topic_generator.py` 的 `PLATFORM_GUIDANCE`）。
模型配置在设置页「标题生成 / 对话模型」（`config/llm_config.toml`），与 `/files` 批量同一配置源。

## 2. 平台速查表（红线：字数/个数不可超；只出标题+话题）

| 平台 | 标题上限 | 话题个数 | 钩子前置位 | 字段布局 | 语气基调 |
|---|---|---|---|---|---|
| 抖音 douyin | 视频 ≤30 / 图文笔记 ≤20（生成按 **20** 产出最稳） | ≤4 | 前 12 字 | 标题 + 描述（话题在描述里） | 短促强钩子，情绪/反差优先，口语 |
| 小红书 xiaohongshu | **≤20** | ≤10 | 前 12–15 字 | 标题 + 描述（含话题） | 笔记标题，关键词清晰，审美克制 |
| 视频号 channels | 描述框（标题合并）；**短标题 ≤16** | ≤4 | 前 12 字 | 单一描述框（描述+话题） | 偏正式可信；社交推荐：让转发者「有面子」 |
| B站 bilibili | **≤80**（推荐流卡片约显示 20–40） | ≤12（独立标签） | 前 15 字 | 标题 + 简介 + **独立标签** | 可稍长、更具体，分区黑话，忌堆字 |

> **红线来源（生产上传器实测，不是估计）**：
> - 抖音图文笔记：`len(title) > 20` 直接 `raise ValueError`；视频发布器 `title_input.fill(title[:30])`。
> - 小红书：`title_container.fill(self.title[:20])`，`max_tags = 10`（超出会卡死发布）。
> - 快手：`cleaned_topics[:3]`。
> - B站：`self.data.title = self.title[:80]`，独立标签 ≤12。
> - 视频号：短标题由 `format_str_for_short_title()` 自动派生 —— 去特殊字符、**截断到 16 字**、不足 6 字补空格。
> - 生成侧红线表：`prism_backend/ai_service/title_topic_generator.py::PLATFORM_META`。
> - 字段布局：`prism_backend/myUtils/platform_metadata_adapter.py::PLATFORM_CONFIGS`。

**铁律**：钩子必须落在「钩子前置位」之内 —— 折叠线之后的钩子等于没写。

## 3. 抖音（douyin）

- **钩子**：开头即冲突 / 结果 / 悬念 / 情绪，5 秒内给出「为什么要看」。
  - 反差：`这就是 X 的代价吗`、`离谱但合理`
  - 悬念 / 结果：`一开场就 X`、`X 直接拉满`
  - 情绪 / 吐槽：`他怎么这么 X`、`看完我沉默了`
- **口语化**：像镜头前的人在说话，不要书面腔；可用疑问、感叹。
- **不堆形容词**：至少含 1 个可验证信息点（人物 / 行为 / 结果 / 场景 / 情绪）。
- **话题**：`1 个品类/IP 标签 + 1 个内容形态标签 + 1–2 个细分标签`，共 ≤4 个；
  放在描述里以 `#话题` 呈现，别把多个话题连成一串粘死。
- **与画面一致**：标题即钩子，要和视频前 3 秒口播/画面一致（标题党是判重灾区，短期流量长期限流）。
- **规避**：不做「货不对板」；同一视频同一账号只发一次，标题不得与上次重复。

## 4. 小红书（xiaohongshu）

- **像笔记标题**：关键词清晰、一眼看懂「讲什么」，审美克制、不浮夸。
  - 结构参考：`主体 + 场景/方法 + 结果/承诺`，如 `新手也能学会的 X 笔记`、`X 的 3 个技巧`。
  - 可轻微带温度：`没人告诉你的 X`、`终于搞定 X 了`，但不虚假。
- **字数**：**10–20 字**（≤20 是硬上限，超了被折叠）。
- **话题组合**：`泛流量话题（人群/场景）+ 垂直话题（品类）+ 细分话题（具体）`，共 ≤10 个；
  避免全是大词，不做与内容无关的蹭热点（算法会惩罚）。
- **语气**：像身边朋友分享；正文/小标题可适度用 emoji，**标题保持克制**，不加夸张营销词。
- **可评论点**：标题可埋一个提问式钩子，配合首图与标题呼应，提高收藏与评论。
- **搜索意图**：优先用读者会真的敲进搜索框的「人话」词，而不是内部术语或行业黑话。

## 5. 视频号（channels）

- **只有一个描述框**（标题与话题合并呈现），**没有独立标题栏** —— 第一句必须自己承担钩子。
- **短标题**：上传器从标题自动派生（去 `《》“”:+?%°` 以外的特殊字符、**≤16 字**、不足 6 字补空格）。
  需要精确控制时用发布参数 `short_title` 显式传入（见 `prism-publish-channels`）。
- **语气**：**偏正式、可信，减少夸张**。视频号是社交推荐 —— 标题要让**转发者「有面子」**：
  像「值得转给朋友看」的内容，而不是「low 的标题党」。深度好文既视感优于情绪叫卖。
- **话题**：≤4 个；描述里以 `#话题` 呈现。
- **`category`**：发布参数，用于**原创类型 / 声明原创**流程（`div.original-type-form` 的「原创类型」），
  不是内容分类标签，别和话题混用。
- **规避**：不用「震惊体」；不用需要解释才懂的内部梗（转发者无法转述）。

## 6. B站（bilibili）

- **允许更长、更具体**：上限 80 字，但**推荐流卡片只显示约 20–40 字** ——
  按「显示位」而不是「允许上限」放钩子，前 15 字必须成立。
- **分区黑话**：标题要「懂行」，让同好一眼认出是自己人（整活 / 名场面 / 硬核 / 考据 / 实测）。
- **忌温差**：B站分区审核对「标题与内容不符」容忍度最低；标题不要承诺内容给不出的东西。
- **标签是独立字段**（不是话题）：`tags` 数组 ≤12 个，发布时走 `--tag`（逗号分隔），
  和标题/简介分开填，不要塞进简介。
- **简介**：可写背景、时间线、参考资料；简介**不支持**话题标签语法。
- **必填**：`tid`（分区 ID）。分区决定推荐池，选错分区比标题差更伤流量。

## 7. 封面文案（四平台差异化）

封面文案不是标题的复制品 —— 不同画布有不同的注意力预算。

| 平台 | 画布 | 封面文案规则 |
|---|---|---|
| 抖音 | **竖封 3:4** 主用 / 横封 4:3 | 大字竖排、单点强钩子；可用「AI 智能推荐封面」，也可 `cover_orientation` + `cover_file` 指定 |
| 小红书 | **1080×1440（3:4）** | 大字 **4–10 个中文字**；主标题占 60–75% 文字权重，缩到 ~80px 宽仍要认出承诺 |
| 视频号 | 竖版封面 | 与标题互补：封面给「面子」，标题给信息；不要重复标题全文 |
| B站 | 16:10（上传后自动裁剪） | 封面是「分区名片」：留出标题区、主体唯一、避免细碎文字 |

**封面文案写法（通用）**：

1. **另写一句短承诺**，不是长标题的压缩版。长标题塞进方图会变成一堵字墙 ——
   抽出「核心动词 + 核心对象」，压到 4–10 字。
   - `第三次进山，装备比上一次轻 3.4kg` → `装备减重 3.4kg`
   - `开源了一个 Skill，让 AI 接管你屏幕边那张便签纸` → `AI 接管便签纸`
2. **唯一视觉锚点**：人脸/主体、已确认的大号数字、真实截图、前后对照，四选一。
   数字型只能用**已确认的数字**；截图型只能用**真实且已授权**的截图。
3. **三层文字层级**：主标题 60–75% / 支持行 20–30% / 角标 5–10%。
4. **事实边界**：没有主体、证据或可确认对照时，用**事实中性骨架**（大标题 + 抽象几何 + 留白），
   不暗示具体人物、业绩或案例。
5. **对比度**：主标题与背景对比 ≥4.5:1，缩略图目标 7:1。

## 8. 一稿多发工作流

```
内容内核（一句话，<20 字：这是谁、得到了什么 / 避开了什么坑）
→ 按平台砍字数（30 → 20 → 16，降级改写，不许升级注水）
→ 换平台语气 / 黑话（内核不变，只换表达）
→ 逐平台过合规自检（§9）
→ 每平台选 Top1 发布
```

- **至少改 30% 的字**：同一标题全平台通发会被判「重复内容」。
- **医疗/金融类不许跨平台直发**：各平台审核尺度差异最大，每平台单独过一遍。
- **带联系方式的标题只发允许的平台**（微信号/二维码暗示语在抖音、小红书属导流违规）。
- **时效性标题写绝对日期**（`10 月 11 日`），别用「今天/本周」—— 跨平台分开发布会过期。

## 9. 输出规范与自检

一条完整的标题+话题输出至少包含：

- `best_title`（或 `ai_title`）：平台字数内、有钩子、含信息点。
- `candidates`（可选交互时）：3 个候选，结构或信息点明显不同。
- `ai_tags`：≤ 平台上限、去重、每个以 `#` 开头（系统写入时自动补 `#`，不要在字段里返 `#`）。
- `cover_copy`（若本次要出封面）：按 §7 **另写一句**，不复制标题。
- 差异度：多平台同素材时，**标题不得完全相同**，差异 >10%（结构或信息点换一个）。

生成后自检（不合规内部重写再输出）：

1. 标题字数在平台红线内（**抖音 ≤20 / 小红书 ≤20 / 视频号短标题 ≤16 / B站 ≤80**）。
2. 话题数不超过平台上限（**抖音 4 / 小红书 10 / 视频号 4 / B站 12**），且不重复、不含空格。
3. 钩子在「钩子前置位」之内（抖音前 12 / 小红书前 12–15 / 视频号前 12 / B站前 15）。
4. 不含 Emoji（标题 / 描述）；不使用英文引号包裹标题。
5. 不做虚假承诺、不编造数据 / 排名 / 评价；避免营销敏感词（领取 / 金币 / 福利 / 礼包 / 首充）。
6. 标题里至少有 1 个可验证信息点，拒绝「空泛堆形容词」。
7. 封面文案是另写的一句短承诺，不是标题的压缩版；数字 / 截图有事实依据。

## 10. 与发布链路的协作

- 生成仅产出**文案**；发布走 `prism <platform> upload-video --account <name> --title ... --tags ...`。
- 各平台字段布局与字数：`myUtils/platform_metadata_adapter.py`；
  生成侧红线：`ai_service/title_topic_generator.py::PLATFORM_META`。
- 平台发布参数细节见对应技能：`prism-publish-douyin` / `prism-publish-xiaohongshu` /
  `prism-publish-channels` / `prism-publish-bilibili`；快手 / TikTok / YouTube / 百家号沿用通用规则。
- 若账号未验证（`prism <platform> check --account <name>` 失败），先不发布，先补标题 / 话题。

## 11. 参考来源与许可

本技能的平台调性结构参考了以下开源 Agent Skills（只迁移方法，未复制其专属资产）：

| 来源 | 许可 | 借鉴内容 |
|---|---|---|
| `lhg-plugs/lhg-headline`（lhg-hl-platform / lhg-hl-formula） | MIT | 多平台字数表 + 钩子前置位 + 平台黑话 + 一稿多发改写四步法 |
| `jackbauerxu/workbuddy-xhs-skills`（wb-xhs-cover-anchor） | 无 LICENSE 文件（仅本地参考，勿再分发） | 封面锚点、三层文字权重、80px 缩略图 QA、事实边界 |
| `op7418/guizang-social-card-skill`（references/platform-specs、title-shortener） | AGPL-3.0（**勿直接搬运代码**） | 小红书 1080×1440 安全区、方图短标题抽取法 |
| `JuneYaooo/self-media-compliance-review` | MIT | 平台违规风险审核的参考框架 |

本地克隆位置：`E:\Laihiujin\Git\`（`--depth 1`，固定提交号如下）：

| 仓库 | 提交 | 克隆日期 |
|---|---|---|
| `lhg-headline` | `fc6f6a0` | 2026-10-10 |
| `workbuddy-xhs-skills` | `8070632` | 2026-08-01 |
| `guizang-social-card-skill` | `cf4b810` | 2026-07-02 |
| `self-media-compliance-review` | `729665f` | 2026-10-09 |

已装进 Hermes（`~/AppData/Local/hermes/skills/social-media/`）：
`lhg-hl-platform` / `lhg-hl-formula` / `lhg-hl-compliance` / `lhg-hl-score` /
`guizang-social-card-skill` / `self-media-compliance-review`（均走 hub 追踪，可 `hermes skills update`）/
`wb-xhs-*` 10 个（手动复制，本地技能）。

**安装坑（`hermes skills install <raw url>` 只取 SKILL.md + 顶层 references）**：

- `self-media-compliance-review`：安装器没带 `references/cases/`，但 SKILL.md 明确要求读它 ——
  已从本地克隆补入（7 个平台案例，`cases/xiaohongshu.md` 单文件 340KB）。
- `guizang-social-card-skill`：已从克隆补入完整 `assets/`（2 个 HTML 模板 + 9 张背景 webp + `magazine-bg-webgl.js`），
  否则 SKILL.md 的「copy `assets/template-*.html`」步骤无法执行。
  **别再对它跑 `hermes skills update`** —— 会覆盖掉手工补入的 assets。
- 上游 SKILL.md 引用的 `assets/hero-mountain.jpg`、`assets/ui-pulse-card.png`、`assets/SOURCES.md`
  在上游仓库中并不存在（上游断链，非本地安装问题）。
