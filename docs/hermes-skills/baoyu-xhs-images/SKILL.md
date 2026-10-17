---
name: baoyu-xhs-images
description: 制作小红书封面及系列图文卡片，提供内容拆页、风格布局、逐页提示词和一致性检查；在 Prism 中按封面工具能力生成。
license: MIT
---

# 小红书封面与系列卡片（Prism 适配）

单张首图也适用；用户只要封面时不要自动扩成整套图文。已有创作授权时自行选择合理默认，用户要求详细选项时再展示方案。

## 内容与拆页

读取 `prism-social-content`，查看素材及用户参考。分析对象、问题、可证明的价值、可视觉化的信息，按需读 [分析框架](references/workflows/analysis-framework.md)。
先提炼一个首图信息钩子；教程按操作顺序，对比按统一维度，清单按清楚分类。每页只解释一个主题，标题与正文分层。
系列图的建议结构为“封面 → 必要的内容页 → 总结”，页数由内容和用户要求决定，不补写不存在的经历、数据或效果保证。
输出逐页大纲：页码、角色、准确标题/正文、布局、主体、强调元素。详细模板见 [outline-template](references/workflows/outline-template.md)。

## 风格、布局、配色一起选择

读取 [风格预设](references/style-presets.md)，按内容选择，例如教程用清晰笔记风，生活方式用柔和留白，强对比清单用醒目图形。
按需读取 `references/presets/`、`references/palettes/` 对应资源，不一次加载所有风格。
首图通常采用稀疏布局，内容页按信息选 balanced、list、comparison、flow 或 dense；密度不能牺牲手机阅读。
具体设计读 [画布](references/elements/canvas.md)、[文字](references/elements/typography.md)、[装饰](references/elements/decorations.md)、[图像效果](references/elements/image-effects.md)。
系列固定：主色/强调色、字体气质、标题位置、页码样式、角色与图标画法；不同页调整信息结构，不随机更换视觉语言。

## 生成与一致性

先为每页保存独立完整提示词到 `prompts/NN-role.md`，写清画布、逐字文案、布局和统一视觉规范。单封面执行 `baoyu-cover-image` 的 Prism 生成与检查流程。
当前 Prism 的 `generate_cover` 绑定 `file_id`，生成的是素材封面库候选，比例仅 `3:4` / `4:3`；它不是图文多页管理接口，也不支持把任意上一页图片路径作为参考参数。
因此：

- 单封面可直接生成、检查并选用。
- 用户要求多页时先交付大纲与全部逐页提示词；如果用户也要求用现有工具出图，可依次生成封面库候选并保留每页路径对应表，只选首图，不轮流覆盖素材已选封面。
- 同一素材的 `use_first_frame=true` 保持人物/产品依据；风格、配色和布局规范完整重复到每页提示词中。不能声称这是上游“首图参考链”，也不能保证仅靠文字实现角色完全一致。
- 后续只有工具目录明确提供图片引用/图文多页能力时，才采用上游首图锚定后逐页传参的方式。不能借此安装新后端或虚构接口。

生成每页后检查准确文字、顺序、内容依据、缩略图可读性及系列一致性。失败仅针对该页修改提示词并重试一次；保留原候选，报告未完成页。
不要把封面库多张候选说成已创建图文发布包或已发布笔记。

## 交付

单首图给出准确文案、风格布局、提示词路径、实际图片路径和选用状态。
系列给出页码/角色/准确文案/提示词/实际图片路径对应表，标明哪些只有方案；说明需要后续图文素材导入或上传的部分。不得将方案完成报告为成品完成。

## 参考来源与许可

改编自 JimLiu/baoyu-skills，MIT，固定版本及版权见 [SOURCE.md](SOURCE.md)、[LICENSE](LICENSE)。上游完整工作流见 [upstream-SKILL](references/upstream-SKILL.md)；平台执行遵守本入口的 Prism 能力边界。
