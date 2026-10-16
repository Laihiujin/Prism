---
name: prism-social-content
description: 为抖音、B站、视频号、小红书制作差异化标题、简介、标签和封面，并通过Prism的MCP或CLI生成、选用封面。用于同素材多平台内容改编和发布准备。
---

# 四平台内容与封面工作流

先读 `prism-title-topic`，按项目实际上传器限制生成字段；按目标平台读取对应
`prism-publish-douyin/bilibili/channels/xiaohongshu`。平台推荐口吻是编辑策略，不是流量保证。

## 从素材到发布包

1. 读取视频描述、已有字幕或转录，查看代表性视频帧。简介不等于字幕；仅使用有依据的信息。
   缺少字幕时继续用已知内容写保守且准确的文案，不虚构视频中的观点、事件、数字或结论。
2. 每个平台产出一个发布包：`title`、`description`、`tags`、`cover_text`、`cover_prompt`，
   视频号另产出 `short_title`。至少在标题结构、强调信息或正文组织上体现平台差异。
3. 先内部拟定三种标题，选一个最贴合内容的版本。已有用户授权足以推进常规创作，
   不逐项询问标题、标签、色彩。若需用户扫码或输入验证码，完成其余准备后提示该具体操作。
4. 从视频实际人物、产品或场景中选一个视觉主体。封面只表达一个核心信息，
   大标题通常4–10字，手机尺寸可读。避免复杂小字、伪造人物表情和与视频无关的素材。
5. 封面提示词明确：主体、构图、色彩、表现形式、准确文字、比例、文字安全区。
   横竖封面分别设计构图，不能只把同一张图拉伸。最终比例服从发布器配置。
6. MCP调用 `generate_cover`（file_id、platform_name、aspect_ratio、prompt），
   取得job_id后调用 `get_cover_job`。成功后用 `list_material_covers` 找到cover_id，
   `select_material_cover` 选用；需要已有封面横竖裁切时调用 `adapt_material_cover`。
   CLI同名入口：`python prism_cli.py tool invoke <工具名> --json-file <参数文件>`。
7. 看实际生成图片，核对文字、主体一致性、可读性和裁切位置；失败要报告具体错误，
   不把只写了提示词说成已生成封面。只有用户授权发布时，才继续对应平台发布技能。

## 平台编排

| 平台 | 标题/正文 | 标签 | 封面 |
| --- | --- | --- | --- |
| 抖音 | 可验证结果或反差前置，口语简洁；正文补充场景或看点 | 品类+内容形态+具体主题，按项目限制，不蹭无关热点 | 一个主体与一句强信息，视觉与视频开头一致 |
| B站 | 主体+具体问题/方法/作品信息；简介交代范围、来源与看点，有依据才加章节 | 独立标签，兼顾分区、主题和具体对象 | 横向信息层次清晰，避免只有模糊情绪而没有内容信息 |
| 视频号 | 可信且易转述的首句，正文适合转给朋友；另做简洁短标题 | 描述内相关话题，按项目限制 | 清晰人物或场景，克制文案，竖屏裁切仍保留主体 |
| 小红书 | 对象+场景/问题+具体价值；正文可分段列步骤，不伪装亲身体验 | 搜索词+垂直主题+具体人群场景 | 竖向首图，单个重点、明显层次，教程卡片保持系列一致 |

不要把外部skill的标签数量、固定机器路径、模型或发布脚本覆盖到Prism。
不要把未经证明的CTR倍数、算法惩罚、限流结论当作平台事实。

## 外部参考

- [baoyu-cover-image](https://github.com/JimLiu/baoyu-skills/tree/main/skills/baoyu-cover-image)：封面设计维度。
- [baoyu-xhs-images](https://github.com/JimLiu/baoyu-skills/tree/main/skills/baoyu-xhs-images)：图文卡片系列。
- [小红书内容技能](https://github.com/vivy-yi/xiaohongshu-skills)：标题、标签、文案、封面分类；增长数据不直接采信。
- [抖音AI图文流程](https://github.com/NewAmorend/douyin-skills-pack)：信源、分析、写作、卡片流程，偏AI科技图文。
- [视频号上传技能](https://github.com/wangzhaobo168/wechat-channels-upload)：流程参考，含固定机器路径，未安装其脚本。

这些是研究参考，不是已安装或已执行的外部依赖。内容制作和发布使用Prism工具。
