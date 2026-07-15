---
name: catalog-voice-audit
description: Scan Square catalog item descriptions against the Richmond General brand voice and flag drift. Triggers when the user mentions "audit descriptions", "check the catalog voice", "find items needing rewrite", "are any items off-brand", "voice check", or asks for a quality pass on item copy. Identifies hype words, missing era anchors, missing condition information, missing practical use notes, and descriptions that exceed length thresholds. Returns a prioritized list of items needing attention with specific feedback per item.
---

# Catalog voice audit

## When to use

Anytime you want to know which items in the Square catalog have descriptions that drift from the curated mercantile brand voice. Useful:

- Before a major catalog refresh
- After bulk-importing items from a vendor (vendor copy is almost always off-brand)
- As a quarterly quality pass
- Before a marketing push, to make sure listings sound like the same shop

## What this skill checks

Each item description is scored against the brand-voice rules from the `brand-voice` skill. Specific checks:

### Red flags (hype / off-brand)

| Flag | Why it's a problem |
|---|---|
| "amazing", "incredible", "stunning", "magnificent" | Hype words; the voice avoids superlatives in favor of specifics |
| "perfect for", "must-have", "iconic", "treasure" | Generic sales copy; replace with concrete use cases |
| "buy now", "while supplies last", "order yours today" | Direct-CTA language; the voice trusts the shopper to make the decision |
| "Beautiful", "elegant", "luxurious" (as standalone adjectives) | Empty descriptors; replace with what makes it beautiful |
| "Step back in time", "harkens back to", "transports you" | Time-travel cliches; the voice describes the era rather than invoking it |
| Excessive exclamation marks (>1 per description) | Hype indicator |
| ALL CAPS phrases (>5 words) | Sales-flier voice, not shopkeeper voice |

### Missing-piece flags

| Flag | What's missing |
|---|---|
| `era_anchor: missing` | No reference to a time period, cultural moment, or maker tradition |
| `condition_note: missing` | No statement about condition for vintage items, or dimensions for new items |
| `use_close: missing` | No closing line about how the buyer might use the item |
| `description_too_long` | >150 words; the voice prefers 50-100 words for most items |
| `description_too_short` | <30 words; needs more substance |

### Structural flags

| Flag | What's wrong |
|---|---|
| `opens_with_brand` | Description opens with "Richmond General [verb]..." instead of leading with the item |
| `bullet_list` | Bullet points; the voice uses paragraphs |
| `no_paragraph_breaks` | Single block of text; the voice uses three short paragraphs |
| `vendor_copy_detected` | Phrases that look pulled from a wholesale vendor sheet (e.g., "Item features...", "Perfect addition to any...") |

## Procedure

### Step 1: scope the audit

Ask the user which subset to audit:

- All items in the catalog
- Items in a specific category
- Items modified in a date range (e.g., "items added since X")
- Specific item IDs

### Step 2: fetch items

Use Catalog API `searchItems` with the relevant filter. Pull `description_plaintext` for each.

If the search returns too much data (Square's response size cap), batch by category or by date range.

### Step 3: score each description

For each item, run all the flags listed above. Compute a score per item:

```
score = base_100
  - 8 per red flag
  - 5 per missing-piece flag
  - 3 per structural flag
```

Categorize:
- **Pass** (score ? 85): looks on-brand
- **Drift** (60-84): needs touch-up
- **Fail** (<60): needs full rewrite

### Step 4: present the report

For each item below pass:

```
[ITEM ID] Item Name (score: 67  -  DRIFT)
  Red flags: "amazing" used 2x, "perfect for any home" detected
  Missing: era_anchor, use_close
  Suggested action: rewrite using brand-voice template
```

Group the report by category and by severity. Show the user how many items in each bucket before listing.

### Step 5: offer next steps

- "Rewrite the failing items now" -> invoke `catalog-voice-rewrite` skill
- "Export the report as markdown" -> write to workspace
- "Just flag these for me, I'll rewrite later" -> output the list

## Voice rules reference

Pull the full brand-voice rules from the `brand-voice` skill before scoring. Don't hardcode the rules in this skill  -  they should stay in one place.

See the `catalog-voice-rewrite` skill's **Patterns from past rewrites** section for the historical/cultural anchors already used in Richmond General descriptions. When suggesting rewrites, you can pull from those for consistency.

## Related skills

- `brand-voice`  -  the voice rules themselves
- `catalog-voice-rewrite`  -  generates new descriptions for flagged items
- `brand-guidelines`  -  visual identity (separate concern from voice)
