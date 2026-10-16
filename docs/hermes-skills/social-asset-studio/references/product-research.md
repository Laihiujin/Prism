# Product research and product logic

A cover can only be right about a product if the person making it understands the product. Image models know what products *look like*; they do not know how products *work*, where they go, or what can physically be seen at once. That knowledge has to be researched and written down before generation, then used as a hard check afterwards.

## When this is required

Whenever a real product (or its packaging, interface or installation) appears in a generated or edited image. Pure studio packshots still need the sheet, but only the identity and orientation sections apply.

## 1. Research sources, in order of authority

1. User-supplied material: spec sheets, manuals, installation guides, product pages, launch decks, real photos of the product in use.
2. The brand's official pages and manuals (installation diagrams are especially valuable).
3. Real-world photos and videos of the product installed or in use (retailer galleries, user reviews, installer videos). Use them to learn context, not to copy assets.
4. General category knowledge (how this kind of product is normally built, installed and used). Mark anything from this tier as *inferred*.

Record each source in the sheet. Anything you could not verify stays *unknown*; do not fill gaps with plausible-looking detail.

## 2. The product logic sheet

Write one sheet per product (and per variant if variants differ physically). Keep it short and concrete.

| Section | Questions to answer |
| --- | --- |
| Identity | Exact model/variant, colorways, which source images show which face. |
| What it is for | The job it does for the user; the problem it solves; the core claim(s) the content is allowed to make, with source. |
| How it works | The user's interaction sequence (approach, unlock, open, operate, close…). Which part is touched, seen, heard, at which moment. |
| Parts and faces | Every externally visible part and which face/side it belongs to (front/back, inside/outside, top/bottom, user side/wall side). |
| Installation / placement | Where it is mounted or placed, what it attaches to, orientation (which way is up, which way it faces), clearances, what is hidden inside the surface it mounts on. |
| Environment | Where it is realistically used (indoor/outdoor, home/office/vehicle), lighting, weather, typical surroundings, scale relative to people and furniture. |
| Users | Who uses it and how they hold, reach or look at it; hand size and eye level when relevant. |
| Physical constraints | What must be true in any image. Written as checkable rules (see below). |
| Forbidden depictions | Concrete things that would be wrong: impossible views, wrong mounting, borrowed parts from other models, invented features, unsafe or illegal usage. |
| Allowed liberties | What may be stylized (exploded views, cutaways, floating packshot, dramatic light) and how such images must signal they are not a literal scene. |
| Open questions | What is still unknown and which images are blocked by it. |

### Writing constraints as checkable rules

Each constraint should be verifiable by looking at the image:

- "The exterior unit is visible only from outside the door; the interior unit only from inside."
- "In one camera view of a closed door, at most one of the two units can be seen. Showing both requires an open door seen edge-on, a split-screen, or an explicitly labeled exploded/product layout."
- "The handle hinge side matches the door's opening direction."
- "The device is mounted vertically, keypad below the camera, at roughly hand height."
- "The camera faces outward, toward a visitor, not into the home."

The examples above use a two-part door device. The same pattern applies to any product with parts or faces that can't coexist in one view: wall switches and their back boxes, two-sided appliances, car interiors and exteriors, packaging fronts and backs, wearables on the correct hand or wrist, phone screens versus phone backs.

## 3. Scene logic check (before generating)

For each concept card, answer in one line each:

1. Where is the camera physically standing, and is that place reachable?
2. Which product faces can that camera see? Do they match the sheet?
3. Is the product mounted/placed exactly as the sheet says (surface, orientation, height, side)?
4. Is the scale right relative to people, doors, hands, furniture?
5. Does the moment depicted match a real step in how the product works?
6. If a liberty is taken (packshot, exploded view, split frame), is it obvious to the viewer that it is a presentation, not a literal scene?

Any "no" or "unsure" sends the concept back for revision. Don't spend generation credits on a concept that fails this check.

## 4. Prompting from the sheet

Turn the relevant constraints into explicit prompt language (e.g. "only the exterior unit is visible, mounted on the outside face of a closed door; no interior hardware visible"). Prefer describing the one correct view over listing negatives. Keep sending the original product images every attempt (see [source assets](source-assets.md)).

## 5. Product-logic review (after generating)

Check the actual image against every constraint in the sheet and record pass/fail per rule in the manifest (`product_logic_review`). A single physical-logic failure fails the cover even if fidelity, lighting and copy are perfect. Typical failures to look for:

- Two parts that belong on opposite sides of something visible on the same side.
- Mounted on the wrong surface, wrong orientation, floating, or with no visible way of being attached.
- Wrong scale or reach height.
- Parts borrowed from another model or invented.
- A usage moment that would never happen (operating the device from the wrong side, product active with no power or context).

## 6. Keep it reusable

Save the sheet next to the task outputs. For recurring products, keep the sheet in the brand's private adapter so the next task starts from verified logic instead of re-deriving it. Update it when the product changes; never let a generated image become the source of truth for product logic.
