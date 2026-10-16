# Product research and product logic

A cover can only be right about a product if the person making it understands the product. Image models know what products *look like*; they do not know how products *work*, where they go, or what can physically be seen at once. That knowledge is researched, thought through and written down **before** any prompt is written. It then drives the prompt and the review, so the rules change with the product instead of being one fixed template.

Pipeline: **research (web + user material) → think it through → product logic sheet (JSON) → per-concept scene choice → compiled prompt constraints + review checklist → generate → review against the same rules.**

## When this is required

Whenever a real product (or its packaging, interface or installation) appears in a generated or edited image. Pure studio packshots still need the sheet, but only identity, units and allowed liberties apply.

## 1. Research (web search is mandatory)

Do real searches every time a product is new to you, or the sheet predates the product's latest version. Use the host's web search and fetch tools; don't answer from model memory.

Search in this order and log each result in the sheet's `sources` list (URL or file, what it confirmed, `model` or `category` level, date checked):

1. User-supplied material: spec sheets, manuals, installation guides, launch decks, real photos.
2. Official brand pages, manuals and installation diagrams. Search the model name with words like manual, installation, dimensions, specs, 说明书, 安装, 尺寸, 参数.
3. Retailer listings and spec tables. Cross-check numbers between at least two.
4. Real-world use: installer videos, user reviews with photos, unboxing, teardowns where relevant.
5. Category references: manuals of comparable products from other brands. Use them only to confirm how the *category* works (installation side, orientation, interaction), and mark those facts `category`, never model-specific.

Rules:

- Search in every language of the product's market (for a Chinese product, Chinese **and** English).
- Always search brand **and** model together, and check every result is from that brand. Different brands reuse the same model names; record any such trap in `product.name_trap`.
- Competitors and similar products are valuable for understanding how the category works (installation, interaction, how people use it), but stay `category` evidence and never become model facts.
- If the exact model can't be found, record `"model_specific_found": false`, fall back to category facts, list what is still unknown in `unknowns`, and block any image that depends on an unknown.
- Never copy images or text from sources into outputs. Research informs logic; product appearance comes only from verified source assets.

## 2. Think it through before writing anything

Before filling the sheet, reason through the product slowly and concretely, and keep the notes in the task folder:

1. **Decompose.** List every physical part. For each: which unit it belongs to, which face it is on, what it does.
2. **Place it in space.** Where does each unit sit in the real world? Which surface, which side of that surface, which way up, at what height, facing whom?
3. **Walk the interaction.** Step through one real use from start to finish: who approaches from where, what they see first, what they touch, what responds. Note which parts are visible at each step and from which side.
4. **Find the impossible views.** Which parts can never be in one frame together? Which camera positions can't exist (inside a wall, both sides of a closed door at once)? Which states can't coexist (door closed and its edge hardware visible)?
5. **Check scale and people.** Size relative to hands, faces, doors and furniture; how people hold or reach it.
6. **Check claims.** Which features does the content mention, and which source confirms each?
7. **Name the traps.** What will an image model most likely get wrong for this product: merging units, borrowing parts from similar products, mirroring, the wrong count of lenses or buttons?

Only then write the sheet.

## 3. Product archetypes (starting rules)

Pick every archetype that applies. Each one gives default questions and rules; adapt them to the actual product, delete what doesn't apply, and add what the research found.

| Archetype | Typical examples | Default rules to adapt |
| --- | --- | --- |
| Two-sided installed | Door locks, intercoms, through-wall devices | Each unit is visible only from its own side; a closed barrier hides the other side; showing both needs an edge-on open view, a divided split frame or a packshot. |
| Surface-mounted | Switches, wall lights, cameras, faucets, shelves | Correct surface, orientation and height; visible fixing; nothing floating; cables and pipes enter the surface, not the air. |
| Handheld / portable | Phones, tools, cosmetics, remotes | Plausible grip and hand scale; which face points at the user vs the camera; screen content matches the moment. |
| Wearable | Watches, glasses, earbuds, clothing | Correct body part and side, fit, scale on the body; straps and hinges mechanically possible. |
| Appliance / furniture | Kitchen appliances, robot vacuums, chairs | Floor or counter contact, clearances, door/drawer opening direction, power or water connection. |
| Vehicle / large equipment | Cars, bikes, machines | Scale to people and roads, correct number of wheels and parts, interior and exterior views kept separate. |
| Packaged goods | Food, beverages, retail boxes | Front vs back panel, label orientation, seal state, realistic shelf or table setting. |
| Screen / software | Apps, dashboards, device UIs | Only UI that sources show; don't invent screens; the device showing it is plausible. |

## 4. The product logic sheet

Keep one JSON sheet per product (and per variant if variants differ physically), using [product-logic.example.json](product-logic.example.json) as the template. Store it with the task outputs; for recurring products, keep it in the brand's private adapter.

| Field | Content |
| --- | --- |
| `product` | Exact model/variant, archetypes, `model_specific_found`. |
| `sources` | Each source with what it confirmed, its level and the date checked. |
| `purpose` | The job it does; allowed claims, each tied to a source id. |
| `units` | Each physical unit: side/surface, orientation, height, visible parts, environment. |
| `interaction` | The real use sequence, step by step, with the units visible at each step. |
| `constraints` | Checkable rules, each with `id`, `applies_to` (unit ids or `*`), `rule`, `prompt` (positive wording), `check` (what to look for) and `source`. |
| `forbidden` | Concrete wrong depictions, each with short negative prompt wording. |
| `liberties` | Allowed stylizations (packshot, split frame, exploded view), which units they allow together, and the prompt wording that makes them read as presentation. |
| `unknowns` | Open questions and which images they block. |

Constraints must be checkable by looking at the image, for example:

- "In one view of a closed door, at most one unit is visible."
- "The exterior unit's camera faces the visitor, not the home."
- "Interior-unit scenes are inside the home; exterior-unit scenes are in a corridor or porch."

## 5. Per-concept scene choice

For each concept card, decide which units are visible and whether a liberty is used, then answer:

1. Where is the camera physically standing, and is that place reachable?
2. Which units and faces can that camera see? Do they match the sheet?
3. Is each unit mounted or placed exactly as the sheet says?
4. Is scale right relative to people, doors, hands and furniture?
5. Does the moment match a real step in `interaction`?
6. If a liberty is used, will the viewer read it as a presentation?

Any "no" or "unsure" sends the concept back. Don't spend credits on a concept that fails this check.

## 6. Compile prompt constraints and the review checklist

```sh
python scripts/compile_product_rules.py product-logic.json --visible exterior_unit
python scripts/compile_product_rules.py product-logic.json --visible exterior_unit,interior_unit --liberty split
```

The script refuses impossible scenes (two units that can't share a view without an allowing liberty) and prints:

- a **prompt constraint block**: identity and visible parts of only the units in view, their mounting, orientation and environment, the applicable constraint wording, the liberty wording if any, and short negatives from `forbidden` plus "no <unit>" for every unit that must stay out of frame;
- a **review checklist**: every applicable constraint's `check` and every forbidden item, to tick off on the actual image.

Paste the constraint block into the generation or edit prompt after the creative description. Keep sending the original product images on every attempt (see [source assets](source-assets.md)). Prefer describing the one correct view over long negative lists.

## 7. Review against the same rules

Check the actual image against the compiled checklist and record the result in the manifest (`product_logic_review`). One physical-logic failure fails the cover even if fidelity, lighting and copy are perfect. When a new failure shows up, add it to the sheet as a constraint or forbidden item, so the next run catches it automatically.

## 8. Keep it alive

Update the sheet when the product, its packaging or its claims change. A generated image is never a source of truth for product logic. A sheet with `model_specific_found: false` stays provisional until official material confirms it.
