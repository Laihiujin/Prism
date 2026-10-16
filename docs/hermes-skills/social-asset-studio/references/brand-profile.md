# Brand profile (optional)

If brand guidelines are available, results get better: use them. The skill works without them; in that case keep branding restrained and say which brand decisions were assumed.

## Where brand data lives

Brand guidelines, logos, fonts, product photos, approved copy and brand-specific product logic sheets are **not** part of this skill. Keep each brand in its own private adapter (a separate skill or folder loaded alongside this one) or in the task's local files. Never commit them into this repository or into any public repository.

## What a brand adapter should provide

- Location of the official logo files (vector / transparent PNG, light and dark versions) and the current brand guidelines. Real paths stay in the adapter or local manifest.
- Logo rules: placement, minimum size, clear space, allowed color versions, what is forbidden (backing plates, distortion, re-spacing, using the logo as the headline).
- Color palette with values and where each color is appropriate. Not every scene needs to be tinted in the brand color.
- Typography, if licensed fonts are available locally.
- Approved claims and copy, each with its source and the products it applies to.
- Product logic sheets for recurring products (see [product research](product-research.md)), and the model-specific source images they refer to.
- Spokesperson / talent rules, if any (when they may appear, and when the user has said not to use them).
- Known failure cases from past tasks, written as checkable rules.
- Approval history per platform, version and file hash. A draft is never recorded as approved without the user's explicit word.

## Using a brand adapter

Load the adapter after this skill. Adapter rules override the generic defaults here where they conflict, but never override the hard rules on source fidelity, product logic or honest review.
