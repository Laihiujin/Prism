---
name: video-thumbnail
description: Use when the user wants to create a YouTube thumbnail, Shorts/Reels/TikTok cover, or any video thumbnail. Asks up front whether it's long-form (horizontal 16:9) or short-form (vertical 9:16), then routes through the correct flow. Uses Gemini 3 Pro Image Preview (Nano Banana Pro) to generate four professional, high-contrast concepts composited with the user's headshot photos.
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


# Video Thumbnail Generator (Long + Short Form)

Generate professional thumbnails and vertical cover art using Gemini Nano Banana Pro. Produces 4 entirely different concepts at once, saves them individually, and creates a 2x2 comparison grid so the user can quickly pick the direction they like best.

This skill handles both:
- **Long-form (horizontal, 16:9)** — YouTube video thumbnails
- **Short-form (vertical, 9:16)** — YouTube Shorts, Instagram Reels, TikTok cover images

---

## Step 0: Ask Which Format First

**Before anything else**, ask the user exactly this:

> **Long-form or short-form?**
> - **Long-form** → 16:9 horizontal YouTube video thumbnail
> - **Short-form** → 9:16 vertical cover image for Shorts / Reels / TikTok

Wait for the answer before proceeding. The answer determines:
- `--aspect-ratio` value passed to `generate_thumbnail.py` (`16:9` or `9:16`)
- Composition rules (see **Format-Specific Composition** below)
- Output folder naming (optional but recommended): `{video-slug}-horizontal` vs `{video-slug}-shorts`

If the user says something ambiguous ("YouTube"), ask whether they mean a regular video (long-form) or a Short (short-form). Don't guess.

---

## Thumbnail Strategy

Before touching any design tool, internalize the psychology of how viewers decide to click. Every thumbnail needs to win a 1-2 second decision loop.

### The 3-Step Viewer Psychology Flow

Viewers don't just "see thumbnail → click." The actual decision happens in three rapid steps:

1. **Visual Stun Gun** — Something in the thumbnail stops the scroll. The viewer switches from passive scanning to active comprehension. Your thumbnail needs to visually pop enough to trigger this.
2. **Title Value Hunt** — The viewer looks at the title (or caption, in the case of shorts) to understand what it's about and whether it's worth their time. They're hunting for a desire loop (educational: "will this help me?") or interest loop (entertainment: "what happens next?").
3. **Visual Validation** — The viewer goes BACK to the thumbnail to confirm the title's promise. If the thumbnail supports the title's promise and they trust it, they click (or keep watching, for shorts).

**The flow is: Thumbnail → Title → Thumbnail.** If the thumbnail doesn't pop, they never see the title. If the title promise is weak, they look but don't click. If the thumbnail doesn't reinforce the title, they bounce.

### Thumbnail + Title Relationship

The thumbnail and title are a package. Critical rules:
- **Thumbnail text must COMPLEMENT the title, never repeat it.** The thumbnail is an additional surface to add trust and clarity. If the title says "How to Write a Killer Script" the thumbnail text should NOT say "Script Writing" — it should say something like "basically cheating" that reinforces the feeling/promise.
- **Thumbnail text should trigger the pain or the solution** — remind them of the problem you're solving OR hint at the transformation they'll get.
- Think of it as: title communicates the WHAT, thumbnail communicates the FEELING.

### Desire Loop Framework

Before designing, define the desire loop for this specific video:
- **What is the core desire?** (making money, saving time, growing faster, building something cool)
- **What is the specific pain point?** (growing too slow, can't code agents, wasting time on manual work)
- **What is the solution/transformation?** (a method, a tool, a framework that solves the pain)
- **What is the curiosity loop?** ("If I click, will I be able to ___?")

Every element in the thumbnail should serve this desire loop.

### The 7 Visual Stun Gun Elements

**Use a maximum of 3 per thumbnail.** Thumbnails are small — especially on mobile, and especially for shorts. Too many elements and nothing is comprehensible.

1. **Color contrast** — Vivid/bright colors that pop against the background.
2. **Large face with emotion** — A recognizable person OR an unknown face with a strong, clear emotion. For smaller channels, emotion matters more than recognition.
3. **Visually compelling graphic** — A visual that draws attention through bright colors, interesting design, or optical patterns. Should immediately represent the desire loop.
4. **Big text, numbers, or dollars** — Large, round numbers in huge font. Brains are magnets to these. Underline or highlight key numbers for emphasis.
5. **Red circles or arrows** — Literally aim attention where you want it. Use sparingly and intentionally.
6. **Aesthetic imagery** — Cinematic, symmetrical, soothing visuals.
7. **Design collage** — Words, numbers, or icons surrounding the subject. Creates energy and density.

### 3 Composition Types

- **Symmetrical** — Main subject centered, both sides relatively balanced
- **Asymmetrical (Rule of Thirds)** — Subject offset to one side (~1/3), remaining space filled with visual elements
- **A→B Split** — Screen split showing a transformation, before/after, or contrast

### Graphic Element Selection

When choosing a graphic/visual element, it should represent the desire loop in one of four ways:
1. **End state** — Show what they want (e.g., PayPal screenshot with earnings, YouTube plaque)
2. **Process visualization** — Show the method/process they'll learn
3. **Before → After** — Show the transformation
4. **Anti-state / Pain point** — Remind them of the pain you're solving

---

## Format-Specific Composition

The psychology and desire-loop framework is the same for both formats. The **composition** is different.

### Long-Form (16:9 Horizontal)

- **Person:** Right side of frame, ~40% of width. Shoulders-up or waist-up.
- **Visual elements:** Left side of frame. Slightly layered/overlapping for depth.
- **Text:** Upper area or integrated into the composition. Large, bold, readable.
- **Bottom-right corner:** Keep clear — YouTube's video timestamp overlay covers this area.
- **Size test:** Every element must be legible at 320x180px (mobile thumbnail size).

### Short-Form (9:16 Vertical)

Shorts/Reels/TikTok covers behave differently from horizontal thumbnails:

- **UI overlays eat real estate.** On Shorts and Reels feed views, large parts of the frame are covered by the app's UI: like/comment/share buttons on the right side, caption + channel info at the bottom, progress bar at the top. **Keep the top 12% and bottom 25% of the frame clear of critical elements.**
- **Person:** Centered or slightly offset. The person usually goes in the upper-middle or middle, NOT the bottom (caption area) and NOT the top (where channel name and Shorts icon sit).
- **Visual elements:** Above or beside the person, still in the "safe zone" (middle 60-70% of vertical space).
- **Text:** If used, keep it LARGE and in the middle third — avoid the top and bottom bands entirely. Shorter words than horizontal (1-3 words max works best).
- **Right side:** Right-edge icons on Shorts/Reels cover ~15% of the right side. Don't put faces or critical text there.
- **Aspect ratio:** 9:16 (720x1280 minimum). On YouTube, a vertical cover image is also what shows up as the Short's preview card — so it doubles as a feed thumbnail.
- **Feed vs. player:** When scrolling, users see the vertical cover briefly before the video auto-plays. It needs to stop the scroll in under a second. Bigger elements, louder contrast, less text than horizontal.

**The simplest mental model:** imagine the 9:16 frame split into thirds vertically. Top third = mostly clear (UI). Middle third = hero zone (face + main graphic + text). Bottom third = mostly clear (caption/UI).

---

## Process

### Step 1: Get the Topic & Set Up

After confirming format (Step 0), all you need is the **video topic or title**. Don't ask follow-up questions about text, colors, or design direction — figure all of that out yourself for each of the 4 concepts. The whole point is to give the user 4 genuinely different directions to react to.

**However, do ask about specific visual elements.** Before designing, ask the user if there are any specific logos, products, tools, screenshots, or other visual assets that should appear. For example: "Should I include any specific logos (Claude, Cursor, etc.) or product shots?" This takes 5 seconds and avoids wasting a generation on the wrong references.

Pick the first available headshot from `.claude/skills/video-thumbnail/assets/headshots/`. If the folder is empty, tell the user to add a headshot photo there first.

### Step 1b: Search for High-Performing Example Thumbnails

Search for videos on the same topic that already have high view counts, and download their thumbnails as style inspiration. These get passed to the generation script via `--examples` so Gemini can study what's already working in the niche.

**For long-form**, search regular YouTube videos. **For short-form**, prefer searching for YouTube Shorts or Reels — their covers use different composition rules, so studying horizontal thumbnails for a vertical project will mislead you.

```bash
python3 .claude/skills/video-thumbnail/scripts/search_examples.py \
  --query "{video topic}" \
  --top 5 \
  --min-views 10000
```

For short-form research, append words like "shorts" or "reel" to the query so you get vertical covers back (e.g., `--query "claude code shorts"`).

This will:
1. Search YouTube via the Scrape Creators API for videos matching the topic
2. Sort results by view count (highest first)
3. Download the top 5 thumbnails to `workspace/examples/`
4. Print a JSON manifest to stdout with metadata (title, views, channel) for each

**Review the downloaded examples** with the `Read` tool. Note composition patterns, color palettes, text styles, and whether faces or graphics are more prominent. For short-form, specifically note how creators handle the safe zones.

**Notes:**
- Requires `SCRAPECREATORS_API_KEY` in `.env` (free tier available — see README)
- YouTube thumbnail URLs (i.ytimg.com) download reliably — no hotlink blocking issues
- If the API is out of credits or fails, skip this step — it's enhancement, not a hard requirement
- The `--min-views` filter helps ensure you're only studying thumbnails that actually performed well

### Step 2: Define the Desire Loop, Then Craft 4 Different Prompts

**Before designing anything**, work through the desire loop:
1. What desire does this video trigger? (money, growth, speed, capability)
2. What pain point does the viewer have?
3. What solution/transformation does the video deliver?
4. What's the curiosity loop? ("If I click, will I ___?")

Then craft **4 entirely different thumbnail concepts**. Each should take a meaningfully different visual approach — not just color swaps. Vary across these dimensions:

- **Visual elements:** Different objects, icons, screenshots, props — each representing the desire loop differently (end state vs. process vs. before/after vs. pain point)
- **Text treatment:** Different words that complement (not repeat) the title, or no text at all
- **Color direction:** Different gradient/accent color combos — at least one concept should explore whether a non-dark approach might stand out against competitors in the feed
- **Person pose/expression direction:** Different emotions that match the feeling a viewer would have after watching (confident, excited, shocked, curious)
- **Composition style:** Different layouts — try at least one of each composition type (symmetrical, asymmetrical, A→B split) across the 4 concepts

Label each concept A, B, C, D. Briefly describe each concept to the user before generating — include what desire loop element each one leverages.

**Key rules for every prompt:**
- Always describe the person placement explicitly (long-form: "a man positioned on the right side"; short-form: "centered in the middle third of the frame")
- Always specify the reference photo ("use the attached reference photo of the person")
- Always specify the aspect ratio and a darkened real-world scene as background (never a solid black void)
- Describe visual elements with specific positioning
- Describe text with font style, color, and position
- **Long-form:** Never place important elements in the bottom-right corner (YouTube's timestamp overlay covers this area).
- **Short-form:** Never place important elements in the top 12% or bottom 25% (Shorts/Reels UI covers these), and keep the right ~15% clear of faces/critical text (app action buttons).
- **Keep elements large** — imagine the thumbnail at 1/16th size on an iPhone. If you can't read/see it, it's too small.

### Step 2b: Gather Reference Images for Concepts

Now that you have 4 specific concepts designed, gather the reference images each one needs. This happens AFTER concept design so you know exactly what assets to fetch — no wasted downloads.

Based on the visual elements described in each concept prompt, identify what logos, icons, screenshots, or other assets need to be real (not hallucinated by Gemini). These get passed via `--reference`.

**What to fetch:**
- **Tool/product logos** — Claude Code, Cursor, Make.com, OpenAI, etc. — fetch their official logos or icons
- **Mascots or brand visuals** — e.g., the Anthropic claude logo, the OpenAI logo mark, app icons from the App Store
- **UI screenshots** — If the video shows a specific tool, IDE, dashboard, or interface, grab a clean screenshot
- **Relevant icons or symbols** — API symbols, code syntax snippets, framework logos (LangChain, React, etc.)
- **Celebrity/creator photos** — If the video references a specific public figure and you want them in the thumbnail

**How to fetch:**
1. Use `WebSearch` to find the best image URL (e.g., search for "Claude Code logo PNG transparent" or "Cursor IDE icon")
2. Use `Bash` with `curl` to download AND validate the image in one step:
   ```bash
   mkdir -p workspace/refs && \
   curl -sL "https://example.com/logo.png" -o "workspace/refs/claude-logo.png" && \
   file workspace/refs/claude-logo.png
   ```
3. **CHECK the `file` output before proceeding.** The `file` command tells you the actual file type:
   - **Good:** `PNG image data`, `JPEG image data`, `SVG Scalable Vector Graphics` → real image, proceed
   - **Bad:** `HTML document text`, `ASCII text`, `XML document` → the download failed (site blocked hotlinking and returned a web page). **Delete it and try a different source.**
4. Only after `file` confirms it's a real image, verify it visually with the `Read` tool

**CRITICAL: Many image hosting sites block direct downloads.** They return an HTML page instead of the image. If you skip validation, the generation script will fail with "Could not process image." The `file` command catches this instantly.

**If a download returns HTML instead of an image:**
- Try a different source URL entirely (don't retry the same URL)
- Prefer these reliable sources for logos/icons:
  - **Wikipedia/Wikimedia Commons** — direct file URLs usually work (use the `/thumb/` URL path)
  - **GitHub raw content** — `raw.githubusercontent.com` URLs work reliably
  - **Official brand/press pages** — often have direct download links
- Add `-H "User-Agent: Mozilla/5.0"` to the curl command if the site requires a browser user-agent
- As a last resort, skip the reference image — Gemini can approximate common logos from description alone

**Tips:**
- Prefer PNG with transparent backgrounds — they composite much better
- Fetch 2-5 reference images max — too many clutters the generation context
- Save all reference images in `workspace/refs/` to keep them organized and reusable across concepts
- **Always validate with `file` before using** — never assume a download succeeded just because curl didn't error

If the concepts don't need any specific visual assets (rare), skip this step.

### Step 3: Generate All 4 Thumbnails

Run the generation script **4 times in parallel** — one for each concept. Pass reference images via `--reference`, example thumbnails (from Step 1b) via `--examples`, and the aspect ratio that matches the format chosen in Step 0.

- **Long-form:** `--aspect-ratio 16:9`
- **Short-form:** `--aspect-ratio 9:16`

```bash
python3 .claude/skills/video-thumbnail/scripts/generate_thumbnail.py \
  --headshot ".claude/skills/video-thumbnail/assets/headshots/{selected-headshot}" \
  --reference "workspace/refs/{ref1}.png" "workspace/refs/{ref2}.png" \
  --examples "workspace/examples/{slug}-1.jpg" "workspace/examples/{slug}-2.jpg" "workspace/examples/{slug}-3.jpg" \
  --aspect-ratio {16:9 or 9:16} \
  --prompt "{concept A prompt}" \
  --output "workspace/{today}/thumbnails/{video-slug}/a.png"
```

Repeat for B, C, D in parallel.

**Run all 4 in parallel** for speed. The script requires `GEMINI_API_KEY` to be set as an environment variable.

**Example image notes:**
- Pass the same `--examples` to all 4 concepts — they're style inspiration, not concept-specific elements
- The script automatically appends a "STYLE EXAMPLES" instruction to the prompt telling Gemini to study but not copy them
- If Step 1b was skipped, simply omit `--examples` entirely
- Use 3-5 examples max — more adds context window bloat without much benefit

**Reference image notes:**
- Only pass `--reference` images that are relevant to that specific concept's visual elements
- In the prompt, explicitly tell Gemini which attached reference image is which: "The second attached image is the Claude Code logo — place it in the upper-left"
- If a concept doesn't use any reference images, omit `--reference` entirely
- The headshot is always the first attached image; reference images follow in the order they're listed

### Step 4: Create Comparison Grid

After all 4 thumbnails are generated, combine them into a single 2x2 comparison image:

```bash
python3 .claude/skills/video-thumbnail/scripts/combine_thumbnails.py \
  --images "workspace/{today}/thumbnails/{video-slug}/a.png" \
           "workspace/{today}/thumbnails/{video-slug}/b.png" \
           "workspace/{today}/thumbnails/{video-slug}/c.png" \
           "workspace/{today}/thumbnails/{video-slug}/d.png" \
  --output "workspace/{today}/thumbnails/{video-slug}/comparison.png" \
  --labels "A" "B" "C" "D"
```

### Step 5: Present to User

Show the comparison grid image and describe each concept:
- **A:** {brief description of concept A}
- **B:** {brief description of concept B}
- **C:** {brief description of concept C}
- **D:** {brief description of concept D}

Ask which direction they like best, or if they want to mix elements from different options.

### Step 6: Iterate

Once the user picks a direction (e.g., "I like B but with the colors from D"), generate a refined version by passing the chosen thumbnail as a reference image:

```bash
python3 .claude/skills/video-thumbnail/scripts/generate_thumbnail.py \
  --headshot ".claude/skills/video-thumbnail/assets/headshots/{selected-headshot}" \
  --reference "workspace/{today}/thumbnails/{video-slug}/b.png" \
  --aspect-ratio {same as before} \
  --prompt "{edit prompt combining user feedback}" \
  --output "workspace/{today}/thumbnails/{video-slug}/v2.png"
```

For the edit prompt, include context about the original design plus the specific changes:
```
Edit this video thumbnail. Keep the same overall composition and style.
The first attached image is a reference photo of the person — use their likeness.
The second attached image is the current thumbnail to modify.
Please make the following changes: {user's edit instructions}
```

Continue iterating with v3, v4, etc. until the user is happy.

---

## Style Guide

The default style is professional, high-contrast, and designed to stand out in feed. If a `brand-style.md` file exists in this skill directory, the generator auto-appends it to every prompt — use that to lock in your own brand colors, typography, and visual identity.

### Composition (Long-Form 16:9)
- **Person:** Right side of frame, taking up ~40% of width. Shoulders-up or waist-up. Slightly angled toward camera or toward the visual elements. Natural, dramatic lighting on face.
- **Face emotion:** Must match the feeling the viewer would have watching the video. For smaller channels, emotion > recognition.
- **Visual elements:** Left side of frame. App icons, dashboards, screenshots, data visualizations, or relevant imagery. Slightly layered/overlapping for depth.
- **Icons/logos:** Upper-left area, floating with subtle shadows. Often with a "+" symbol between them to suggest integration.
- **Text (if any):** Bold, large, readable. Usually upper area or integrated into the composition. White against the dark background. Must complement (not repeat) the video title.
- **Bottom-right corner:** Keep clear — YouTube's timestamp overlay covers this area.
- **Element count:** Maximum 3 distinct elements.
- **Size test:** Every element must be legible at 320x180px.

### Composition (Short-Form 9:16)
- **Person:** Middle third of frame vertically, centered or slightly offset horizontally. Face should be LARGER than in a horizontal thumbnail — shorts feed plays at full height.
- **Visual elements:** Stacked above or beside the person in the middle band. Less room for layering, so go bolder with fewer elements.
- **Text:** Middle third only. LARGE, 1-3 words max. Never in the top 12% (Shorts/Reels header UI) or bottom 25% (caption area).
- **Safe zones:**
  - Top 12% = channel/Shorts header
  - Bottom 25% = caption + title
  - Right ~15% = like/comment/share buttons
- **Element count:** Maximum 2-3 elements. Vertical covers have even less room than horizontal.

### Background (Both Formats)
- **Never a solid black void.** Use a darkened real-world scene or environment relevant to the topic. If the video is about Paris, the background should be a darkened moody Paris cityscape — not a black background with an Eiffel Tower graphic floating on it.
- Dark and moody overall. Cinematic color grading, not solid fills.
- Color tone: dark, desaturated, with the primary color being near-black `#0A0B12` equivalent — but achieved through darkening a real scene, not a flat color.
- Never bright, white, or pastel.
- Subtle gradient, texture, or environmental detail to add depth.
- No glow effects. Use subtle highlights, borders, and accent elements for depth.

### Color Palette
- **Background:** Darkened real-world scene or environment.
- **Accent colors:** Pick what fits the video topic and creates visual contrast. Bright, saturated accents work best against dark backgrounds.
- **Text:** White `#FFFFFF` is the default. Bold accent color sparingly for a single emphasized word.
- **High contrast** between foreground elements and dark background is critical.
- When varying the 4 concepts, explore different color palettes across them. Try warm tones (orange, red, gold), cool tones (blue, cyan, purple), and neutral high-contrast (white + dark).
- **Semantic colors:** Green = good/positive outcomes. Red = bad/negative outcomes.
- **Competitor contrast awareness:** Most AI/dev content uses dark, muted themes. Differentiate through bold text sizing, high saturation accent colors, and vivid contrast.

### Typography
- **Headlines:** Bold, heavy sans-serif. Describe as "bold, heavy, modern sans-serif font" in prompts.
- **Accent text:** Medium-weight serif italic. Describe as "elegant serif italic" in prompts.
- **Playful accents:** Hand-drawn comic style. Use sparingly.
- Note: Gemini can't render specific fonts. Describe the *style* in prompts. Exact fonts can be composited in post-production.

### Text on Thumbnails
- **Long-form:** Maximum 3-5 words. Fewer is better.
- **Short-form:** Maximum 1-3 words. Even fewer is better.
- Must be readable at small size (320x180 for horizontal, 180x320 for vertical).
- Do NOT overlap text with the person's face.
- **Must complement the title, never repeat it.**
  - Good: Title = "How to Write a Killer Script" → Thumbnail text = "basically cheating"
  - Bad: Title = "How to Write a Killer Script" → Thumbnail text = "Script Writing Guide"
- Big, round numbers are attention magnets — use them when relevant.
- Underline or highlight key words/numbers for extra emphasis.

### Technical Specs
- **Aspect ratio:** 16:9 (long-form) or 9:16 (short-form)
- **Minimum resolution:** 1280x720 (horizontal) or 720x1280 (vertical)
- **Output format:** PNG

---

## Prompt Template

Use this as a starting point for each of the 4 concepts. Customize heavily — each concept should feel like a different design direction, not a minor tweak. The template below is for long-form; for short-form, swap the composition section (see below).

```
A professional video thumbnail in {16:9 / 9:16} aspect ratio.

ATTACHED IMAGES:
- Image 1 (headshot): Reference photo of the person to include. Use their exact likeness.
{reference_image_descriptions}

PERSON:
Use the likeness from the headshot (Image 1).
[Long-form]: Place them on the right side of the frame, taking up approximately 40% of the width. Show them from the waist up or shoulders up.
[Short-form]: Place them centered horizontally, in the middle third of the frame vertically. Face should be clearly visible and larger than for a horizontal thumbnail. Keep the top 12% and bottom 25% of the frame clear of the person and any critical elements.
Dramatic, natural lighting on their face with the dark background behind them. They are looking [toward the camera / slightly toward the visual elements]. Their expression is [confident / excited / curious / serious].

BACKGROUND:
Dark, moody, cinematic background — NOT a solid black void. Use a darkened real-world scene or environment relevant to the video topic. The scene should feel like dramatic night photography or heavy cinematic color grading — dark overall but with real environmental detail, texture, and depth. {color_direction} color tones. No glow effects. No bright or white backgrounds, and never a flat solid-color void.

VISUAL ELEMENTS:
[Long-form]: Place on the left side of the frame, slightly layered/overlapping for depth.
[Short-form]: Stack above or beside the person in the middle third. Keep clear of top 12%, bottom 25%, and right 15%.
{visual_elements_description}
When referencing attached images, be explicit: "Use the [logo/screenshot/icon] from Image N as the [element description], placed in [position]."

TEXT:
"{thumbnail_text}" in bold, large, white text.
[Long-form]: Placed {text_position}.
[Short-form]: Placed in the middle third only. Larger and with fewer words than a horizontal thumbnail.
Clean, heavy, modern sans-serif font. High contrast against the dark background. Must be clearly readable. Default to white for all text — use a bold accent color only for a single emphasized word if needed.

STYLE:
Professional, high-contrast, clean design. Dramatic lighting on the person. Subtle depth with layered elements. Polished and modern — not cluttered.
```

**Reference image description format** — list each reference image passed via `--reference` with what it is and how to use it:
```
- Image 2 (Claude Code logo): The official Claude Code terminal icon. Use this as the app icon in the upper-left area.
- Image 3 (Cursor IDE screenshot): A screenshot of the Cursor code editor. Use this as the dashboard/UI element on the left side.
```

### Ideas for Varying the 4 Concepts

To make each concept genuinely different, vary along these axes:

| Dimension | Concept A | Concept B | Concept C | Concept D |
|-----------|-----------|-----------|-----------|-----------|
| **Desire loop angle** | End state (show the result) | Process (show the method) | Before → After (transformation) | Pain point (show the problem) |
| **Visual focus** | App icons + logo | Dashboard/data | Code/terminal | Product mockup |
| **Text** | Punchy feeling word (complements title) | No text (visual only) | Big number or dollar amount | Pain-trigger word |
| **Colors** | Dark + warm accent (orange, gold) | Dark + cool accent (blue, cyan) | Dark + bold red/magenta | Dark + white/minimal + high contrast |
| **Person emotion** | Confident smile (success) | Shocked/surprised (discovery) | Curious, pointing (teaching) | Serious, direct (authority) |
| **Layout** | Asymmetrical (rule of thirds) | Symmetrical (centered) | A→B split (transformation) | Minimal, lots of negative space |
| **Stun gun elements** | Face + graphic + text | Face + big number | Face + collage design | Compelling graphic + text (no face) |

---

## Quality Checklist

Run through this after every generation:

### Technical Quality
- [ ] **Person is recognizable** — face is clear, well-lit, not distorted
- [ ] **Person is positioned correctly** — right side for long-form, middle third for short-form
- [ ] **Face has clear emotion** — matches the feeling a viewer would have watching the video
- [ ] **Background is dark** — moody, not bright or distracting, and uses a real scene (not a solid void)
- [ ] **Visual elements are present** — icons, dashboards, or other relevant elements
- [ ] **3 elements max** — not overcrowded
- [ ] **Text is readable** at the smallest display size for the format
- [ ] **Text doesn't overlap the face**
- [ ] **UI safe zones respected**
  - Long-form: bottom-right clear of YouTube timestamp overlay
  - Short-form: top 12%, bottom 25%, and right 15% clear of critical content
- [ ] **High contrast** — foreground elements pop against the background
- [ ] **Correct aspect ratio** — 16:9 for long-form, 9:16 for short-form
- [ ] **Clean composition** — not cluttered, clear visual hierarchy

### Psychology Flow Check (the 3-step gut check)
- [ ] **Visual Stun Gun** — would this stop a scrolling thumb? Does it pop in a feed of competitor thumbnails?
- [ ] **Title Value Hunt** — does it make you curious enough to read the title?
- [ ] **Visual Validation** — after reading the title, does the thumbnail REINFORCE the promise?

### Strategic Check
- [ ] **Thumbnail text complements the title** — adds new information or feeling, doesn't repeat
- [ ] **Desire loop is clear** — visuals represent the end state, process, transformation, or pain point
- [ ] **Emotion is intentional** — face expression, color choices, and text all serve the same direction
- [ ] **Stands out from competitors** — would this catch your eye against similar content in the feed?

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Could not process image" when reading downloaded reference | The downloaded file is HTML, not an image — the site blocked hotlinking. Run `file <path>` to confirm. Delete it and download from a different source (Wikipedia, GitHub raw, or official press kit). |
| search_examples.py "out of credits" or "Invalid API key" | Scrape Creators API needs credits topped up. Skip Step 1b and generate without `--examples` — it's enhancement, not required. |
| No image returned | Simplify the prompt. Remove any potentially flagged content. Try again. |
| Person doesn't look like the headshot | Add more explicit instruction: "Use the exact likeness from the attached reference photo." Try a different headshot with clearer lighting. |
| Text is garbled or unreadable | Gemini's text rendering isn't perfect. Consider generating without text and adding it in post-production (Figma, Canva, etc.). |
| Wrong aspect ratio | Pass `--aspect-ratio 9:16` for vertical thumbnails. If the output looks wrong, check the saved file dimensions. |
| Short-form elements overlap with Shorts UI | The prompt didn't enforce safe zones — be explicit about keeping the top 12% and bottom 25% clear. |
| API error or timeout | Check that GEMINI_API_KEY is set. Check internet connection. Try again — API calls can intermittently fail. |
| One of the 4 fails | The other 3 still save fine. Re-run just the failed one. |

---

## Output Format

Use today's date (YYYY-MM-DD format) for the date folder. For example, if today is 2026-02-18, the output goes in `workspace/2026-02-18/thumbnails/`.

Each video topic gets its own folder under `workspace/{today}/thumbnails/`. Suggested naming convention to tell long-form and short-form outputs apart:

```
workspace/{today}/thumbnails/{video-slug}-horizontal/    # long-form 16:9
  a.png  b.png  c.png  d.png  comparison.png  v2.png ...

workspace/{today}/thumbnails/{video-slug}-shorts/        # short-form 9:16
  a.png  b.png  c.png  d.png  comparison.png  v2.png ...
```

The scripts create directories automatically via `mkdir -p`.
