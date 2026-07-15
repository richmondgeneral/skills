---
name: catalog-voice-rewrite
description: Generate new product descriptions in the Richmond General curated mercantile voice for one or more catalog items. Triggers when the user mentions "rewrite this item", "redo the description", "apply the voice to this product", "make this on-brand", "rewrite from vendor copy", or asks to fix items flagged by the catalog-voice-audit skill. Takes existing item data plus optional research context, produces structured descriptions following the form-anchor-condition-use template, and batch-updates items via the Catalog API.
---

# Catalog voice rewrite

## When to use

For one-off or batch rewriting of Square catalog item descriptions in the Richmond General brand voice. Common scenarios:

- User flagged an item: "the Rose Sage Bundle description is too long"
- Audit returned a list: "rewrite the 12 items the audit flagged"
- New vendor import: "I just added 8 Roots And Leaves products  -  make them sound like us"
- Single item polish: "this works but feels off  -  try again"

## Voice template (mandatory structure)

Every rewrite follows this four-part structure:

```
[Form + provenance + era  -  1 sentence opening with the item, not the brand]

[Cultural/historical anchor  -  1-2 sentences placing the item in a tradition]

[Condition + dimensions + materials  -  1-2 sentences, honest about wear]

[Practical close  -  1 sentence about how the buyer might use it]
```

Three paragraph breaks. Total length 50-100 words for most items, up to 150 for marquee pieces with documented provenance.

See the **Patterns from past rewrites** section below for the cultural anchors already used in Richmond General descriptions.

## Procedure

### Step 1: gather context

For each item to rewrite, you need:

- Current `name`
- Current `description` (for reference / to identify what to keep)
- Current `version` (the integer object version, needed for the Step 6 update)
- Current `image_ids` (the photos can hint at form, era, condition)
- Variation data: SKU, price, dimensions if encoded there
- `categories` (tells you what shelf this lives on)

If the user has provenance information that's not in Square (estate sale source, seller notes, prior listing copy), ask for it before drafting.

### Step 2: identify the four anchors

For each item, identify:

1. **Form & provenance**: What is it? When was it made? Who made it?
2. **Anchor**: What tradition, era, or cultural moment does this connect to? See the **Patterns from past rewrites** section below for ones already used  -  reuse for consistency.
3. **Condition note**: For vintage items, name specific wear. For new items, name materials and dimensions.
4. **Use close**: How does someone live with this?

If you can't answer #2, the item may need research (web search, maker-mark lookup, era identification). Pause and ask the user before drafting a generic anchor.

### Step 3: draft the description

Write to the four-part template. Constraints:

- Open with the item, not the brand: "1954 Pennwood flip clock" ? / "Richmond General proudly offers..." ?
- Banned words (always remove): amazing, incredible, stunning, magnificent, perfect for, must-have, iconic, treasure, beautiful (as standalone), elegant, luxurious, transports you, harkens back to, step back in time
- Cut all exclamation marks unless quoting
- Replace "buy now"/"order today" closes with concrete use scenarios
- Use em dashes for asides (` - `), not parentheses, to keep the voice readable aloud
- Italicize Latin botanical names (`*Limonium sinuatum*`)
- Bold the form in the first sentence (HTML: `<strong>`)

### Step 4: write both formats

Square stores two versions of each description:

- `description`  -  plain text with newlines (`\n\n` between paragraphs)
- `description_html`  -  formatted with `<p>`, `<strong>`, `<em>` tags

Always update both. The plain text shows in some Square POS contexts; the HTML is what renders on the storefront.

### Step 5: confirm before deploying

Show the user:

```
[ITEM ID] Current Name
?????????????????????????????????????
BEFORE (current desc, truncated to 60 words)
?????????????????????????????????????
AFTER (new desc, full)
?????????????????????????????????????
```

For batches, show 2-3 examples and ask "shall I apply the same template to the rest?"

### Step 6: deploy via batch update

```
service: catalog
method: batchUpdateObjects
request: {
  sparse_update: true,
  idempotency_key: "<uuid>",
  batches: [{
    objects: [{
      type: "ITEM",
      id: "<item_id>",
      version: <latest_object_version_number>,
      item_data: {
        description: "<plain text>",
        description_html: "<formatted html>"
      }
    }, ...]
  }]
}
```

Send the object's **current `version`** (the latest integer version, read from the item in Step 1) on every update. When `version` is supplied it must match the version in the database, or Square rejects the write as conflicting; on a version conflict, re-fetch the item, regenerate the diff, and retry.

Keep batches to 10 items or fewer per Square's recommendation. Use one batch per call but multiple batches per call when ?10 each.

### Step 7: cross-sell wiring

After rewriting, look at related items in the same category. If two items naturally pair (workbook + brush set, mug + sage bundles, 1926 reprint + 1931 reprint), add a "pairs with" or "companion to" line in each item's `use_close` paragraph. This is how the voice does merchandising work.

## Patterns from past rewrites

Documented below  -  the cultural references already used and the items they appear on. Examples:

- **Sage bundles** -> "Victorian general stores," "frontier healers," "old-time apothecaries"
- **Watercolor kits** -> "Palmer paint-by-number kits of the 1950s," "stationers a century ago"
- **Vintage books** -> "Victorian parlors," "Space Race kids," "Dover Publications reprints"
- **DVDs** -> "mid-2000s horror revival," "DVD compilation era"
- **Furniture** -> "Railway Express Agency, 1929-1975," "American gift shops, 1970s-90s"

Reuse anchors across similar items so the catalog reads as one coherent shop.

## Anti-patterns (do not generate)

- Opening with "Richmond General [verb]..."  -  leads with the brand instead of the item
- Bullet-point lists of features  -  the voice uses paragraphs
- "This [item] is [adjective]" sentences  -  replace with what specifically is in/on/about the item
- Promotional CTAs at the end  -  "Order yours today!" never appears
- Generic gift framing ("Perfect for any home")  -  replace with the specific occasion or use
- Citing reviews or testimonials  -  the voice doesn't do social proof

## Related skills

- `brand-voice`  -  the voice rules
- `catalog-voice-audit`  -  find items needing rewrite
- `brand-guidelines`  -  visual identity
