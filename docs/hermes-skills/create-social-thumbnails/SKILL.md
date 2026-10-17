---
name: create-social-thumbnails
description: Create, adapt, or review high-CTR creator thumbnails and social-media covers for Xiaohongshu, WeChat Channels, YouTube, YouTube Shorts, and Douyin. Use for requests such as 自媒体封面, 爆款封面, high-CTR thumbnail, or click-driving cover from real photos, screenshots, products, or style references; preserve real assets exactly, avoid AI-generated lookalikes, and never promise virality or performance.
---

## Prism 项目覆盖规则（优先于下方上游默认值）

本技能作为社媒视频封面制作入口，必须同时读取 `create-social-thumbnails` 的素材保真、构图与 QA 参考。`video-thumbnail` 补充视觉钩子、标题与画面的互补关系及横竖独立构图。宝玉封面技能退为文章/插画参考；CineForge 只辅助用户要求的电影感方向，不改变产品或将任务替换为产品广告海报。

- 用户给过的平台、比例、数量、风格与是否出镜即为已回答，不重复询问。明确的 3:4、4:3 优先于上游 16:9、9:16 默认；12 张不扩成每次四候选。用户无人物要求时不自动加入人物、代言人或陌生脸。
- 产品图、Logo、截图属于 exact-use，风格截图属于 style-only，背景属于 generatable。先找本地原始素材（Everything 可用时优先），核对型号与用户确认图；文件名不能替代目视核对。原图不存在才说明具体缺口。
- 记录产品锁定项：轮廓比例、组件数量、镜头/按键/屏幕/旋钮位置、字标、颜色与表面材质。AI 的“相似产品”不算保真。若生成改变这些结构，淘汰该图，使用原图裁切/蒙版/缩放合成；不能仅反复加强提示词后交付失真产品。输出应说明真实使用了哪些原始资产。
- 先用用户提供的同品牌社媒参考提取标题比例、画面密度、场景类别、产品占比与 Logo 尺寸，不把每张图都做成“Logo + 长卖点 + 产品并排”的目录海报。不凭空制造使用效果、测试结论或投放范围。
- 根据已有授权完成一张有完成度的主稿，按源图比对结构、逐字核对文案/Logo、约 160px 和 320px 缩略图检查。核心产品或字标失真即不通过，不批量扩展失败方向。
- 默认使用宿主内置图像生成能力；不执行上游安装命令、不擅自切换 Gemini、不索要其 API Key。需要精确产品/Logo 合成时保留原始像素；生成结果不能保证这一点时使用可验证的确定性合成流程，并遵守宿主工具约束。
- Prism 封面工具当前 `generate_cover.aspect_ratio` 仅支持 3:4 和 4:3，且没有任意本地图像引用参数。不能声称其已经引用用户原图。需要本地参考图的任务按宿主实际支持的工具完成；不要为硬套 Prism 工具放弃原图保真。
- 只有实际生成、看图检查并保存的文件才计入成品。按平台、版本、比例命名；横竖各自构图，交付精确比例、实际路径与尚未解决的问题。

上游完整方法、脚本和参考保留如下；版权与固定版本见 `SOURCE.md` 和 `LICENSE`。


# Create High-CTR Creator Thumbnails

Produce a platform-ready creator thumbnail that communicates the topic in roughly one second, remains legible at feed size, uses the user's real assets faithfully, and has a clear click-driving visual hierarchy. Treat “viral” or “爆款” as a creative objective, never as a guaranteed outcome.

## Route the request

1. Identify the target platform and content type. Treat the requested ratio as a separate choice: it may use a platform preset or a generic `1:1`, `4:3`, `3:4`, `4:5`, `6:7`, `16:9`, or `9:16` canvas.
2. Read [references/platform-specs.md](references/platform-specs.md) for the matching platform or ratio-only canvas and export preset.
3. If the user names a style ID, uses a natural-language style phrase, supplies a style reference, asks what styles are available, or needs a reusable prompt, read [references/style-catalog.md](references/style-catalog.md). A supplied style reference is the primary art-direction input: match its general title scale, density, subject ratio, background category, card rhythm, outline weight, and decoration language while using the user's own content.
4. Read [references/composition-patterns.md](references/composition-patterns.md) when adapting the selected style to supplied assets, creating variants, or reproducing the title-to-image gradient treatment.
5. Read [references/asset-integrity.md](references/asset-integrity.md) whenever the request includes user photos, product screenshots, brands, public figures, or a commercial-use claim.
6. Before delivery, follow [references/qa-checklist.md](references/qa-checklist.md).

## Intake

Collect or infer these inputs:

- target platform, content type, and requested ratio;
- a style name, style reference, or free-form visual description; a catalog ID `S01` through `S11` is optional;
- primary title and optional supporting text; when the user supplies only a topic, write three concise candidate hooks internally and select the strongest one instead of asking the user to fill every label;
- exact-use assets such as the user's portrait, real screenshots, products, or logos;
- style-only references;
- desired tone, brand colors, and output format;
- whether the user is requesting commercial-use clearance.

Do not block on non-critical omissions. Choose a sensible default and state it. Ask only when a missing title, required real asset, or rights-sensitive choice would materially change the result.

## Protect source fidelity

Classify every input before editing:

- **Exact-use asset:** preserve its actual content. Crop, mask, scale, color-correct, and composite it deterministically.
- **Style reference:** borrow only general layout, rhythm, contrast, or color direction. Do not copy protected artwork or treat the reference as a source asset.
- **Generatable support:** scene extension, generic shapes, arrows, highlights, and non-branded decoration may be generated when useful. If a real interface, room, product screen, or evidence image can establish the topic, reuse and extend it instead of inventing an unrelated abstract background.

Never redraw a real interface screenshot, product, document, data visualization, logo, or person when the user expects the original. Never create an AI lookalike as a substitute for the supplied portrait. If a cutout tool may alter the subject, compare the result with the source at face, hands, clothing, logos, and edges before using it.

## Build the composition

1. Create the exact target canvas before laying out content. Never stretch an existing cover to change ratios; recompose it.
2. Establish one dominant promise, one dominant subject, and one supporting proof area.
3. Keep the main title short enough to understand in roughly one second. For high-density creator covers, use two or three compact lines occupying roughly 35–45% of the canvas height, with alternating pale-yellow and white fill plus a very thick dark keyline. A chunky hand-painted/marker rhythm may be used for the main hook and large count; keep subtitles, labels, scores, and check items in a clean heavy sans/黑体.
4. Reserve UI-safe margins and avoid placing essential text or faces near edges.
5. For a collage beneath the title, place the real collage unchanged, then add a separate background-colored-to-transparent overlay above it. Do not bake fake screenshots into the gradient.
6. For a portrait-led cover, cut out the supplied person, keep recognizable features unchanged, and scale the half-body subject to 35–55% of the canvas. Place it in the lower half, let it bleed off an edge when appropriate, and add a pale-yellow or white contour plus shadow. Never put a usable cutout back inside a photo frame.
7. When exploration is requested, create up to three meaningfully different variants: text-led, face-led, and proof-led. Do not create superficial color-only variants.
8. Treat `S11 Creator Impact / 真人高密度大字` as the current flagship system. When it is selected or the user requests a dense bold-title portrait cover, read [references/signal-impact-system.md](references/signal-impact-system.md). Its default structure is huge outlined hook + expressive cutout person + real topic background + one proof card + short check items/arrows.

## Generate and edit

When the user asks to create the cover, use the built-in image-generation workflow for the finished visual by default; do not stop at a prompt or substitute a code-drawn poster unless the user explicitly requests deterministic/source-editable construction. Pass the supplied style reference, person, screenshots, and logo as separately labeled inputs. In the prompt, lock the person's identity, exact title, reference background category, subject ratio, title scale, palette, cards, arrows, and check items. Use deterministic compositing or a final overlay pass for exact logos, numbers, tables, and text when generation changes them materially.

For one requested cover, generate one strong master first. Inspect it at full size and feed size. Retry only for a concrete failure such as wrong ratio, unreadable title, altered identity, malformed hands, invented data, unrelated background, or weak visual density.

Keep source files separate where possible:

- background and texture;
- title and annotations;
- real collage or product screenshots;
- subject cutout;
- gradient, outline, and shadow effects.

## Verify

Run the bundled helpers when Python is available. The prompt builder is optional; natural-language style direction is the primary interface:

```bash
python3 scripts/platform_presets.py --list
python3 scripts/platform_presets.py --list-ratios
python3 scripts/prompt_builder.py --list-styles
python3 scripts/prompt_builder.py --style S01 --ratio 16:9 --title "400+ Figma Templates"  # optional catalog helper
python3 scripts/verify_thumbnail.py output.png --platform wechat-channels
python3 scripts/verify_thumbnail.py output.png --ratio 4:3
```

Use `--aspect-only` only when the user intentionally requests a non-canonical resolution. The verifier checks technical conformance; still perform visual QA at full size and at a small feed preview.

## Deliver

Report:

- the final file path and pixel dimensions;
- the platform preset or generic ratio used;
- the interpreted style description and, if useful, an optional catalog tag;
- which supplied real assets were preserved;
- any assumptions or unsupported native-file claims;
- a rights caveat when commercial use is requested but third-party rights are not documented.

Do not label an output “commercially cleared” merely because this skill's code is open source. Commercial clearance depends on every included photo, person, brand, font, screenshot, template, and generated asset.
