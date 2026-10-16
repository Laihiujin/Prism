---
name: social-asset-studio
description: Plan, generate and review social-media assets (covers/thumbnails, titles, descriptions, tags, cover copy) for Douyin, WeChat Channels, Bilibili, Xiaohongshu and other platforms. Researches the product's real-world logic before any product image is generated, traces every generation back to verified source images, and records review evidence. Prepares publish packages; never publishes on its own.
license: Apache-2.0
---

# Social Asset Studio

One workflow for covers, titles, descriptions, tags and brand alignment. State which guidance you actually loaded for the task. Reading a reference is not the same as running a check, and neither is the same as a passing result.

## Load by task

- Copy only, or a multi-platform publish package: [titles and fields](references/title-copy.md).
- Covers or multiple versions: [platform concepts](references/platform-design.md) and [quality gates](references/quality-gates.md).
- Doors and smart locks: [door, lock and person logic](references/door-lock-physics.md).
- Any real product in the image: [product research](references/product-research.md) **first**, then [source assets](references/source-assets.md). Both are mandatory before generating.
- Brand work: [brand profile](references/brand-profile.md). Brand guidelines make results better when you have them; the skill still works without them.
- Prism MCP/CLI: [tool adapter](references/prism-tools.md). A standalone install can use the host's own image tools; the Prism service is not required.

## Order of work

1. **Facts.** Extract content facts, user references, target platforms, ratios, counts, mandatory copy, prior approvals and budget. Don't re-ask what the user already gave. A general creative brief is enough to start reversible preparation; publishing needs its own authorization.
2. **Product logic.** If a product appears, follow [product research](references/product-research.md): search the web and the user's material for the exact model, think the product through (parts, placement, interaction, impossible views, traps), then write the JSON product logic sheet. Each concept's scene is compiled from that sheet with `scripts/compile_product_rules.py` into prompt constraints and a review checklist, so the rules adapt to each product. No product image is generated until the sheet exists and the scene compiles.
3. **Concept cards.** One short card per platform: viewer motivation, content promise, cover copy, single hero visual, scene mechanism, title structure, source images, and what substantively differs from the other platforms. Every scene is checked against the product logic sheet before it is approved for generation. Platform tone is an editorial choice, not an algorithm guarantee.
4. **Representative draft.** Make one representative draft, review it for real, then expand. If the user asked to approve before continuing, stop at a viewable draft and wait. No explicit approval means not approved, and approval of one draft does not extend to every platform.

Multi-platform sets must differ in at least one of: scene, visual mechanism, information relationship, narrative viewpoint. Changing only color, font weight, position or product angle does not count. A second version needs its own mechanism. Portrait and landscape are composed separately. Count against a platform × version × ratio matrix; failed drafts don't count toward the total.

## Product and brand hard rules

Every generation and every revision re-sends the verified original product images and records their path and hash. Caches, earlier outputs, model names in the prompt and model memory never replace the originals. Search local originals first (Everything when available, otherwise native file search). Verify model/version by opening the file, not by filename.

Lock structure, components, wordmark and proportions, then still compare the actual output. Generate or edit product and scene together so perspective, light direction, color temperature, reflections, occlusion, contact and installation agree **and** match the product logic sheet. A product shown in a physically impossible way (wrong side of a door, wrong orientation, parts that cannot coexist in one view) fails, however good it looks. Don't paste a hard-edged original over a broken render to hide a product error. If an exact wordmark must be composited, keep its transparent edge and clear space without adding a backing plate.

## Records and minimal revisions

Save concept cards, the product logic sheet, full prompts and a local manifest in the task output folder. For each call, list the originals actually passed in and their role (product / style / logo). Never claim a tool received an image parameter it doesn't support.

Record the real provider, tool, job/path and reference links. Review the full image, the side-by-side with originals, the compiled product-logic checklist and a phone-size thumbnail before writing a verdict. Locate the defect (product, logic, fusion, composition, copy, mark) instead of regenerating the whole batch. If the same defect survives two revisions, report the blocker and candidates and stop spending credits.

Use the structure in [manifest.example.json](references/manifest.example.json). `python scripts/check_delivery.py <manifest.json>` checks local files, source hashes, per-attempt references, the product-logic review, counts and ratios. It does not replace visual judgment or user approval.

## Delivery states

Keep these distinct: planned / generated, awaiting review / failed check / user-approved / final delivery. Report actual images, platform, version, ratio, path, what was checked and what is unresolved. A loaded skill, a successful API call or a file count is never a quality pass, and no click-through or virality is promised.

A publish package has separate `title / description / tags / cover_copy / cover_path`, plus `short_title` for WeChat Channels. A copy-only request does not start image generation; a cover-only request does not publish.

## Maintenance and licensing

This repository is the canonical source. Prism vendors a copy under `docs/hermes-skills/social-asset-studio/`; the older `prism-title-topic` and `prism-social-content` skills remain as compatibility entry points. Sources, licenses and pinned commits are in [SOURCES.md](SOURCES.md). Product images, brand marks, fonts, brand manuals and samples are not covered by the code license and are never shipped with the skill. Brand- or client-specific adapters live in their own private repositories and are loaded on top of this skill.
