---
name: rg-full-auto
description: >
  End-to-end 10-phase workflow for onboarding NEW items to Richmond General from acquisition through sale.
  Covers appraisal, lot/acquisition cost tracking, photography, Square catalog creation, image upload,
  payment links, labels, info card publishing, Whatnot CSV listing, and Photos library cleanup.
  Use when processing a new acquisition from scratch, doing a complete item redo, or user says
  "list this item" or "sell this". Triggers on "new item", "full workflow", "onboard",
  "process acquisition", "add to inventory", "process this photo", "list item", "sell this",
  "add to whatnot". NOT for simple edits to existing items -- use rg-item-update for price
  changes, description tweaks, or adding images.
metadata:
  version: "3.7"
  author: scottybe
  updated: "2026-02-16"
  changelog: |
    v3.7 - Packaging refactor for Mac app compatibility:
    - Moved JSON payloads, formatting rules, troubleshooting, and publishing commands to references/
    - SKILL.md trimmed from 987 to ~500 lines for reliable .skill import
    - No workflow changes; all content preserved in references/
    See CHANGELOG.md for full history.
---

# Richmond General Full Auto

Complete 10-phase workflow for onboarding new vintage/antique items from acquisition to sale-ready.

## Architecture Note

**Two environments:** Claude's container (text files via Filesystem tools) and User's Mac (binary operations via osascript). Use osascript for all file operations on user's Mac to avoid path case sensitivity issues.

## Quick Reference

| Key | Value |
|-----|-------|
| Square Location | B87BAEZ0NWV34 (Richmond General) |
| Merchant ID | 7MM9AFJAD0XHW |
| SKU Prefix | RG-XXXX (sequential) |
| GitHub Pages | https://richmondgeneral.github.io/items/ |
| Working Directory | `/Users/scottybe/workspace/square/items/` |

### Category Assignment

Pick one **type** (primary, sets `reporting_category`) + one **tier** (secondary). See `references/square-catalog.md` for full category ID table.

| Type | Use For |
|------|---------|
| Books & Paper | Books, magazines, paper ephemera |
| Furniture | Stools, trunks, tables, chairs |
| Pottery & Ceramics | Mugs, vases, plaques, figurines |
| Collectibles | Games, toys, dolls, vintage misc |
| Art & Craft Kits | Watercolor kits, craft supplies |
| Wellness & Apothecary | Teas, serums, natural products |
| The Apothecary Cabinet | Sage, ritual items, candles |
| Home & Gifts | Home decor, giftable items |
| Analog | Vinyl, pinball, analog tech |

**Tiers:** The New Finds (default) or The Real Rarities (genuinely special).

### Channel Classification By Phase

- **Phase 2 (Square):** Use Square category IDs from `references/square-catalog.md`.
- **Phase 7 (GitHub Pages):** Use website filter slugs in `data-category` (not Square IDs).
- **Phase 8 (Whatnot):** Use Whatnot CSV category labels (not Square IDs, not website slugs).

## Python Environment

All scripts use **uv**: `uv run --project ~/.claude/skills python ~/.claude/skills/<skill>/scripts/<script>.py <args>`

---

## Phase 0: Image Processing

**All image processing runs on USER'S MAC via osascript.** Binary files cannot transfer between environments.

### Step 0.1: Get next SKU from cache

```
square_cache_mcp:square_cache_search with sku_pattern: "RG-"
```
Find highest RG-XXXX and increment.

### Step 0.2: Verify SKU not taken

```
square_cache_mcp:square_cache_search with sku_pattern: "RG-XXXX"
```
Check for exact SKU match (not substring). If taken, increment and re-check. Do NOT use `searchItems` with `text_filter`.

### Step 0.3: Create item folder

```applescript
do shell script "mkdir -p /Users/scottybe/workspace/square/items/RG-XXXX"
```

### Step 0.4: Auto-discover product photo cluster (preferred)

```applescript
do shell script "source ~/.local/bin/env && uv run --project ~/.claude/skills python ~/.claude/skills/photos-library/scripts/find_product_clusters.py --days 14 --type product"
```

If clusters found: confirm with user, copy best image by UUID:
```applescript
do shell script "source ~/.local/bin/env && uv run --project ~/.claude/skills python ~/.claude/skills/image-processor/scripts/photos.py --copy 'PHOTO_UUID' --output '/Users/scottybe/workspace/square/items/RG-XXXX/source-original.EXT' 2>&1"
```

If no cluster found, fall back to Step 0.5.

### Step 0.5: Locate user's image (manual fallback)

Check both Desktop and Downloads:
```applescript
do shell script "ls -lt ~/Desktop/*.jpg ~/Desktop/*.jpeg ~/Desktop/*.png ~/Desktop/*.heic ~/Downloads/*.jpg ~/Downloads/*.jpeg ~/Downloads/*.png 2>/dev/null | head -10"
```

### Step 0.6: Check file size & prepare input

Check size (`stat -f%z`). If > 20MB, compress first: `sips -Z 3000 source --out hero_temp.png`. Convert HEIC to PNG if needed: `sips -s format png source --out hero_temp.png`.

### Step 0.7: Remove background

```applescript
do shell script "source ~/.local/bin/env && source ~/.env && uv run --project ~/.claude/skills python ~/.claude/skills/image-processor/scripts/process.py '/ABSOLUTE/REMOVE_BG_INPUT' --output '/Users/scottybe/workspace/square/items/RG-XXXX/hero.png' --quality premium --model removebg 2>&1"
```

Prerequisites: `~/.env` must have `REMOVEBG_API_KEY`. Monitor credits -- alert user if <= 5. If bg removal fails, fall back to original image.

---

## Phase 1: Appraisal & Research

### Step 1.0: View image for appraisal

Compress on Mac (`sips -Z 1500`), transfer via `Filesystem:copy_file_user_to_claude`, view with `view` tool.

### USER CHECKPOINTS (Do Not Assume)

**STOP and ask the user before proceeding:**

| Question | Why It Matters |
|----------|----------------|
| **Quantity** -- How many pieces? | Set of 9 vs single = different listing |
| **Selling strategy** -- Set or individual? | Changes title, pricing, inventory count |
| **Condition specifics** -- Chips, cracks, wear? | Affects price and disclosures |
| **Original elements** -- Stickers, labels, boxes? | Adds provenance value |
| **Lot assignment** -- Track acquisition cost? | Needed for margin analysis via `rg-lot-tracker` |

Do research first, then ask with context. Never assume quantity=1 or condition=excellent.

### Step 1.1: Assign lot & record acquisition cost

Delegate to `rg-lot-tracker` skill. Store `allocated_cost` for pricing validation. If user skips lot tracking, skip margin validation in Step 1.5.

### Step 1.2: Route to specialized appraiser if needed

| Item Type | Skill to Use |
|-----------|--------------|
| Books dated 1970 or earlier | `book-appraiser` -- **MUST USE** |
| Carnival glass (iridescent pressed glass) | `carnival-glass-appraiser` |
| Maker's marks (stamps, hallmarks) | `maker-mark-identifier` |
| General vintage | Continue here |

### Step 1.3: Research

1. Identify maker/manufacturer, 2. Date the piece, 3. Assess condition, 4. Research comps, 5. Determine price point.

Pricing tiers: quick flip 2.5-3x, mid-range 3-4x, showcase research-based. See `rg-lot-tracker` for full margin targets.

### Step 1.4: Determine shipping eligibility

Ships easily: books, paper, small collectibles, sturdy standard-box items. Pickup only: furniture, large/awkward, extremely fragile, heavy (shipping cost ~ item value). Flat rate: Small $10.20 | Medium $17.10 | Large $21.90.

### Step 1.5: Validate pricing against cost basis

If `allocated_cost` available, delegate to `rg-lot-tracker` for margin analysis. If below target, present analysis -- user decides. Skip if lot tracking was skipped.

**Output from Phase 1:** Item title, description (HTML for `description_html`), price in cents, condition, SEO data, shippable YES/NO.

---

## Phase 2: Square Catalog Creation

**Method Selection:** Try `catalog.batchInsertObjects` first. Fallback: `catalog.upsertCatalogObject`. `idempotency_key` stays at TOP LEVEL for both. Variation MUST have `present_at_all_locations: false`.

**Description format:** Use `description_html` (NOT `description`). Use `<p>` tags + `<p>&nbsp;</p>` spacers + Unicode chars (not HTML entities). See `references/description-formatting.md` for full rules and template.

**Payloads:** See `references/api-payloads.md` for complete JSON templates (Payload A and Payload B).

```
mcp_square_api:make_api_request
  service: catalog
  method: batchInsertObjects   (primary)
  method: upsertCatalogObject  (fallback)
```

**Capture IDs:** Prefer `id_mappings` by temp IDs (`#RG-XXXX` -> CATALOG_ITEM_ID, `#RG-XXXX-var` -> VARIATION_ID). See `references/api-payloads.md` for fallback extraction logic.

---

## Phase 3: Set Inventory

```
mcp_square_api:make_api_request
  service: inventory
  method: batchChange
```

Do NOT include `catalog_object_type`. `quantity` is a STRING. `occurred_at` must be a current ISO timestamp (generate dynamically). See `references/api-payloads.md` for full JSON.

---

## Phase 4: Image Upload

Use `square-image-upload` skill script on user's Mac:

```applescript
do shell script "source ~/.local/bin/env && source ~/.env && uv run --project ~/.claude/skills python ~/.claude/skills/square-image-upload/scripts/upload_image.py --image '/Users/scottybe/workspace/square/items/RG-XXXX/hero.png' --item-id 'CATALOG_ITEM_ID' --name 'RG-XXXX Hero' --caption 'Front view' --primary 2>&1"
```

WebP not supported -- convert if needed: `sips -s format png image.webp --out hero.png`

### Step 4.1: Sync and verify square-cache

After Phase 2/3/4 writes, reconcile cache:

**Primary:** `square_cache_mcp:square_cache_sync`
**Fallback:** Run cache wrapper script via osascript.

**Category governance gate:**
```bash
python3 /Users/scottybe/.claude/skills/square-catalog-ops/scripts/catalog_ops.py audit-cleanup --fail-on-issues
```

Verify: 1. Exact SKU exists in cache (`square_cache_search`). 2. Cached item includes uploaded image ID (`square_cache_get_item`). If missing, sync once more.

---

## Phase 5: Payment Link

Shipping decision from Phase 1 determines `ask_for_shipping_address` (true for shippable, false for pickup).

```
mcp_square_api:make_api_request
  service: checkout
  method: createPaymentLink
```

See `references/api-payloads.md` for full JSON (shippable and pickup variants).

**Capture:** `payment_link.url` -> `https://square.link/u/XXXXXXXX`

---

## Phase 6: Generate Label

Append row to batch CSV at `/Users/scottybe/workspace/square/items/rg-labels-batch.csv`:

```csv
Product Name,Attributes,Price,Condition,Condition Notes,SKU,QR Code URL
"Item Title","Era . Type . Feature",55.00,Good,"Wear notes",RG-XXXX,https://richmondgeneral.github.io/items/RG-XXXX/
```

Every item gets a QR code linking to the info card. See `references/label-format.md` for Print Master settings.

---

## Phase 7: Info Card & Publishing

Run only if item should be published to GitHub Pages. Site: https://richmondgeneral.github.io/items/ | Repo: `/Users/scottybe/workspace/square/items/`

### Step 7.1: Write index.html (FLIP CARD TEMPLATE REQUIRED)

Use the flip card template from `references/info-card-template.html`. Do NOT use detail-page layouts.

Write populated template to `/Users/scottybe/workspace/square/items/RG-XXXX/index.html` via `Filesystem:write_file`.

**Requirements:** `.flip-card`/`.card-front`/`.card-back` structure, `aspect-ratio: 5 / 7`, CSS variables `--rg-gold`/`--rg-cream`/`--rg-charcoal`, flip animation, keyboard accessibility, ARIA, responsive breakpoints, print styles.

**Placeholders:** `{{SKU}}`, `{{ITEM_TITLE}}`, `{{ERA_LINE}}`, `{{PRICE}}`, `{{STORY_TEXT}}`, `{{DETAIL_N_LABEL}}`, `{{DETAIL_N_VALUE}}`, `{{CONDITION}}`, `{{PAYMENT_LINK}}`, `{{SEO_DESCRIPTION}}`, `{{OG_DESCRIPTION}}`

**DO NOT** use traditional multi-section layouts, simplified CSS variables, or omit the flip animation / 5x7 ratio.

### Steps 7.2-7.6: QR code, gallery, count, cleanup, git push

See `references/info-card-publishing.md` for exact commands:
- **7.2:** Generate QR code (Python qrcode library via osascript)
- **7.3:** Add item card to gallery `index.html` (sed via osascript)
- **7.4:** Update item count in gallery
- **7.5:** Cleanup temp files
- **7.6:** `git add`, `git commit`, `git push origin main`

**Customer flow:** QR on label -> Info card -> Read story -> Buy Now -> Square checkout

---

## Phase 8: Whatnot Item Library Listing

Run only if item should be listed on Whatnot.

**Dependencies:** Read `whatnot-catalog` (field values, categories, shipping) and `whatnot-chrome` (Chrome automation) skills.

**Account:** richmondgeneral on whatnot.com. Images must be pushed (Step 7.6) before Whatnot can fetch them.

### Step 8.1: Build CSV Row

Look up in `whatnot-catalog`: Category/Sub Category, Shipping Profile (weight heuristic), Price via `ceil(square_price_cents / 100)`, Condition, Hazmat.

Append to `/Users/scottybe/workspace/square/items/rg-inventory/whatnot-import.csv`. Create headers first if file doesn't exist.

### Step 8.2: Upload CSV to Whatnot

Ensure git push (Step 7.6) completed. Follow `whatnot-chrome` "CSV Import via Chrome" steps: get tab context, navigate, find import button, inject CSV via DataTransfer API, click Import, verify drafts.

### Step 8.3: Fill Category-Specific Metadata

Read `whatnot-catalog` "Category-Specific Metadata Fields" for valid values. Follow `whatnot-chrome` "React Combobox Interaction" pattern for each field. Verify Shipping Profile matches weight heuristic.

If `whatnot-catalog` has a TODO for this category: screenshot edit page, ask user, fill manually, then update `whatnot-catalog` with discovered fields.

### Step 8.4: Publish Drafts

Follow `whatnot-chrome` "Publish Drafts Pass": navigate to drafts, open each, publish, confirm, verify live.

---

## Phase 9: Photos Library Archive (Cleanup)

Organize source photos into per-item albums in Photos.app (`Richmond General Archive/RG-XXXX/`).

Prerequisite: Git push (Step 7.6) must be complete.

### Step 9.1: Archive photos

**Mode A -- Direct UUID** (from Step 0.4 cluster discovery):
```applescript
do shell script "source ~/.local/bin/env && uv run --project ~/.claude/skills python ~/.claude/skills/photos-library/scripts/archive_photos.py --item-id RG-XXXX --uuids UUID1 UUID2 UUID3 --json 2>&1"
```

**Mode B -- Reverse filename lookup** (from Step 0.5 manual):
```applescript
do shell script "source ~/.local/bin/env && uv run --project ~/.claude/skills python ~/.claude/skills/photos-library/scripts/archive_photos.py --item-id RG-XXXX --reverse --include 'IMG_*' --json 2>&1"
```

Add `--dry-run` to preview without touching Photos.

### Step 9.2: Verify archive

Confirm output JSON shows `archived > 0`. This does NOT delete photos -- only adds to album. User can bulk-delete from "Richmond General Archive" folder when satisfied.

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

After completing full workflow, print summary. See `references/workflow-summary.md` for template.

---

## Troubleshooting

See `references/troubleshooting.md` for common issues (image size, upload failures, API errors, path case mismatches).

---

## Related Skills

| Skill | Use For |
|-------|---------|
| `rg-item-update` | Quick edits to existing items |
| `square-image-upload` | Image upload via API |
| `square-catalog-ops` | Compliance proof, category merges, cleanup audits |
| `square-webhook-monitor` | Webhook subscription operations and local monitoring |
| `book-appraiser` | Antiquarian books, LOC cross-reference |
| `carnival-glass-appraiser` | Pressed iridescent glass 1908-1930s |
| `maker-mark-identifier` | Pottery, silver, furniture marks |
| `product-labeler` | Label generation, Square descriptions |
| `square-cache` | Fast catalog lookups |
| `photos-library` | Auto-discover and cluster local Photos shoots |
| `rg-lot-tracker` | Lot tracking, cost allocation, margin validation |
| `whatnot-catalog` | Whatnot category data, allowed values, shipping heuristics (Phase 8) |
| `whatnot-chrome` | Whatnot Chrome automation patterns (Phase 8) |

## References

- `references/square-catalog.md` - Category IDs, location/merchant IDs, API details
- `references/api-payloads.md` - JSON templates for Phase 2/3/5
- `references/description-formatting.md` - HTML formatting rules for `description_html`
- `references/info-card-template.html` - Flip card HTML template for Phase 7
- `references/info-card-publishing.md` - QR code, gallery insertion, git commands for Phase 7
- `references/label-format.md` - Print Master CSV settings
- `references/marketplace-templates.md` - Title/description templates across platforms
- `references/mcp-connectors.md` - MCP connector quick reference
- `references/system-paths.md` - Canonical absolute paths
- `references/troubleshooting.md` - Common issues and fixes
- `references/workflow-summary.md` - Post-workflow output template
