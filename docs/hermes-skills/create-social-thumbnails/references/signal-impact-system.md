# Creator Impact / 真人高密度大字

Use this flagship system for AI tutorials, product tests, beginner explainers, creator tips, and other feed covers where a real presenter, a large conversational hook, and real proof must create an immediate click signal.

## Required inputs

Use what the user already supplied. Do not repeat questions whose answers are present.

- Target platform and ratio.
- One real person reference or cutout.
- One or more topic assets: interface, benchmark, product, document, result, or logo.
- A finished title, topic, or script from which a title can be written.
- An optional style reference or fixed title-color reference.

If only a topic is supplied, write the cover copy yourself. Select one 4–10-character conversational hook, one short context line, and up to three 2–6-character proof labels. For reviews, surface a truthful count such as “7项横评” and verified numbers from the supplied evidence.

## Default generation route

When the user asks for a finished cover, use the built-in image-generation workflow for the complete visual. Do not default to a Python/Pillow poster, a prompt-only answer, or an abstract background study.

Label image inputs explicitly:

1. Style reference: composition, density, typography, palette, outline weight, and decoration rhythm only.
2. Person reference: identity, expression, clothing, pose, and proportions must remain recognizable.
3. Topic/evidence assets: reuse as the environment, product cards, proof cards, or screenshots.
4. Logo/brand assets: preserve their actual mark and spelling.

Ask the image model for one master first. Use deterministic overlays afterward only when exact text, logo, or data changed materially.

## Standard SOP

Follow this sequence so another user can reproduce the style from new content.

1. **Resolve inputs.** Identify platform/ratio, one person image, one topic/evidence image, optional logo, and optional style/color reference. Do not ask again for information already present.
2. **Write the copy package.** Produce one 4–10-character conversational hook, one context tag, one short supporting line, one large count/result phrase, and zero to three verified proof chips. Keep every claim traceable to supplied material.
3. **Assign image roles.** Person = identity-locked foreground cutout. Topic image = blurred/dimmed background environment and/or sharp proof card. Logo = exact compact context mark. Style reference = title scale, density, subject ratio, background category, outline weight, card rhythm, and decoration language only.
4. **Compose the prompt.** State the exact ratio, all text verbatim, headline height, person area, background source, proof-card position, arrow direction, check items, palette, and avoid list. Do not use vague phrases such as “make it viral” without concrete layout instructions.
5. **Generate one master.** Use the built-in image-generation workflow. Do not create several weak color variants before the first structure passes review.
6. **Review at two scales.** Inspect full size for identity, hands, text, numbers, screenshot fidelity, and edges. Inspect at roughly 25% size for title dominance, face recognition, and the title → face → count → proof reading order.
7. **Targeted retry.** Change one failed property only: typography, subject scale, proof crop, background relevance, or density. Preserve successful parts and do not restart art direction unnecessarily.
8. **Export.** Recompose or crop minimally to the platform preset, verify exact dimensions, retain the original generated master when useful, and save a feed-size preview.

## Visual system

### Headline

- The headline is the first visual and fills roughly 35–45% of a vertical canvas.
- Use two or three tightly stacked lines in ultra-heavy creator/variety-show type.
- Alternate pale yellow `#FDFFA7` and white. Apply a very thick black or near-black keyline and a thin cream highlight edge.
- Keep punctuation large and integrated. One small red/coral label such as `实测`, `新手必看`, or `教程` may sit above the hook.
- The headline may overlap the person contour or proof card slightly, but never covers eyes or mouth.

### Typography hierarchy

- Apply hand-drawn energy selectively, not uniformly.
- **Primary hook:** use chunky hand-painted/marker-like display lettering with deliberately irregular baselines, slightly uneven character widths, rounded corners, and human edge wobble. Keep counters open and every character recognizable.
- **Large count or result phrase:** may reuse a milder version of the hand-drawn display treatment so it belongs to the hook.
- **Supporting line, context tag, check items, scores, model names, and evidence labels:** use a clean heavy sans/黑体. These elements must remain precise and compact; do not make them scribbly.
- Keep the pale-yellow/white fill and thick black keyline even when the hook becomes hand-drawn. “Hand-drawn” changes the letterform rhythm, not the contrast system.
- Never apply handwriting to dense tables, benchmark numbers, small English model names, or three-line check labels.

### Person

- Use a real half-body or large-head cutout occupying 35–55% of the canvas.
- Default placement is lower-right or lower-center; use lower-left only when the title and evidence require it.
- Preserve the supplied identity and expression. Do not beautify, replace, or regenerate the face.
- Add a pale-yellow or white outer contour and a soft dark shadow.
- Let the body bleed off one or two edges. Never put an already-cut-out person inside a rectangular photo frame.

### Topic background

- Prefer a real room, software interface, product screen, benchmark, or supplied scene related to the topic.
- Enlarge, crop, blur, dim, or extend that asset to create the background environment.
- If evidence exists, do not replace it with an unrelated rayburst, gradient poster, gaming field, or invented technology scene.
- Background detail must remain visible enough to establish context but dark/soft enough to protect headline readability.

### Proof and support

- Use one dominant screenshot or benchmark as a tilted card with a light contour and shadow.
- Add a thick hand-drawn pale-yellow arrow from the person or headline toward the proof.
- Add up to three short check items using bright green checks, white/yellow heavy text, and dark rounded backing.
- Useful support includes a large count, verified score, product card, UI crop, question mark, sparkle, cursor, or small themed sticker.
- Fill meaningful gaps, but do not cover the face, title, or proof numbers.

## Product-test layout

For model, tool, or product comparisons:

- Top 40%: huge two-line question or verdict tension.
- Lower-right 40–50%: expressive presenter cutout.
- Lower-left 20–30%: real benchmark/product card.
- Near the proof: a large count such as `7项能力横评`.
- Bottom or side: up to three verified check items.
- Background: darkened version of the actual interface, benchmark, or tool screen.

The intended reading order is title → face → large count → proof card → check items.

## Prompt contract

The production prompt must specify:

- exact target ratio and platform;
- exact title and supporting labels in quotation marks;
- each input image's role;
- title scale, line count, colors, and outline weight;
- person size, placement, contour, and identity invariants;
- topic-related background source;
- proof-card placement, arrow, check items, and decoration density;
- avoid list: no unrelated abstract background, thin type, empty central gap, extra people, altered identity, malformed hands, fake data, watermark, or checkerboard.

## Review gate

Reject and retry when any of these occur:

- headline is smaller than the person or cannot be read at feed size;
- the cover looks like a clean editorial poster instead of a dense creator cover;
- an unrelated generated background replaces a usable topic asset;
- the person occupies less than 35% of the canvas, is framed like a photo, or has altered facial features;
- title, person, proof, and labels look like separate stickers with no overlap or directional flow;
- evidence data is invented, relabeled, or illegible at full size;
- there is a large unassigned central gap;
- title spelling, ratio, hands, face, or safe area is wrong.

Deliver the platform-sized PNG, keep the original generated master when useful, and report which real assets were preserved.
