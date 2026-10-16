# Thumbnail QA checklist

## Content

- [ ] Platform and content type are identified.
- [ ] Style ID and platform or generic ratio are identified.
- [ ] Headline matches the user's topic and contains no invented claim.
- [ ] Spelling, numbers, brand names, and punctuation are correct.
- [ ] Reference-image text was not mistaken for a user instruction.

## Real-asset fidelity

- [ ] Every exact-use screenshot, product, logo, chart, and portrait comes from the supplied source.
- [ ] No fake UI or AI lookalike replaced a real asset.
- [ ] Portrait identity, face, hands, clothing, logos, and edges survive cutout/editing.
- [ ] Collages remain readable enough to function as proof.

## Visual hierarchy

- [ ] One promise, one dominant subject, and one supporting proof area are obvious.
- [ ] Main title is readable at a small feed preview.
- [ ] Contrast is sufficient without excessive outlines or glow.
- [ ] Gradient improves the title-to-image transition without hiding key proof.
- [ ] Essential content stays inside the recommended safe area.
- [ ] For Creator Impact covers, the hook occupies roughly 35–45% of a vertical canvas and remains readable at feed size.
- [ ] The real person occupies 35–55%, bleeds naturally off an edge when useful, and is never put back inside a photo frame.
- [ ] A usable topic screenshot or environment drives the background; no unrelated abstract field replaces it.
- [ ] The proof card, count, arrow, and up to three check items form one compact flow with no unexplained central dead zone.
- [ ] Portrait cutout was checked on light and dark backgrounds; there is no rectangular residue, black halo, clipped hat/hair, or broken shoulder edge.
- [ ] Generated background elements do not contain person-shaped placeholders, fake screenshot frames, pseudo-text, generic comic bursts, or unrelated gaming decoration.
- [ ] Project files and delivery notes use the repository's `Creator Impact / 真人高密度大字` name.

## Technical export

- [ ] Pixel dimensions and aspect ratio match the selected preset.
- [ ] A ratio adaptation was recomposed rather than stretched.
- [ ] Output is PNG or JPG in sRGB.
- [ ] No accidental alpha fringe, crop, stretching, or compression artifact is visible.
- [ ] File opens successfully at full resolution.
- [ ] `verify_thumbnail.py` passes, or a deliberate exception is documented.

## Rights and delivery

- [ ] Commercial-use wording matches the documented asset rights.
- [ ] Third-party or public-figure demo limitations are disclosed.
- [ ] Delivery lists the file path, dimensions, preset, preserved assets, and assumptions.
