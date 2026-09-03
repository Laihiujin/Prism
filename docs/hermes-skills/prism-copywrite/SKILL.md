---
name: prism-copywrite
description: "Prism 标题/话题生成技能：给出各平台（抖音/小红书）的「网感」标题与话题规则、生成调用方式与自检标准，让发布标题更符合平台调性。"
version: 1.0.0
author: Prism
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Prism, copywrite, title, 标题, topic, 话题, douyin, xiaohongshu]
    related_skills: [prism-project-layout]
prerequisites:
  commands: [prism]
---

# Prism 标题/话题生成（网感 · 平台差异化）

Prism 是多平台内容编排与发布项目。本技能给出 **抖音** 与 **小红书** 的「网感」标题 + 话题
生成规则：每个平台的标题钩子、字数上限、话题组合、语气与合规自检。目标是让标题在信息流里
**自然、可停留、像"人"在说**，而不是机器腔、模板腔。

> 先读 `prism-project-layout`（项目布局 / API / CLI / MCP 工具），再按本技能的规则生成标题与话题。

## 1. 生成入口

标题 + 话题由 AI 生成并写入素材。调用方式：

- **后端 API**：`POST /api/v1/files/batch-generate-metadata`
  - body：`{ "file_ids": [..], "force_regenerate": false, "platform": "douyin" | "xiaohongshu" | "tiktok" | 空, "language": "zh" | "en" | "bilingual" | 空 }`
  - 返回每条的 `ai_title` / `ai_description` / `ai_tags`。
- **Hermes MCP 工具**：`generate_ai_metadata`（`file_ids` + `force_regenerate` + `platform` + `language`），
  平台与语言通过同名字段透传。
- **交互生成**：`POST /api/v1/ai/chat`（`generate_title` / `generate_tags` / `generate_title_tags`），
  在 `platform` slot 传入平台。

`platform` 传空时走通用生成；传 `douyin` / `xiaohongshu` / `tiktok` 时启用本技能的平台规则。
`language` 控制输出语言：`zh` 中文 / `en` 英文 / `bilingual` 中英双语；**TikTok 默认 bilingual**。

## 2. 平台速查表（红线：字数/个数不可超）

| 平台 | 标题字数(红线) | 话题个数(红线) | 字段布局 | 语气基调 |
|---|---|---|---|---|
| 抖音 douyin | 10–20 字 | 最多 4 个 | 标题 + 描述（描述带 #话题） | 短促强钩子，情绪/反差优先，口语 |
| 小红书 xiaohongshu | 10–20 字 | 最多 10 个 | 标题 + 描述（描述带 #话题） | 笔记标题，关键词清晰，审美克制 |
| TikTok | caption（不单独卡标题） | 最多 5 个 | 标题/描述合并（caption + #话题） | 面向海外，简洁、开头即钩子，**默认中英双语** |

> 红线取自**生产上传器的硬上限**（超过会卡发布）：抖音标题 `len>20` 抛错、小红书标题填空取
> `[:20]` 且标签 `max_tags=10`、快手标签 `[:3]`；B站/YouTube 等用
> `myUtils/platform_metadata_adapter.py` 的字数上限（B站 80、YouTube 100）。

## 3. 抖音（douyin）网感规则

- **钩子**：开头即冲突 / 结果 / 悬念 / 情绪，5 秒内给出"为什么要看"。
  - 反差：`这就是 X 的代价吗`、`离谱但合理`
  - 悬念 / 结果：`一开场就 X`、`X 直接拉满`
  - 情绪 / 吐槽：`他怎么这么 X`、`看完我沉默了`
- **口语化**：像镜头前的人在说话，不要书面腔；可用疑问、感叹。
- **不堆形容词**：至少包含 1 个可验证信息点（人物 / 行为 / 结果 / 场景 / 情绪）。
- **话题**：`1 个品类/IP 标签 + 1 个内容形态标签 + 1–2 个细分标签`，共 ≤4 个；
  放在描述里以 `#话题` 呈现，别把多个话题连成一串粘死。
- **规避**：不做标题党到"货不对板"；同一视频同一账号只发一次，标题不得与上次重复。

## 4. 小红书（xiaohongshu）网感规则

- **像笔记标题**：关键词清晰、能一眼看懂"讲什么"，审美克制、不浮夸。
  - 结构参考：`主体 + 场景/方法 + 结果/承诺`，如 `新手也能学会的 X 笔记`、`X 的 3 个技巧`。
  - 可轻微带一点温度：`没人告诉你的 X`、`终于搞定 X 了`，但不虚假。
- **字数**：10–20 字（≤20 字上限）。
- **话题组合**：`泛流量话题（人群/场景）+ 垂直话题（品类）+ 细分话题（具体）》`，共 ≤10 个；
  描述里以 `#话题` 呈现，避免全是大词。
- **语气**：像身边朋友分享，可适度用 emoji（正文/小标题），但标题保持克制、不加夸张营销词。
- **封面/排版**：标题留白、色调统一（见 `prism-project-layout` 的封面生成约定）。

## 5. TikTok（中英双语）规则

- **默认双语**：标题形如 `中文标题 | English Title`，话题同时含中文 + 英文标签，
  兼顾国内运营与海外搜索；`language=en` 时纯英文，`language=zh` 时纯中文。
- **面向海外观众**：开头即钩子 / 结果 / 好奇心；语言简洁、少成语、少生僻词。
- **话题**：1 个品类 + 1 个内容形态 + 1–2 个细分，≤5 个，含 `#english_tag`。
- **字段**：TikTok 为合并 caption（标题/描述 + #话题），无独立短标题栏。

## 6. 输出规范与自检

一条完整的标题+话题输出至少包含：

- `best_title`（或 `ai_title`）：平台字数内、有钩子、含信息点。
- `candidates`（可选交互时）：3 个候选，结构或信息点明显不同。
- `ai_tags`：≤ 平台上限、去重、每个以 `#` 开头（系统写入时自动补 `#`，不要在字段里返 `#`）。
- 差异度：多平台同素材时，**标题不得完全相同**，差异 >10%（结构或信息点换一个）。

生成后自检（不合规内部重写再输出）：

1. 标题字数在平台红线内（抖音 ≤20 / 小红书 ≤20 / B站 ≤80 / YouTube ≤100）。
2. 话题数不超过平台上限（抖音 4 / 小红书 10 / 快手 3 / B站 12），且不重复、不含空格。
3. 不含 Emoji（标题 / 描述）；不使用英文引号包裹标题。
4. 不做虚假承诺、不编造数据 / 排名 / 评价；避免营销敏感词（领取 / 金币 / 福利 / 礼包 / 首充）。
5. 标题里至少有 1 个可验证信息点，拒绝"空泛堆形容词"。

## 7. 与发布链路的协作

- 生成仅产出 **文案**；发布仍走 `prism <platform> upload-video --account <name> --title ... --tags ...`。
- 快手 / B站 / 视频号 / TikTok / YouTube 的字段布局与字数见 `platform_metadata_adapter.py`；
  本技能当前聚焦抖音 + 小红书，其余平台沿用通用规则。
- 若账号未验证（`prism <platform> check --account <name>` 失败），先不发布，先补标题/话题。
