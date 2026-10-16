#!/usr/bin/env python3
"""Build a ready-to-edit thumbnail prompt from a style ID and ratio."""

from __future__ import annotations

import argparse

from platform_presets import RATIO_PRESETS, resolve_ratio


STYLES = {
    "S01": {"zh": "暖白手写拼贴：暖白纸张、深蓝手写标题、少量橙蓝笔刷、真实截图拼图、标题下方白色到透明渐变。", "en": "Warm Handwritten Collage: ivory paper, navy marker title, restrained coral/blue strokes, real screenshot collage, and a background-to-transparent title transition."},
    "S02": {"zh": "人物高点击：真人占画面约 40%，短标题、强对比、一个真实结果截图，只用一种描边或阴影。", "en": "Face-led High CTR: real portrait at about 40%, short high-contrast title, one real proof image, and one outline or shadow."},
    "S03": {"zh": "极简 UI 展示：浅色背景、现代无衬线、充足留白、一张真实主界面和最多两张辅助卡片。", "en": "Clean UI Showcase: light background, modern sans serif, generous spacing, one dominant real interface, and at most two supporting cards."},
    "S04": {"zh": "深色科技霓虹：近黑背景、单一霓虹强调色、真实仪表盘或代码界面、克制边缘光。", "en": "Dark Tech Neon: near-black field, one neon accent, real dashboard or code proof, and restrained edge lighting."},
    "S05": {"zh": "大数字清单：数字最大、类别或收益第二、三到六个真实案例清晰分组。", "en": "Bold Number List: one dominant number, a secondary category or benefit, and three to six grouped real examples."},
    "S06": {"zh": "前后对比：可比的真实前后图片、对应裁切、清楚标签和最多一支箭头。", "en": "Before–After Split: comparable real before/after images, matched crops, clear labels, and at most one arrow."},
    "S07": {"zh": "新闻观点：真实事件或人物图片、简短事实角度、一个色块或栏目标签。", "en": "News Commentary: real topic image, concise factual angle, and one color block or segment label."},
    "S08": {"zh": "高级杂志：中性低饱和背景、衬线与无衬线搭配、高清主体和大面积负空间。", "en": "Premium Editorial: neutral muted background, serif/sans pairing, high-quality subject, and deliberate negative space."},
    "S09": {"zh": "活力贴纸：亮色或暖纸张、真人或真实产品、原创涂鸦胶带、两到三种强调色。", "en": "Playful Sticker: bright blocks or warm paper, real subject or product, original doodles and tape, and two or three accent colors."},
    "S10": {"zh": "产品主视觉：真实产品为唯一主角、收益优先标题、简洁品牌背景和自然光影。", "en": "Product Hero: one real hero product, benefit-first title, clean brand setting, and natural light and shadow."},
    "S11": {"zh": "真人高密度大字：超大浅黄/白粗黑描边标题、35%-55%真人抠图、真实界面背景、倾斜证据卡、大数字、箭头和绿色勾选项。", "en": "Creator Impact: huge pale-yellow/white black-keylined title, 35%-55% real cutout, topic-related interface background, tilted proof card, large count, arrows, and green checks."},
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-styles", action="store_true", help="List available style IDs")
    parser.add_argument("--style", help="Style ID S01 through S11")
    parser.add_argument("--ratio", help="Ratio such as 4:3, 16:9, or 9:16")
    parser.add_argument("--title", default="{主标题 / main title}")
    parser.add_argument("--subtitle")
    parser.add_argument("--platform", default="unspecified")
    parser.add_argument("--assets")
    parser.add_argument("--colors")
    parser.add_argument("--language", choices=("zh", "en"), default="zh")
    args = parser.parse_args()

    if args.list_styles:
        for style_id, description in STYLES.items():
            print(f"{style_id}: {description[args.language]}")
        return 0
    if not args.style or not args.ratio:
        parser.error("--style and --ratio are required unless --list-styles is used")

    style_id = args.style.upper()
    if style_id not in STYLES:
        parser.error(f"unknown style '{args.style}'. Choose: {', '.join(STYLES)}")
    ratio = resolve_ratio(args.ratio)
    if ratio not in RATIO_PRESETS:
        parser.error(f"unknown ratio '{args.ratio}'. Choose: {', '.join(RATIO_PRESETS)}")
    preset = RATIO_PRESETS[ratio]

    if args.language == "zh":
        subtitle = args.subtitle or ("根据主题自动写一条短副标题，并从证据提炼最多三条短标签" if style_id == "S11" else "{可选副标题}")
        assets = args.assets or "{已上传的真人、产品、截图和 Logo}"
        colors = args.colors or ("柔和浅黄 #FDFFA7、白色、近黑色，绿色勾选与少量珊瑚红标签" if style_id == "S11" else "{品牌色或自动选择}")
        style_rule = "\nS11 专用规则：标题占竖版高度35%-45%，真人占35%-55%；主标题和大数字使用粗犷手绘/马克笔字形，副标题、模型名、分数和勾选项使用规整粗黑体；使用真实界面或截图延展为背景；加入一张倾斜证据卡、大数字、粗箭头和最多三条绿色勾选；禁止无关抽象背景、全画面手写小字、细字体、相框式抠图和大面积留白。" if style_id == "S11" else ""
        prompt = f"""$create-social-thumbnails
请制作一张社交媒体封面。
风格编号：{style_id}
风格定义：{STYLES[style_id]['zh']}
平台：{args.platform}
比例：{ratio}
建议画布：{preset['width']} × {preset['height']}
主标题：{args.title}
副标题：{subtitle}
真实素材：{assets}
品牌色：{colors}
{style_rule}

必须使用我上传的真实素材。不要生成、重绘或替换人物、产品、Logo、数据和界面截图。参考图只用于构图、层级和配色方向。标题在手机信息流小图中仍要清楚，重要内容保留安全边距。完成后说明最终尺寸、使用的真实素材和未确认的授权风险。"""
    else:
        subtitle = args.subtitle or ("write one short supporting line from the topic and up to three proof chips from supplied evidence" if style_id == "S11" else "{optional supporting title}")
        assets = args.assets or "{uploaded real portraits, products, screenshots, and logos}"
        colors = args.colors or ("pale yellow #FDFFA7, white, near-black, bright green checks, and one coral-red label" if style_id == "S11" else "{brand colors or auto-select}")
        style_rule = "\nS11 rule: title uses 35%-45% of vertical height and the real cutout uses 35%-55%; use chunky hand-painted/marker forms for the main hook and large count, but clean heavy sans for subtitles, model names, scores, and check items; extend a real interface or screenshot into the background; add one tilted proof card, a large count, a thick arrow, and up to three green checks; forbid unrelated abstract backgrounds, all-handwritten small copy, thin type, framed cutouts, and large empty gaps." if style_id == "S11" else ""
        prompt = f"""$create-social-thumbnails
Create a social-media thumbnail.
Style ID: {style_id}
Style definition: {STYLES[style_id]['en']}
Platform: {args.platform}
Ratio: {ratio}
Suggested canvas: {preset['width']} × {preset['height']}
Main title: {args.title}
Supporting title: {subtitle}
Real assets: {assets}
Brand colors: {colors}
{style_rule}

Use my uploaded real assets. Do not generate, redraw, or replace people, products, logos, data, or interface screenshots. Treat references as direction for composition, hierarchy, and color only. Keep the title readable at mobile feed size and essential content inside safe margins. On delivery, report final dimensions, preserved real assets, and unresolved rights risks."""

    print(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
