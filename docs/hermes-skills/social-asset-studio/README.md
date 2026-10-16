# Social Asset Studio

A skill for planning, generating and reviewing social-media assets (covers/thumbnails, titles, descriptions, tags, cover copy) for Douyin, WeChat Channels, Bilibili, Xiaohongshu and more.

Entry point: [SKILL.md](SKILL.md). It covers platform concepts, titles/descriptions/tags, **product research and product logic** (how a product works, where it is installed, what can physically appear in one view), source-image tracing per call, product/scene fusion, optional brand alignment, review records and the Prism MCP/CLI adapter. It works standalone; the Prism service is not required.

Install by copying this repository into the host's skill folder as `social-asset-studio/`. Prism vendors a copy at `docs/hermes-skills/social-asset-studio/`.

```text
SKILL.md
references/       # platforms, titles, product research, source assets, brand profile, tools, quality gates, manifest template
scripts/          # product-rule compiler, delivery-evidence checker and tests
agents/           # agent metadata
third-party/      # MIT notices for method references
```

## Verify

```sh
python scripts/test_check_delivery.py
python scripts/test_compile_product_rules.py
python scripts/compile_product_rules.py product-logic.json --visible <unit ids> [--liberty <id>]
python scripts/check_delivery.py path/to/manifest.json
python scripts/check_delivery.py path/to/manifest.json --require-approved
```

The example manifest is a template, not a passed delivery. The checker doesn't prove image quality, which references a provider actually used, brand authorization or user approval; those still need real call evidence and human review.

## What is not here

No product images, logos, brand manuals, fonts, samples, real local paths, private memory or keys. Brand guidelines improve results when you have them, but they belong in a separate private brand adapter (see [references/brand-profile.md](references/brand-profile.md)), never in this repository.

License: Apache-2.0. Method sources and MIT notices: [SOURCES.md](SOURCES.md) and `third-party/`.
