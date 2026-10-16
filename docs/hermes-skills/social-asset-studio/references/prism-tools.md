# Prism and host tool adapter

## Discover capabilities

Read the project's tool catalog / CLI / MCP schema; don't invent APIs from skill names. Current Prism entry points:

- `generate_cover(file_id, platform_name, aspect_ratio, prompt, style_hint, use_first_frame)` returns a `job_id`.
- `get_cover_job(job_id)` reports success/failure and the actual path.
- `list_material_covers(file_id)`, `select_material_cover(file_id, cover_id)`.
- `adapt_material_cover(file_id, path, platform)`; `path` is relative to the material library.

CLI: `python prism_cli.py tool invoke <tool name> --json-file <params file>`.

`generate_cover` currently supports only 3:4 / 4:3. `use_first_frame` means the video's first frame only, not arbitrary local product or logo references, and there is no parameter for original product images. For brand images that need original references, use the host's real reference-image generate/edit entry point; don't use unsupported Prism parameters or quietly fall back to pure text-to-image.

## Tool choice

A provider the user named comes first. Otherwise use the image tools and skills the host has right now. If local image references are supported, pass originals directly; for upload-based tools, get asset IDs as documented and record the mapping to original files. Don't install model backends, switch to paid services or ask for keys that aren't needed.

Without the needed capability, deliver the prepared plan, asset list, product logic sheet and prompts and state the blocker; never say images were produced. When tool ratios differ from the final uploader, solve crop/re-layout first; never stretch.

## Discovery and compatibility

Prism vendors this skill at `docs/hermes-skills/social-asset-studio/`, synced to the Hermes creative category at session setup. The older `prism-title-topic` and `prism-social-content` route here. A standalone install only needs this skill; all required references are inside it.

Generating and selecting a cover is not publishing. Actual publishing uses the matching platform publish skill and the user's explicit authorization.
