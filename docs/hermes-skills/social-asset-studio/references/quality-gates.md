# Quality gates and states

## Before generating

Verify facts, product originals, logo and style sources, and record the originals' paths/upload IDs and hashes for every call. The product logic sheet exists and every concept card has passed its scene logic check. Concept cards pass the platform difference check before generation starts. Re-texting the same background can't be fixed by producing more of it.

## Look at the actual image

1. **Source comparison:** model, silhouette, components, lens/windows, keys, screen, knob and wordmark, item by item.
2. **Product logic:** every item of the checklist compiled for this scene by `scripts/compile_product_rules.py`. Correct face visible from the camera position, correct mounting surface and side, orientation, scale, reach height, a realistic usage moment. Parts that belong on opposite sides are never shown together on one side.
3. **Fusion:** perspective/scale, installation structure, light direction/color temperature, material reflections, contact shadows, occlusion edges. The product must not float or look cut from another picture.
4. **Brand:** transparent logo structure, size, position and clear space; exact text; color aligned with the brand guidelines when available. No fake transparency with a backing plate; the logo never overpowers the title.
5. **Visual:** one focal point, clear hierarchy, appropriate negative space, no crop accidents, title correct character by character.
6. **Phone thumbnail:** view the whole cover at about 160px and 320px wide. Title, subject and product must still be recognizable. Don't judge only at full size.
7. **Side by side:** without text, platforms/versions still differ substantively. Not one landscape reused everywhere.

Any error in core product structure, product logic, logo or mandated copy, or a serious fusion failure, marks the cover `failed` and it doesn't count toward completion. A provider success response or a format check never overrides this.

## States

planned → generated → needs_review → approved / rejected → delivered.

Record local visual review and user approval separately. When the user wants approval before expanding, require explicit `approved_by_user=true` bound to the file's SHA-256. Praise for one detail is not approval of every platform. Generating or editing a file invalidates its old approval. If the same issue survives two revisions, report evidence and gaps and stop paid batch retries.

## Tool checks

`check_delivery.py` checks that files exist, PNG dimensions, exact ratio, source hashes, that every attempt includes the original product references, that a product-logic review passed for covers that show a product, candidate state/approval hashes and the final count. It doesn't do OCR or perception and can't prove the originals actually reached the provider or that the image is good; call records and visual evidence must still be real.

The delivery list states only checks that actually ran; reading a file is not running the skill's script.
