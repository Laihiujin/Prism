# Source-asset tracing and fidelity

## Local discovery

1. Prefer paths the user gave; confirm the file exists and open it. Then search locally (Everything when available) by product name / model / version, brand asset folders and neighboring project assets.
2. If Everything's tool or CLI is available, use its real interface. If not, say you are falling back to native file search; don't claim it was called. Search only task-relevant folders and filenames, and never print accounts or secrets.
3. Distinguish front, side, back/interior parts and different models in the same series. Compare at least the user-confirmed image with what you found. If you can't decide, block the affected product image and continue other preparation.
4. The local manifest records asset_id, path, SHA-256, model/version, role and what was visually checked. Paths and hashes stay in local task output; a published skill repository only keeps a redacted template.

## Four reference roles

- `product_original`: the single authority for product structure. Every generation or revision that involves the product must actually pass in the currently verified original.
- `logo_original`: authority for the wordmark and its transparency. Original vector / transparent PNG first; shape and spacing are never left to the model.
- `style_only`: user-supplied cover screenshots. Extract title size, visual weight, density, lighting and scene mechanism only. Never copy a different product or a spokesperson from them into this task.
- `prior_candidate`: for continuity and local edits. Always used alongside the original product image, never as the sole product authority.

If a provider can't accept local reference images, pick a tool that really supports them, or upload as its docs describe and reference the upload. Don't silently fall back to text-to-image, don't say "the cache is enough", and don't fake an upload. Upload only what the task needs.

## Mandatory checks

Silhouette, proportions, component count, lens/sensor windows, key rows, screen, ports, handle, knob, seams, markings, material and color.

Occlusion or cropping may serve the composition, but hiding key areas is not a way to pass fidelity. Unpublished internals and screen UI stay unknown; don't invent them. Close-ups need detail the originals support; never generate precise-looking fake structure.

## Fusion and re-check

Camera perspective, installation, scale, light direction and softness, color temperature, reflections, ambient color, contact shadows and occlusion must be consistent with each other **and** with the product logic sheet ([product research](product-research.md)). Parts that belong on opposite sides of a surface must never appear together on the same side.

Pasting the original onto an incompatible landscape or plinth is not fusion. Compositing is allowed only with equally strict physical fusion and source verification. Fidelity doesn't replace fusion, and fusion doesn't replace fidelity.

Every revision re-sends the originals and is re-checked and versioned. A failed draft stays failed and never becomes a new product source.
