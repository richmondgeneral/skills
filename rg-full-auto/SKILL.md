---
name: rg-full-auto
description: End-to-end 10-phase workflow for onboarding NEW items to Richmond General from acquisition through sale. Covers appraisal, lot/acquisition cost tracking, photography, Square catalog creation, image upload, payment links, labels, info card publishing, Whatnot CSV listing, and Photos library cleanup. Use when processing a new acquisition from scratch, doing a complete item redo, or user says "list this item" or "sell this". Triggers on "new item", "full workflow", "onboard", "process acquisition", "add to inventory", "process this photo", "list item", "sell this", "add to whatnot". NOT for simple edits to existing items—use rg-item-update for price changes, description tweaks, or adding images.
metadata:
  version: "3.4"
  author: scottybe
  updated: "2026-02-16"
  changelog: |
    v3.4 - Phase 8.3: Post-import metadata editing & shipping profile fix:
    - BREAKING: Fixed Shipping Profile values — old values (0-1 oz, 1-4 oz, etc.) were wrong
    - Correct values: 1-3 oz, 4-7 oz, 8-11 oz, 12-15 oz, 1 lb, 1-2 lbs
    - Added Phase 8.3: Post-Import Metadata Editing (Chrome Automation)
    - Documents category-specific fields (Movie/TV Show Title, Genre, Type, Edition) for Movies > DVDs
    - Clarifies two "Type" fields: CSV listing type vs. edit page content type
    - Added React combobox interaction patterns and known quirks
    - Added Shipping Profile weight heuristic table (DVDs, VHS, books, vinyl, collectibles)
    - Updated CSV example and append command to use 4-7 oz default

    v3.3 - Whatnot Phase 8 overhaul (post DVD batch learnings):
    - BREAKING: Category hierarchy fix — DVDs is Sub Category under Movies, not a Category
    - BREAKING: Prices must be positive integers (no decimals) — added ceil() conversion rule
    - Added Chrome automation upload process with DataTransfer API JavaScript injection
    - Added category hierarchy reference table (Movies>DVDs, Movies>VHS, etc.)
    - Added validation error troubleshooting table
    - Added Whatnot price conversion rule (Square cents → Whatnot whole dollars)
    - Cost Per Item must also be integer

    v3.2 - Fix Square description HTML formatting:
    - BREAKING: Switched from deprecated `description` field to `description_html`
    - Use `<p>` tags for paragraphs instead of `<br>` tags in plain text
    - Use Unicode characters (©, –, —) instead of HTML entities (&copy;, &ndash;, &mdash;)
    - Added "Description Formatting Rules" reference table in Phase 2
    - Updated Square category model to type + tier assignments with `reporting_category` guidance
    - Added per-phase channel classification rules (Square IDs vs GitHub slugs vs Whatnot labels)
    - Prevents double-escaping that rendered raw `<br>` and `&amp;` on richmondgeneral.com

    v3.1 - square-cache reconciliation after writes:
    - Added Step 4.1 to sync square-cache after Phase 2/3/4 write operations
    - Added post-sync verification for exact SKU + cached image linkage
    - Added fallback sync command via square-cache wrapper script

    v3.0 - Photos library cleanup phase + sold-state flow:
    - Added Phase 9: Photos Library Archive — organizes source photos into
      per-item albums under "Richmond General Archive" folder in Photos.app
    - Two archive modes: direct UUID (from cluster discovery) and reverse-lookup
      (filename-to-UUID for Desktop/Downloads imports)
    - New scripts: archive_photos.py (Python wrapper), archive_to_album.scpt (AppleScript)
    - Now a 10-phase workflow (Phases 0–9)

    v2.9 - Whatnot workflow metadata alignment:
    - Updated skill description to reflect 9-phase workflow
    - Added Whatnot CSV listing to top-level capability summary
    - Bumped metadata version to match current Phase 8 coverage

    v2.8 - Square Phase 2 connector compatibility hardening:
    - Added method fallback path (`batchInsertObjects` -> `upsertCatalogObject`)
    - Clarified `idempotency_key` must remain top-level for both payloads
    - Added resilient ID extraction using `id_mappings` before object traversal

    v2.7 - Background removal quality hardening:
    - Phase 0.7 now requests premium remove.bg path (`--model removebg --quality premium`)
    - Aligns onboarding workflow with improved image-processor model preference handling

    v2.6 - Photos Library auto-cluster intake:
    - Added Step 0.4 to discover product photo clusters via photos-library
    - Added UUID-based photo copy flow for the selected cluster
    - Added manual fallback path when clustering is unavailable

    v2.5 - Lot tracking delegation refinement:
    - Moved margin validation before catalog write (Step 1.5)
    - Delegated lot assignment/cost allocation to rg-lot-tracker
    - Removed lot/pricing references moved to rg-lot-tracker

    v2.4 - Review & consistency fixes:
    - Fixed SKU verification: replaced broken searchItems text_filter with cache-based exact match
    - Updated occurred_at guidance to use dynamic ISO timestamp (not hardcoded)
    - Fixed phase count references (8-phase, not 7)
    - Cross-file path consistency fixes

    v2.3 - Anthropic skills update:
    - Enhanced triggers: "list item", "sell this"
    - Aligned with Anthropic Agent Skills best practices

    v2.2 - Post RG-0014 improvements:
    - Added Step 1.0: View image for appraisal using copy_file_user_to_claude
    - Emphasized exact Square MCP method names (batchInsertObjects, batchChange)
    - Gallery index update now uses osascript/sed exclusively (Filesystem:str_replace unreliable)
    - Added reminder to check ~/Desktop for images

    v2.1 - Template enforcement:
    - Created references/info-card-template.html with complete flip card template
    - Phase 7.1 now REQUIRES flip card template with explicit checklist
    - Added placeholder reference table for template variables
    - Added explicit "DO NOT" list to prevent wrong template usage

    v2.0 - Post RG-0013 improvements:
    - Added 20MB file size check before remove.bg (Phase 0.5)
    - Strengthened book-appraiser routing for pre-1970 books (Phase 1)
    - Added explicit inventory API example without catalog_object_type (Phase 3)
    - Documented path case sensitivity issue with Filesystem tools (Phase 7)
    - Added cleanup step for temp files (Phase 7.5)
    - Added remove.bg credit monitoring
---

# Richmond General Full Auto

Complete 10-phase workflow for onboarding new vintage/antique items from acquisition to sale-ready.

## Architecture Note

**Two environments exist:**
1. **Claude's container** - Linux environment where Claude runs. Has `/mnt/user-data/uploads/` for user uploads, `/mnt/skills/` for skills. Can write TEXT files to user's Mac via Filesystem tools.
2. **User's Mac** - Where binary operations (image processing, QR generation) must run via osascript. Has `~/.env` with API keys, git repos, and full filesystem access.

**Rule:** Text files (HTML, CSV, MD) → Filesystem tools. Binary files (PNG, JPEG) → osascript on user's Mac.

**⚠️ Path Case Sensitivity:** Filesystem tools may return paths with wrong case (e.g., `/Users/scottybe/Workspace/` instead of `/workspace/`). For reliability, use osascript for all file operations on user's Mac.

## Quick Reference

| Key | Value |
|-----|-------|
| Square Location | B87BAEZ0NWV34 (Richmond General) |
| Merchant ID | 7MM9AFJAD0XHW |
| SKU Prefix | RG-XXXX (sequential) |
| GitHub Pages | https://richmondgeneral.github.io/items/ |
| Working Directory | `/Users/scottybe/workspace/square/items/` |

### Category Assignment (pick type + tier)

**Type Categories (primary — determines reporting):**

| Category | ID | Use For |
|----------|----|---------|
| Books & Paper | `CLZCJ62H4TTHDQ3ZBYMZQASQ` | Books, magazines, paper ephemera |
| Furniture | `W3EYAJJPTNC46WSLNYI4WH7V` | Stools, trunks, tables, chairs |
| Pottery & Ceramics | `APSTFSN4UXQI44HBFSDTSEX7` | Mugs, vases, plaques, figurines |
| Collectibles | `YQWBSOJDENMXDGUUQ3TGI3HF` | Games, toys, dolls, vintage misc |
| Art & Craft Kits | `F4JQYK4Z5MEBV5VFCDYHIAWT` | Watercolor kits, craft supplies |
| Wellness & Apothecary | `I5PMPWGTVR7IDBL4RUJWN3A4` | Teas, serums, natural products |
| The Apothecary Cabinet | `6E7UZYZFNZBGFRJFH272RVBE` | Sage, ritual items, candles |
| Home & Gifts | `AR3ZTA45KU4BH23AJ7LOLLRA` | Home decor, giftable items |
| Analog | `N35REXL33FZWJNJV24IUQGPN` | Vinyl, pinball, analog tech |

**Tier Categories (secondary):**

| Category | ID | Use For |
|----------|----|---------|
| The New Finds | `P34KX3L7XRZJJ5RP6W35K4YO` | Default intake — most new items get this |
| The Real Rarities | `FL4L42RRUE5UXMWFDLXOCNB5` | Truly rare/showcase pieces only |

**Assignment:** Pick type category → set as primary + `reporting_category`. Add The New Finds as secondary (or The Real Rarities if genuinely special). See `references/square-catalog.md` for full list including snack and TVM categories.

### Channel Classification By Phase

- **Phase 2 (Square):** Use Square category IDs (`categories` + `reporting_category`) from the tables above.
- **Phase 7 (GitHub Pages):** Use website filter slugs in `data-category` (not Square IDs).
- **Phase 8 (Whatnot):** Use Whatnot CSV category labels (not Square IDs, not website slugs).
- **Channel gating:** Not every item must be published to every channel. Only run phases requested by the user/workflow.

## Python Environment

All Python scripts use **uv** with a shared virtual environment at `~/.claude/skills/`.

**Command pattern (works from any directory):**
```bash
uv run --project ~/.claude/skills python ~/.claude/skills/<skill>/scripts/<script>.py <args>
```

See `~/.claude/skills/PYTHON.md` for setup details.

---

## Phase 0: Image Processing

**⚠️ CRITICAL:** Image processing runs on USER'S MAC via osascript, NOT in Claude's container. Binary files cannot transfer between environments.

### Step 0.1: Get next SKU from cache

Use square-cache for fast lookup:
```
square_cache_mcp:square_cache_search with sku_pattern: "RG-"
```
Find highest RG-XXXX and increment to get candidate SKU.

### Step 0.2: Verify SKU not taken

**Cache may be stale.** Before committing to the SKU, verify via cache with exact match:

```
square_cache_mcp:square_cache_search with sku_pattern: "RG-XXXX"
```

Check the results for an **exact SKU match** (not substring). The cache search returns partial matches, so verify the specific SKU string appears in results.

- If no exact match → SKU is safe, proceed
- If exact match found → increment and check again
- Repeat until finding an unused SKU

**⚠️ Do NOT use `searchItems` with `text_filter`** — it does broad text matching across all fields and returns the entire catalog instead of filtering by exact SKU.

### Step 0.3: Create item folder

```applescript
do shell script "mkdir -p /Users/scottybe/workspace/square/items/RG-XXXX"
```

### Step 0.4: Auto-discover product photo cluster (preferred)

Use `photos-library` clustering to find likely product shoots from the local Photos database:

```applescript
do shell script "source ~/.local/bin/env && uv run --project ~/.claude/skills python ~/.claude/skills/photos-library/scripts/find_product_clusters.py --days 14 --type product"
```

If product clusters are found:
- Prefer the most recent cluster by default
- Ask user to confirm cluster/date-time before copying
- Select the best image from that cluster (portrait-first, highest resolution)
- Copy by UUID to the item folder and set `SOURCE_IMAGE_PATH` (`EXT` should match source format, e.g., `heic` or `jpg`):

```applescript
do shell script "source ~/.local/bin/env && uv run --project ~/.claude/skills python ~/.claude/skills/image-processor/scripts/photos.py --copy 'PHOTO_UUID' --output '/Users/scottybe/workspace/square/items/RG-XXXX/source-original.EXT' 2>&1"
```

If no cluster is found (or Photos DB access fails), fall back to Step 0.5.

### Step 0.5: Locate user's image (manual fallback)

User uploads appear in `/mnt/user-data/uploads/` in Claude's container, but we need the file on user's Mac.

**⚠️ CHECK BOTH LOCATIONS:** User often places images on Desktop, not just Downloads.

```applescript
do shell script "ls -lt ~/Desktop/*.jpg ~/Desktop/*.jpeg ~/Desktop/*.png ~/Desktop/*.heic ~/Downloads/*.jpg ~/Downloads/*.jpeg ~/Downloads/*.png 2>/dev/null | head -10"
```

Or use `Filesystem:list_directory` on `/Users/scottybe/Desktop` to see all files.
Set `SOURCE_IMAGE_PATH` to the selected absolute path.

### Step 0.6: Check file size & prepare input

**⚠️ remove.bg has a 22MB limit.** Check file size first:

```applescript
do shell script "stat -f%z '/ABSOLUTE/SOURCE_IMAGE_PATH'"
```

**If > 20MB (20000000 bytes):** Compress before background removal:
```applescript
do shell script "sips -Z 3000 '/ABSOLUTE/SOURCE_IMAGE_PATH' --out '/Users/scottybe/workspace/square/items/RG-XXXX/hero_temp.png'"
```
Set `REMOVE_BG_INPUT=/Users/scottybe/workspace/square/items/RG-XXXX/hero_temp.png`

**If ≤ 20MB:** Use original directly unless it's HEIC.
- HEIC source: convert to PNG first and set `REMOVE_BG_INPUT` to `hero_temp.png`
```applescript
do shell script "sips -s format png '/ABSOLUTE/SOURCE_IMAGE_PATH' --out '/Users/scottybe/workspace/square/items/RG-XXXX/hero_temp.png'"
```
- Non-HEIC source: set `REMOVE_BG_INPUT=/ABSOLUTE/SOURCE_IMAGE_PATH`

### Step 0.7: Remove background

```applescript
do shell script "source ~/.local/bin/env && source ~/.env && uv run --project ~/.claude/skills python ~/.claude/skills/image-processor/scripts/process.py '/ABSOLUTE/REMOVE_BG_INPUT' --output '/Users/scottybe/workspace/square/items/RG-XXXX/hero.png' --quality premium --model removebg 2>&1"
```

**Prerequisites:** `~/.env` must have `REMOVEBG_API_KEY`. Note: Must `source ~/.env` to load API key.

**Monitor credits:** The script outputs remaining API credits. Alert user if credits ≤ 5.

**If bg removal fails:** Fall back to original image (copy/rename to hero.png), note in description that background removal is pending.

---

## Phase 1: Appraisal & Research

### Step 1.0: View image for appraisal

To see what we're working with, transfer a compressed preview to Claude's environment:

**1. Compress on user's Mac (if large):**
```applescript
do shell script "sips -Z 1500 '/path/to/original.png' --out '/tmp/preview.png'"
```

**2. Transfer to Claude's environment:**
```
Filesystem:copy_file_user_to_claude
  path: /tmp/preview.png
```
(Returns path like `/mnt/user-data/uploads/preview.png`)

**3. View with Claude's view tool:**
```
view
  path: /mnt/user-data/uploads/preview.png
```

Now you can see the item and do proper research.

---

### ⚠️ USER CHECKPOINTS (Do Not Assume)

**STOP and ask the user before proceeding.** These details fundamentally change pricing and description:

| Question | Why It Matters | Example Impact |
|----------|----------------|----------------|
| **Quantity** — How many pieces? | Set of 9 vs single goblet = completely different listing | 9pc set @ $89 vs single @ $15 |
| **Selling strategy** — Set or individual? | Changes title, description, pricing, inventory count | "Set of 9" vs "1 of 9 available" |
| **Condition specifics** — Chips, cracks, wear, repairs? | Affects price and required disclosures | "Excellent" vs "Good - minor chip" |
| **Original elements** — Stickers, labels, boxes, tags? | Adds provenance value, affects description | "with original Made in Germany sticker" |
| **Lot assignment** — Track acquisition cost? | Optional but needed for margin analysis (via `rg-lot-tracker`) | L2-Peter's Estate @ $5 cost |

**Do the research first**, then ask these questions with context. Example flow:

```
Claude: "These are Goebel Hummel figural wine goblets from West Germany, 
        1960s-70s. Sets of 6 typically sell $50-150. 
        
        A few questions:
        1. How many goblets in your set?
        2. Selling as set or individually?
        3. Any original 'Made in Western Germany' stickers?
        4. Any chips, cracks, or gold wear?"

User:  "we have 9, as a set, no stickers, no chips or cracks"

Claude: [now has accurate info for pricing and description]
```

**Never assume** quantity=1, condition=excellent, or selling strategy. Ask.

---

### Step 1.1: Assign lot & record acquisition cost

→ **Delegate to `rg-lot-tracker` skill** (Phase 0 + Phase 1)

If the user provides lot info (source, cost, date), pass it to `rg-lot-tracker`:
- Phase 0 creates or selects the lot
- Phase 1 allocates cost to this item
- Returns: `lot_id` and `allocated_cost`

Store the `allocated_cost` for pricing validation before Phase 2.

**Even if user says "unknown"** — prompt once more: "Do you want to assign this to a lot for tracking, or skip for now?"
If they skip, continue without cost data and skip margin validation in Step 1.5.

### Step 1.2: Route to specialized appraiser if needed

**⚠️ MANDATORY ROUTING — Do not skip:**

| Item Type | Trigger | Skill to Use |
|-----------|---------|--------------|
| Books dated 1970 or earlier | Publication year ≤ 1970 | `book-appraiser` — **MUST USE** |
| Carnival glass | Iridescent pressed glass | `carnival-glass-appraiser` |
| Maker's marks | Stamps, hallmarks, signatures | `maker-mark-identifier` |
| General vintage | Everything else | Continue here |

**For books:** If the book is from 1970 or earlier, you MUST read and follow the `book-appraiser` skill. This includes children's books, textbooks, and any printed material. The skill provides LOC cross-reference, edition identification, and specialized pricing.

### Step 1.3: Research

1. Identify maker/manufacturer
2. Date the piece (era, production dates)
3. Assess condition
4. Research comps (eBay sold, auction records)
5. Determine price point

**Pricing tiers:** See `rg-lot-tracker` for full margin targets by category.
Quick reference: quick flip 2.5-3x, mid-range 3-4x, showcase research-based.

### Step 1.4: Determine shipping eligibility

**Ships easily:**
- Books, paper goods, small collectibles
- Sturdy items that fit in standard boxes
- Most things you'd drop at the post office

**Pickup only:**
- Furniture (size/weight impractical)
- Large or awkward shapes
- Extremely fragile items
- Heavy items where shipping cost ≈ item value

**Flat rate reference:** Small $10.20 | Medium $17.10 | Large $21.90

### Step 1.5: Validate pricing against cost basis

If `allocated_cost` is available from Step 1.1:

→ **Delegate to `rg-lot-tracker` skill** (Phase 2)

Pass: item SKU, proposed list price, allocated cost, and item category.
Receive: margin analysis with go/no-go recommendation.

If margin is below target, present the analysis and ask whether to adjust price
or proceed anyway. Do not block; user decides.

If lot tracking was skipped and no `allocated_cost` is available, skip this step.

**Output from Phase 1:**
- Item title
- Description (HTML paragraphs for `description_html` — see Phase 2 formatting rules)
- Price in cents
- Condition grade
- SEO title and description
- **Shippable: YES or NO**

---

## Phase 2: Square Catalog Creation

**Method Selection:**
1. **Primary:** Attempt `catalog.batchInsertObjects` first.
2. **Fallback:** If rejected (e.g., due to schema/body issues), switch to `catalog.upsertCatalogObject`.

**⚠️ CRITICAL:**
- `idempotency_key` stays at the **top level** for both payload styles.
- Do NOT move `idempotency_key` inside `batches`.
- Variation MUST have `present_at_all_locations: false` at the variation level.

### Description Formatting Rules (MANDATORY)

**⚠️ Square's `description` field is DEPRECATED.** Always use `description_html` instead.

**Supported HTML tags:** `<p>`, `<br>`, `<b>`, `<strong>`, `<i>`, `<em>`, `<u>`, `<ul>`, `<ol>`, `<li>`, `<h1>`–`<h6>`, `<a>`, `<div>`, `<code>`.
**NOT supported:** Inline styles, `<style>` tags, CSS classes. No `style="..."` attributes.

| Rule | Correct | WRONG |
|------|---------|-------|
| Paragraph spacing | `</p><p>&nbsp;</p><p>` (spacer paragraph) | `<p>` alone (no visible gap on Square) |
| Paragraph breaks | `<p>Paragraph one.</p><p>&nbsp;</p><p>Paragraph two.</p>` | `<br><br>` in `description` field |
| Bold labels | `<b>Condition:</b> Good` | Plain text (no visual hierarchy) |
| Ampersand | `&amp;` (only entity needed) | `&amp;amp;` (double-escaped) |
| Copyright © | Unicode `©` directly | `&copy;` entity |
| Em dash — | Unicode `—` directly | `&mdash;` entity |
| En dash – | Unicode `–` directly | `&ndash;` entity |

**Why `<p>&nbsp;</p>` spacers:** Square Online CSS strips `<p>` margins to zero, so back-to-back `<p>` tags render as line breaks with no visual gap. A `<p>&nbsp;</p>` spacer paragraph forces a visible blank line between sections.

**Template pattern:**
```html
<p>Opening paragraph — what this item is.</p>
<p>&nbsp;</p>
<p>History/provenance paragraph.</p>
<p>&nbsp;</p>
<p>Additional context paragraph.</p>
<p>&nbsp;</p>
<p>Production/technical details. Copyright © Year Holder.</p>
<p>&nbsp;</p>
<p><b>Condition:</b> Grade. Specific notes. Shipping info.</p>
```

**Why not `description`:** When you put `<br>` tags or HTML entities into the plain `description` field, Square wraps everything in `<p>` tags and escapes the HTML, so `<br>` becomes visible as literal text on the website.

**Correct approach:** Use `description_html` with `<p>` tags + `<p>&nbsp;</p>` spacers + Unicode characters. Square auto-generates `description` and `description_plaintext` from `description_html`.

**Payload A: `batchInsertObjects`**
```json
{
  "idempotency_key": "rg-XXXX-create-TIMESTAMP",
  "batches": [{
    "objects": [{
      "type": "ITEM",
      "id": "#RG-XXXX",
      "present_at_all_locations": false,
      "present_at_location_ids": ["B87BAEZ0NWV34"],
      "item_data": {
        "name": "Item Title",
        "description_html": "<p>First paragraph.</p><p>&nbsp;</p><p>Second paragraph.</p><p>&nbsp;</p><p><b>Condition:</b> Good. Notes here.</p>",
        "categories": [
          {"id": "TYPE_CATEGORY_ID"},
          {"id": "TIER_CATEGORY_ID"}
        ],
        "reporting_category": {"id": "TYPE_CATEGORY_ID"},
        "tax_ids": ["LPKEJF7H27NOPK7EE6A5CA7V"],
        "is_taxable": true,
        "ecom_visibility": "VISIBLE",
        "ecom_seo_data": {
          "page_title": "[Era] [Item] - [Feature] | Richmond General",
          "page_description": "Keyword-rich, ends with Richmond, IL",
          "permalink": "lowercase-hyphenated-slug"
        },
        "variations": [{
          "type": "ITEM_VARIATION",
          "id": "#RG-XXXX-var",
          "present_at_all_locations": false,
          "present_at_location_ids": ["B87BAEZ0NWV34"],
          "item_variation_data": {
            "item_id": "#RG-XXXX",
            "name": "Regular",
            "sku": "RG-XXXX",
            "pricing_type": "FIXED_PRICING",
            "price_money": {"amount": 1999, "currency": "USD"},
            "track_inventory": true,
            "sellable": true,
            "stockable": true
          }
        }]
      }
    }]
  }]
}
```

**Payload B: `upsertCatalogObject` (Fallback)**
```json
{
  "idempotency_key": "rg-XXXX-create-TIMESTAMP",
  "object": {
    "type": "ITEM",
    "id": "#RG-XXXX",
    "present_at_all_locations": false,
    "present_at_location_ids": ["B87BAEZ0NWV34"],
    "item_data": {
      "name": "Item Title",
      "description_html": "<p>First paragraph.</p><p>&nbsp;</p><p>Second paragraph.</p><p>&nbsp;</p><p><b>Condition:</b> Grade. Notes.</p>",
      "categories": [
        {"id": "TYPE_CATEGORY_ID"},
        {"id": "TIER_CATEGORY_ID"}
      ],
      "reporting_category": {"id": "TYPE_CATEGORY_ID"},
      "tax_ids": ["LPKEJF7H27NOPK7EE6A5CA7V"],
      "is_taxable": true,
      "ecom_visibility": "VISIBLE",
      "ecom_seo_data": {
        "page_title": "[Era] [Item] - [Feature] | Richmond General",
        "page_description": "Keyword-rich, ends with Richmond, IL",
        "permalink": "lowercase-hyphenated-slug"
      },
      "variations": [{
        "type": "ITEM_VARIATION",
        "id": "#RG-XXXX-var",
        "present_at_all_locations": false,
        "present_at_location_ids": ["B87BAEZ0NWV34"],
        "item_variation_data": {
          "item_id": "#RG-XXXX",
          "name": "Regular",
          "sku": "RG-XXXX",
          "pricing_type": "FIXED_PRICING",
          "price_money": {"amount": 1999, "currency": "USD"},
          "track_inventory": true,
          "sellable": true,
          "stockable": true
        }
      }]
    }
  }
}
```

**Capture IDs from response (in order of reliability):**
1. Prefer `id_mappings` lookup by temp IDs:
   - `#RG-XXXX` -> CATALOG_ITEM_ID
   - `#RG-XXXX-var` -> VARIATION_ID
2. If no mappings:
   - `batchInsertObjects`: `objects[0].id` and `objects[0].item_data.variations[0].id`
   - `upsertCatalogObject`: `catalog_object.id` and `catalog_object.item_data.variations[0].id`
3. If variation ID is still missing, call `retrieveCatalogObject` with related objects and resolve by SKU.

---

## Phase 3: Set Inventory

**Use Square MCP:**
```
mcp_square_api:make_api_request
  service: inventory
  method: batchChange   ← EXACT NAME (not batchChangeInventory)
```

**⚠️ CRITICAL:** Do NOT include `catalog_object_type` — Square rejects it as a write-only field.

```json
{
  "idempotency_key": "rg-XXXX-inv-TIMESTAMP",
  "changes": [{
    "type": "PHYSICAL_COUNT",
    "physical_count": {
      "catalog_object_id": "VARIATION_ID_FROM_PHASE_2",
      "location_id": "B87BAEZ0NWV34",
      "quantity": "1",
      "state": "IN_STOCK",
      "occurred_at": "CURRENT_ISO_TIMESTAMP"
    }
  }]
}
```

**Note:** `quantity` is a STRING, not integer. `occurred_at` must be a **current** ISO 8601 timestamp (within 24 hours). Generate dynamically — do NOT hardcode a date.

---

## Phase 4: Image Upload

**Use square-image-upload skill script on user's Mac:**

```applescript
do shell script "source ~/.local/bin/env && source ~/.env && uv run --project ~/.claude/skills python ~/.claude/skills/square-image-upload/scripts/upload_image.py --image '/Users/scottybe/workspace/square/items/RG-XXXX/hero.png' --item-id 'CATALOG_ITEM_ID' --name 'RG-XXXX Hero' --caption 'Front view' --primary 2>&1"
```

**Capture:** Image ID from response.

**⚠️ WebP not supported** - convert if needed:
```bash
sips -s format png image.webp --out hero.png
```

### Step 4.1: Sync and verify square-cache

After catalog create (Phase 2), inventory write (Phase 3), and image upload (Phase 4), reconcile cache before moving on:

**Primary (MCP):**
```
square_cache_mcp:square_cache_sync
```

**Fallback (local script):**
```applescript
do shell script "source ~/.local/bin/env && source ~/.env && uv run --project ~/.claude/skills python ~/.claude/skills/square-cache/scripts/cache_wrapper.py sync --json 2>&1"
```

Then verify:

1. Exact SKU exists in cache
```
square_cache_mcp:square_cache_search with sku_pattern: "RG-XXXX"
```
Confirm exact `RG-XXXX` match (not substring only).

2. Cached item includes uploaded image
```
square_cache_mcp:square_cache_get_item with item_id: "CATALOG_ITEM_ID"
```
Confirm `item_data.image_ids` contains the image ID from Phase 4. If not, run sync once more and re-check.

---

## Phase 5: Payment Link

**Shipping decision from Phase 1 determines `ask_for_shipping_address`:**

| Shippable? | Setting | Customer Experience |
|------------|---------|---------------------|
| YES | `"ask_for_shipping_address": true` | Customer enters address → you ship |
| NO | `"ask_for_shipping_address": false` | No address collected → pickup only |

**Use Square MCP:**
```
mcp_square_api:make_api_request
  service: checkout
  method: createPaymentLink
```

**For shippable items:**
```json
{
  "idempotency_key": "rg-XXXX-pay-TIMESTAMP",
  "quick_pay": {
    "name": "Item Title",
    "price_money": {"amount": 1999, "currency": "USD"},
    "location_id": "B87BAEZ0NWV34"
  },
  "checkout_options": {
    "ask_for_shipping_address": true
  }
}
```

**For pickup-only items:**
```json
{
  "idempotency_key": "rg-XXXX-pay-TIMESTAMP",
  "quick_pay": {
    "name": "Item Title",
    "price_money": {"amount": 1999, "currency": "USD"},
    "location_id": "B87BAEZ0NWV34"
  },
  "checkout_options": {
    "ask_for_shipping_address": false
  }
}
```

**Capture:** `payment_link.url` → `https://square.link/u/XXXXXXXX`

---

## Phase 6: Generate Label

**Append row to batch CSV:**

**Batch file:** `/Users/scottybe/workspace/square/items/rg-labels-batch.csv`

```csv
Product Name,Attributes,Price,Condition,Condition Notes,SKU,QR Code URL
"Item Title","Era • Type • Feature",55.00,Good,"Wear notes",RG-XXXX,https://richmondgeneral.github.io/items/RG-XXXX/
```

```applescript
do shell script "echo '\"Item Title\",\"Era • Type • Feature\",55.00,Good,\"Wear notes\",RG-XXXX,https://richmondgeneral.github.io/items/RG-XXXX/' >> ~/workspace/square/items/rg-labels-batch.csv"
```

**Every item gets a QR code** on its label, linking to the info card. This is the customer experience—scan, read the story, buy.

See `references/label-format.md` for Print Master settings.

---

## Phase 7: Info Card & Publishing

Run this phase only if the item should be published to GitHub Pages.

**Site:** https://richmondgeneral.github.io/items/
**Repo:** /Users/scottybe/workspace/square/items/

### Step 7.1: Write index.html (FLIP CARD TEMPLATE REQUIRED)

**⚠️ MANDATORY:** Use the **flip card template** from `references/info-card-template.html`. Do NOT use detail-page layouts.

Use `Filesystem:write_file` to write the populated template to:
`/Users/scottybe/workspace/square/items/RG-XXXX/index.html`

(Item folder already exists from Phase 0.3)

**Template requirements:**
- MUST use `.flip-card`, `.card-front`, `.card-back` structure
- MUST use `aspect-ratio: 5 / 7` for print optimization
- MUST use CSS variables: `--rg-gold`, `--rg-cream`, `--rg-charcoal` (not shortened versions)
- MUST include flip animation, keyboard accessibility, and ARIA attributes
- MUST include mobile responsive breakpoints and print styles

**Placeholders to replace:**
| Placeholder | Replace With |
|-------------|-------------|
| `{{SKU}}` | RG-XXXX |
| `{{ITEM_TITLE}}` | Item name |
| `{{ERA_LINE}}` | Era • Type • Feature |
| `{{PRICE}}` | XX.XX (no $ sign) |
| `{{STORY_TEXT}}` | 2-3 paragraph story |
| `{{DETAIL_N_LABEL}}` | Era, Maker, Origin, etc. |
| `{{DETAIL_N_VALUE}}` | Corresponding value |
| `{{CONDITION}}` | Good, Excellent, etc. |
| `{{PAYMENT_LINK}}` | https://square.link/u/XXXXXXXX |
| `{{SEO_DESCRIPTION}}` | Keyword-rich meta description |
| `{{OG_DESCRIPTION}}` | Shorter OG description |

**DO NOT:**
- Use traditional multi-section layouts (header → hero → story → details → footer)
- Use simplified CSS variables (`--gold` instead of `--rg-gold`)
- Omit the flip animation or 5×7 aspect ratio

### Step 7.2: Generate QR code (payment link)

```applescript
do shell script "source ~/.local/bin/env && cd /Users/scottybe/workspace/square/items/RG-XXXX && uv run --project ~/.claude/skills python -c \"import qrcode; qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2); qr.add_data('https://square.link/u/XXXXXXXX'); qr.make(fit=True); img = qr.make_image(fill_color='#2C2C2C', back_color='white'); img.save('qr-code.png'); print('QR code saved')\""
```

### Step 7.3: Add to gallery index

**⚠️ DON'T FORGET:** The item card won't appear on the main gallery page unless added to the index.

**⚠️ USE OSASCRIPT:** Filesystem tools may return wrong-case paths. Use sed via osascript for reliability:

```applescript
do shell script "sed -i '' 's|<!-- Coming Soon Placeholder -->|<!-- RG-XXXX: Item Title -->\\
            <a href=\"./RG-XXXX/\" class=\"item-card\" data-category=\"CATEGORY\">\\
                <div class=\"item-image\">\\
                    <span class=\"item-badge\">New</span>\\
                    <span class=\"item-sku\">RG-XXXX</span>\\
                    <img src=\"./RG-XXXX/hero.png\" alt=\"Item Title\" style=\"max-width: 100%; max-height: 200px; object-fit: contain; border-radius: 4px;\">\\
                </div>\\
                <div class=\"item-info\">\\
                    <p class=\"item-category\">Category</p>\\
                    <h3 class=\"item-title\">Item Title</h3>\\
                    <p class=\"item-era\">Era • Origin • Feature</p>\\
                    <div class=\"item-footer\">\\
                        <span class=\"item-price\">$XX.XX</span>\\
                        <span class=\"view-story\">\\
                            View Story\\
                            <svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\">\\
                                <path d=\"M5 12h14M12 5l7 7-7 7\"/>\\
                            </svg>\\
                        </span>\\
                    </div>\\
                </div>\\
            </a>\\
            \\
            <!-- Coming Soon Placeholder -->|' /Users/scottybe/workspace/square/items/index.html"
```

**Categories for filter (`data-category` on index card):**
- `books` → Square type `Books & Paper`
- `furniture` → Square type `Furniture`
- `pottery` → Square type `Pottery & Ceramics`
- `collectibles` → Square types `Collectibles`, `Art & Craft Kits`, `Wellness & Apothecary`, `The Apothecary Cabinet`, `Home & Gifts`, `Analog`

### Step 7.4: Update item count

```applescript
do shell script "sed -i '' 's|<div class=\"stat-number\" id=\"item-count\">[0-9]*</div>|<div class=\"stat-number\" id=\"item-count\">NEW_COUNT</div>|' /Users/scottybe/workspace/square/items/index.html"
```

### Step 7.5: Cleanup temp files

Remove any intermediate files created during processing:

```applescript
do shell script "rm -f /Users/scottybe/workspace/square/items/RG-XXXX/hero_temp.png 2>/dev/null; echo 'Cleanup complete'"
```

### Step 7.6: Git commit and push

```applescript
do shell script "cd /Users/scottybe/workspace/square/items && git add RG-XXXX/ index.html && git commit -m 'Add RG-XXXX: Item Title' && git push origin main 2>&1"
```

**Customer flow:** QR on label → Info card → Read story → Buy Now → Square checkout

---

## Phase 8: Whatnot Item Library Listing

Run this phase only if the item should be listed on Whatnot.

**Method:** CSV bulk import via Chrome automation (no API/MCP connector exists for Whatnot)
**Image hosting:** GitHub Pages — `https://richmondgeneral.github.io/items/RG-XXXX/hero.png`
**Account:** richmondgeneral on whatnot.com

### Step 8.1: Append row to Whatnot batch CSV

**Batch file:** `/Users/scottybe/workspace/square/items/rg-inventory/whatnot-import.csv`

**CSV columns (exact header names — must match Whatnot template):**

```
Category,Sub Category,Title,Description,Quantity,Type,Price,Shipping Profile,Offerable,Hazmat,Condition,Cost Per Item,SKU,Image URL 1,Image URL 2,Image URL 3,Image URL 4,Image URL 5,Image URL 6,Image URL 7,Image URL 8
```

**Field mapping from earlier phases:**

| CSV Column | Source | Example |
|------------|--------|---------|
| Category | Whatnot **parent** category (see hierarchy below) | `Movies` |
| Sub Category | Whatnot sub-category (required for some categories) | `DVDs` |
| Title | Item title from Phase 1 | `Dick Tracy: The Art of Chester Gould (1978) Exhibition Catalogue` |
| Description | Plain text description from Phase 1 (NOT HTML) | Full provenance + condition |
| Quantity | Always `1` for unique items | `1` |
| Type | Always `Buy it Now` for fixed-price | `Buy it Now` |
| Price | **Positive integer only** (no decimals!) | `7` |
| Shipping Profile | Weight bracket (must match allowed values — see heuristic table below) | `4-7 oz` |
| Offerable | `TRUE` to accept offers | `TRUE` |
| Hazmat | Always `Not Hazmat` | `Not Hazmat` |
| Condition | Item condition | `Good` |
| Cost Per Item | Allocated cost from lot tracker (integer, seller-only) | `1` |
| SKU | Same SKU as Square | `RG-0015` |
| Image URL 1 | GitHub Pages hero image | `https://richmondgeneral.github.io/items/RG-0015/hero.png` |
| Image URL 2-8 | Additional images if available | _(leave empty)_ |

**⚠️ CRITICAL GOTCHAS:**
1. **Price must be a positive integer.** Whatnot rejects decimals like `6.50`. Round up: `$6.50 → $7`.
2. **Category hierarchy matters.** DVDs is NOT a top-level category — it's a sub-category under `Movies`. Use `Category=Movies, Sub Category=DVDs`.
3. **Cost Per Item must also be integer** if provided.
4. Values for Category, Sub Category, Condition, Type, and Shipping Profile must exactly match Whatnot's allowed values.

**Append command:**
```applescript
do shell script "echo '\"Movies\",\"DVDs\",\"Item Title\",\"Plain text description\",1,Buy it Now,7,4-7 oz,TRUE,Not Hazmat,Good,1,RG-XXXX,https://richmondgeneral.github.io/items/RG-XXXX/hero.png,,,,,,,,' >> ~/workspace/square/items/rg-inventory/whatnot-import.csv"
```

### Step 8.2: Upload CSV to Whatnot (Chrome Automation)

**⚠️ REQUIRES GIT PUSH FIRST** — The hero.png must be live on GitHub Pages before Whatnot can fetch it. Ensure Step 7.6 (git push) has completed.

**Automated upload via Claude in Chrome:**

1. Navigate to `https://www.whatnot.com/dashboard/inventory`

2. Open the CSV import modal — click the cloud/upload icon next to "Create Product" (approximate coordinate: `1122, 110`):
   ```
   computer tool: left_click at [1122, 110]
   ```

3. Inject CSV via JavaScript DataTransfer API (bypasses native file picker):
   ```javascript
   const csvContent = `Category,Sub Category,Title,...`; // full CSV content with header + data rows
   const blob = new Blob([csvContent], { type: 'text/csv' });
   const file = new File([blob], 'whatnot-import.csv', { type: 'text/csv' });
   const fileInput = document.querySelector('input[type="file"]');
   const dataTransfer = new DataTransfer();
   dataTransfer.items.add(file);
   fileInput.files = dataTransfer.files;
   fileInput.dispatchEvent(new Event('change', { bubbles: true }));
   fileInput.dispatchEvent(new Event('input', { bubbles: true }));
   ```

4. After injection: modal shows "filename.csv — Ready to import" with a yellow **Import** button.

5. Click **Import** → server-side validation runs.

6. On success: "Your products have successfully imported" with "View Drafts" link. Products import as **Drafts**.

7. Verify drafts at `https://www.whatnot.com/dashboard/inventory?tab=drafts`

**If validation fails**, common errors and fixes:

| Error | Cause | Fix |
|-------|-------|-----|
| "Subcategory not provided" | Category requires a sub-category | Check hierarchy table below |
| "Subcategory X is not part of Category Y" | Wrong parent/child pairing | Look up correct hierarchy in Values tab |
| "Price must be a positive integer" | Decimal price like `6.50` | Round up to whole dollar `7` |

**Manual fallback:** If Chrome automation isn't available, download the CSV file and upload manually through the Whatnot dashboard.

### Step 8.3: Post-Import Metadata Editing (Chrome Automation)

**Purpose:** After CSV import, certain category-specific fields are only available on the Whatnot edit page — they cannot be set via CSV. This step fills those fields using Claude in Chrome.

**⚠️ IMPORTANT DISTINCTION — Two different "Type" fields:**
- **CSV column "Type"** = Listing type (`Buy it Now`, `Auction`, `Giveaway`)
- **Edit page "Type" dropdown** = Content type (e.g., `Movie`, `Mini Series`, `TV Series` for DVDs)

These are completely separate fields. The CSV "Type" is set during import; the edit page "Type" must be set manually afterward.

**Edit page URL pattern:**
```
https://www.whatnot.com/dashboard/inventory/TGlzdGluZ05vZGU6XXXXXXXXXX==
```
(Base64-encoded Whatnot node IDs — find these by clicking items from the inventory list)

**Workflow per item:**

1. Navigate to `https://www.whatnot.com/dashboard/inventory` (or use `?tab=drafts` for newly imported items)
2. Click the item to open its edit page
3. Scroll down to find the category-specific metadata fields
4. For each combobox field:
   - Use `find` tool to locate the field by label (e.g., `"Genre combobox"`, `"Type combobox"`)
   - Use `form_input` with the ref to type a filter string (e.g., `"Horror"`, `"Movie"`)
   - Click the matching dropdown option that appears
5. Verify Shipping Profile is correct (CSV import may have used a default value)
6. Click **Save** button
7. Navigate back to inventory list and repeat for next item

**⚠️ React combobox quirks:**
- Whatnot uses React comboboxes — typing into them filters the dropdown options
- If dropdown shows "No options available," the typed value is NOT a valid option
- Don't try to force invalid values (e.g., typing "DVD" into the content Type field won't work)
- Always click an option from the dropdown to ensure React state updates properly

#### Category-Specific Metadata Fields

**Movies > DVDs:**

| Field | Required | Valid Values | Notes |
|-------|----------|-------------|-------|
| Movie/TV Show Title | Yes | Free text | Use the actual film title, not the listing title |
| Genre | Yes | Action, Comedy, Drama, Horror, Sci-Fi, Thriller, etc. | Combobox with typeahead filtering |
| Type (content) | Yes | `Movie`, `Mini Series`, `TV Series` | NOT the CSV "Type" column |
| Edition | No | `Standard Edition`, `Collector's Edition`, `Unrated Edition`, `Special Edition`, `Director's Cut`, etc. | Combobox with typeahead |

> **TODO:** Document metadata fields for other categories (Vinyl Records, Vintage Toys, etc.) as they are onboarded.

#### Shipping Profile Weight Heuristic

Use this table to select the correct Shipping Profile value:

| Item Type | Weight Estimate | Shipping Profile |
|-----------|----------------|-----------------|
| Single DVD (standard case) | ~4-5 oz | `4-7 oz` |
| DVD multi-pack (2-4 discs) | ~5-6 oz | `4-7 oz` |
| DVD box set (5-8 discs) | ~6-7 oz | `4-7 oz` |
| DVD large box set (9+ discs) | ~8-10 oz | `8-11 oz` |
| Single Blu-ray | ~4-5 oz | `4-7 oz` |
| VHS tape (single) | ~8-10 oz | `8-11 oz` |
| Paperback book | ~4-7 oz | `4-7 oz` |
| Hardcover book (small) | ~8-12 oz | `8-11 oz` |
| Hardcover book (large/coffee table) | ~1-2 lbs | `1-2 lbs` |
| Vinyl record (single LP) | ~8-10 oz | `8-11 oz` |
| Small collectible / figurine | ~4-6 oz | `4-7 oz` |

> When in doubt, weigh the item. Accurate shipping prevents losses on lightweight items and buyer complaints on heavy ones.

### Whatnot Category Hierarchy Reference

**⚠️ CRITICAL:** Some items that seem like categories are actually sub-categories. Always check the hierarchy.

**Common RG inventory mappings:**

| Item Type | Category (parent) | Sub Category | Notes |
|-----------|-------------------|--------------|-------|
| DVDs | `Movies` | `DVDs` | NOT `DVDs` as category! |
| VHS tapes | `Movies` | `VHS` | |
| Blu-ray | `Movies` | `Blu-ray` | |
| Movie memorabilia | `Movies` | `Movie Memorabilia` | |
| Rare/vintage books | `Rare & Vintage Books` | _(empty)_ | Top-level, no sub required |
| Vintage toys | `Vintage Toys` | _(varies)_ | Check Values tab |
| Vinyl records | `Vinyl Records` | _(varies)_ | |
| Art | `Art` | _(varies)_ | |

**Full category/sub-category list:** See Values tab (columns E & F) of the [Whatnot CSV template](https://docs.google.com/spreadsheets/d/1UNxbyQoXjpjuqYcCE_Ie94OTCEB7lXR7Yz84aynILW4/edit#gid=0)

### Whatnot Allowed Values Reference

**Condition:**
`Brand New`, `Like New`, `Very Good`, `Good`, `Fair`, `Poor`

**Type:**
`Auction`, `Buy it Now`, `Giveaway`

**Shipping Profile (must match Whatnot dropdown exactly):**
`1-3 oz`, `4-7 oz`, `8-11 oz`, `12-15 oz`, `1 lb`, `1-2 lbs`

> **⚠️ Updated Feb 2026:** Previous values (`0-1 oz`, `1-4 oz`, `5-8 oz`, etc.) were incorrect. The values above are the actual Whatnot dropdown options.

**Hazmat:**
`Not Hazmat`

### Whatnot Price Conversion Rule

Square prices use cents (e.g., `650` = $6.50), but Whatnot requires **whole dollar integers**. When converting:

| Square Price (cents) | Whatnot Price | Rule |
|---------------------|---------------|------|
| 650 | 7 | Round up |
| 1050 | 11 | Round up |
| 4000 | 40 | Already whole |
| 1999 | 20 | Round up |

**Formula:** `ceil(square_price_cents / 100)`

---

## Phase 9: Photos Library Archive (Cleanup)

**Purpose:** Organize source photos into per-item albums so the Photos library stays clean.

**Structure in Photos.app:**
```
Richmond General Archive/     (folder)
  RG-0001/                    (album — originals for item 1)
  RG-0002/                    (album — originals for item 2)
  ...
```

**⚠️ PREREQUISITE:** Git push (Step 7.6) must have completed successfully — the item folder in git is the archive of record. Photos.app albums are for convenient browsing, not backup.

### Step 9.1: Archive photos to per-item album

**Mode A — Direct UUID (when Step 0.4 cluster discovery was used):**

If you have the UUIDs from the cluster discovery step, pass them directly:

```applescript
do shell script "source ~/.local/bin/env && uv run --project ~/.claude/skills python ~/.claude/skills/photos-library/scripts/archive_photos.py --item-id RG-XXXX --uuids UUID1 UUID2 UUID3 --json 2>&1"
```

**Mode B — Reverse filename lookup (when Step 0.5 manual fallback was used):**

When photos came from Desktop/Downloads (no UUIDs captured), reverse-lookup the original filenames against the Photos database:

```applescript
do shell script "source ~/.local/bin/env && uv run --project ~/.claude/skills python ~/.claude/skills/photos-library/scripts/archive_photos.py --item-id RG-XXXX --reverse --include 'IMG_*' --json 2>&1"
```

This searches the Photos SQLite DB for assets matching filenames in the item directory and archives any matches. Use comma-separated globs for stricter matching when needed, for example: `--include 'IMG_*.jpg,IMG_*.jpeg,IMG_*.HEIC'`.

**Dry run (preview without touching Photos):**
```applescript
do shell script "source ~/.local/bin/env && uv run --project ~/.claude/skills python ~/.claude/skills/photos-library/scripts/archive_photos.py --item-id RG-XXXX --reverse --include 'IMG_*' --dry-run --json 2>&1"
```

### Step 9.2: Verify archive

Confirm the output JSON shows `archived > 0`. If `skipped > 0`, some UUIDs weren't found (photos may have already been deleted from the library).

**⚠️ This step does NOT delete photos.** It only adds them to an album. The user can periodically review and bulk-delete from the "Richmond General Archive" folder in Photos when satisfied that git has everything.

---

## Quick Tasks (Single Phase)

| Request | Action |
|---------|--------|
| "make a label for..." | Phase 6 only |
| "price this" / "what's this worth" | Phase 1 only |
| "upload this image to Square" | Phase 4 only |
| "create a payment link" | Phase 5 only |
| "what's the SKU for..." | Cache lookup only |
| "add to whatnot" / "list on whatnot" | Phase 8 only |
| "archive photos" / "clean up photos" | Phase 9 only |

---

## Workflow Summary Output

After completing full workflow:

```
✅ NEW ITEM ADDED: RG-XXXX

📦 Square Catalog
   Item ID: {CATALOG_ITEM_ID}
   Variation: {VARIATION_ID}
   Price: ${PRICE}
   Inventory: 1 in stock

🖼️ Image
   Hero: /Users/scottybe/workspace/square/items/RG-XXXX/hero.png
   Square Image ID: {IMAGE_ID}
   Cache Sync: verified (SKU + image_ids)

🔍 SEO
   Title: {PAGE_TITLE}
   Permalink: {PERMALINK}

🚚 Fulfillment: {SHIPPING / PICKUP ONLY}

💳 Payment Link: {PAYMENT_LINK_URL}

🏷️ Label: Added to rg-labels-batch.csv

📄 Info Card: https://richmondgeneral.github.io/items/RG-XXXX/

📸 Photos Archive: Richmond General Archive / RG-XXXX ({N} photos archived)

Next: Print label, place item on floor
```

---

## Troubleshooting

**Image too large for remove.bg:**
- remove.bg limit is 22MB
- Compress first: `sips -Z 3000 image.png --out hero_temp.png`

**Image upload fails:**
- Ensure catalog item created FIRST (need ITEM_ID for image upload)
- Check token: `source ~/.env && echo $SQUARE_ACCESS_TOKEN`
- Verify image is PNG or JPEG (WebP not supported)

**Background removal fails:**
- Check API keys on user's Mac: `source ~/.env && echo $REMOVEBG_API_KEY`
- Ensure image is accessible on user's Mac (not just in Claude's container)
- Check remaining credits in script output

**Photos cluster discovery fails:**
- Check Photos DB path exists: `~/Pictures/Photos Library.photoslibrary/database/Photos.sqlite`
- Ensure terminal/Codex has Full Disk Access on macOS
- If you see `sqlite3.OperationalError: unable to open database file`, this is usually a macOS privacy permission issue
- Fall back to Step 0.5 manual image selection

**Binary file transfer fails:**
- Binary files (PNG, JPEG) cannot transfer between Claude's container and user's Mac
- Solution: Generate binaries via osascript on user's Mac directly

**Square 401 Unauthorized:**
- Token expired: Check `$SQUARE_ACCESS_TOKEN`

**Inventory API rejects request:**
- Do NOT include `catalog_object_type` in the request
- Ensure `quantity` is a string, not integer

**Image upload 413 Too Large:**
- Compress: `sips -Z 2000 image.png`

**Item shows "sold out":**
- Missing inventory count (Phase 3)

**Path case mismatch:**
- Filesystem tools may return `/Workspace/` instead of `/workspace/`
- Use osascript + sed for file edits on user's Mac

---

## Related Skills

| Skill | Use For |
|-------|---------|
| `rg-item-update` | Quick edits to existing items |
| `square-image-upload` | Image upload via API |
| `book-appraiser` | Antiquarian books, LOC cross-reference |
| `carnival-glass-appraiser` | Pressed iridescent glass 1908-1930s |
| `maker-mark-identifier` | Pottery, silver, furniture marks |
| `product-labeler` | Label generation, Square descriptions |
| `square-cache` | Fast catalog lookups |
| `photos-library` | Auto-discover and cluster local Photos shoots |
| `rg-lot-tracker` | Lot tracking, cost allocation, margin validation |

## References

- `references/square-catalog.md` - API details, category IDs
- `references/label-format.md` - Print Master settings, style guide
- `references/info-card-template.html` - HTML template for item pages
