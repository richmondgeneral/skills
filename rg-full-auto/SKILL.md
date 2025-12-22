---
name: rg-full-auto
description: End-to-end 8-phase workflow for onboarding NEW items to Richmond General from acquisition through sale. Covers appraisal, lot/acquisition cost tracking, photography, Square catalog creation, image upload, payment links, labels, and info card publishing. Use when processing a new acquisition from scratch, doing a complete item redo, or user says "list this item" or "sell this". Triggers on "new item", "full workflow", "onboard", "process acquisition", "add to inventory", "process this photo", "list item", "sell this". NOT for simple edits to existing items—use rg-item-update for price changes, description tweaks, or adding images.
metadata:
  version: "2.3"
  author: scottybe
  updated: "2025-12-21"
  changelog: |
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

Complete 8-phase workflow for onboarding new vintage/antique items from acquisition to sale-ready.

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

### Category Assignment (choose ONE)

| Category | ID | Use For |
|----------|----|---------|
| The Real Rarities | `FL4L42RRUE5UXMWFDLXOCNB5` | Rare, special, showcase-worthy pieces |
| The New Finds | `P34KX3L7XRZJJ5RP6W35K4YO` | Regular new inventory arrivals |

**Decision:** Is this genuinely rare/special → The Real Rarities. Standard new stock → The New Finds.

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
square-cache:square_cache_search with sku_pattern: "RG-"
```
Find highest RG-XXXX and increment to get candidate SKU.

### Step 0.2: Verify SKU not taken (live API check)

**Cache may be stale.** Before committing to the SKU, verify it doesn't exist:

```
Square:make_api_request
  service: catalog
  method: searchItems
  request: {"text_filter": "RG-XXXX"}
```

- If results empty (just `{"cursor":""}`) → SKU is safe, proceed
- If results contain this SKU → increment and check again
- Repeat until finding an unused SKU

### Step 0.3: Create item folder

```applescript
do shell script "mkdir -p /Users/scottybe/workspace/square/items/RG-XXXX"
```

### Step 0.4: Locate user's image

User uploads appear in `/mnt/user-data/uploads/` in Claude's container, but we need the file on user's Mac. 

**⚠️ CHECK BOTH LOCATIONS:** User often places images on Desktop, not just Downloads!

```applescript
do shell script "ls -lt ~/Desktop/*.jpg ~/Desktop/*.jpeg ~/Desktop/*.png ~/Desktop/*.heic ~/Downloads/*.jpg ~/Downloads/*.jpeg ~/Downloads/*.png 2>/dev/null | head -10"
```

Or use `Filesystem:list_directory` on `/Users/scottybe/Desktop` to see all files.

### Step 0.5: Check file size & compress if needed

**⚠️ remove.bg has a 22MB limit.** Check file size first:

```applescript
do shell script "stat -f%z '/Users/scottybe/Desktop/IMAGE_NAME.png'"
```

**If > 20MB (20000000 bytes):** Compress before background removal:
```applescript
do shell script "sips -Z 3000 '/Users/scottybe/Desktop/IMAGE_NAME.png' --out '/Users/scottybe/workspace/square/items/RG-XXXX/hero_temp.png'"
```

Then use `hero_temp.png` as input for background removal.

**If ≤ 20MB:** Use original file directly.

### Step 0.6: Remove background

```applescript
do shell script "source ~/.local/bin/env && source ~/.env && uv run --project ~/.claude/skills python ~/.claude/skills/rg-new-item/scripts/remove_background.py '/Users/scottybe/workspace/square/items/RG-XXXX/hero_temp.png' '/Users/scottybe/workspace/square/items/RG-XXXX/hero.png' 2>&1"
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
| **Lot assignment** — Track acquisition cost? | Optional but needed for margin analysis | L2-Peter's Estate @ $5 cost |

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

- Lot prefix format: `L##-` (e.g., L2 = Peter's Estate)
- Record: lot ID, purchase date, total lot cost, item cost allocation
- See `references/lot-tracking.md` for full lot management

**Even if user says "unknown"** — prompt once more: "Do you want to assign this to a lot for tracking, or skip for now?"

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

**Pricing tiers:**
| Tier | Range | Margin Target |
|------|-------|---------------|
| Quick flip | $1-15 | 2-3x cost |
| Mid-range | $15-75 | 2.5-4x cost |
| Showcase | $75+ | Research-based |

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

**Output from Phase 1:**
- Item title
- Description (HTML with `<br>` tags)
- Price in cents
- Condition grade
- SEO title and description
- **Shippable: YES or NO**

---

## Phase 2: Square Catalog Creation

**Use Square MCP:**
```
Square:make_api_request
  service: catalog
  method: batchInsertObjects   ← EXACT NAME (not batchUpsertCatalogObjects)
```

**⚠️ CRITICAL:** Variation MUST have `present_at_all_locations: false` at the variation level, not just the item level.

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
        "description": "HTML description with <br> tags",
        "categories": [{"id": "CHOSEN_CATEGORY_ID"}],
        "reporting_category": {"id": "CHOSEN_CATEGORY_ID"},
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

**Capture from response:**
- `objects[0].id` → CATALOG_ITEM_ID (e.g., `6CYX5VOFKOK2QN3P7TYVXSEH`)
- `objects[0].item_data.variations[0].id` → VARIATION_ID (e.g., `AR63H4MGON7VTBQ3TZB3KOHJ`)

---

## Phase 3: Set Inventory

**Use Square MCP:**
```
Square:make_api_request
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
      "occurred_at": "2025-12-21T19:32:00Z"
    }
  }]
}
```

**Note:** `quantity` is a STRING, not integer. `occurred_at` must be ISO 8601 format.

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

---

## Phase 5: Payment Link

**Shipping decision from Phase 1 determines `ask_for_shipping_address`:**

| Shippable? | Setting | Customer Experience |
|------------|---------|---------------------|
| YES | `"ask_for_shipping_address": true` | Customer enters address → you ship |
| NO | `"ask_for_shipping_address": false` | No address collected → pickup only |

**Use Square MCP:**
```
Square:make_api_request
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

**Categories for filter:** `books`, `furniture`, `pottery`, `collectibles`

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

## Quick Tasks (Single Phase)

| Request | Action |
|---------|--------|
| "make a label for..." | Phase 6 only |
| "price this" / "what's this worth" | Phase 1 only |
| "upload this image to Square" | Phase 4 only |
| "create a payment link" | Phase 5 only |
| "what's the SKU for..." | Cache lookup only |

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

🔍 SEO
   Title: {PAGE_TITLE}
   Permalink: {PERMALINK}

🚚 Fulfillment: {SHIPPING / PICKUP ONLY}

💳 Payment Link: {PAYMENT_LINK_URL}

🏷️ Label: Added to rg-labels-batch.csv

📄 Info Card: https://richmondgeneral.github.io/items/RG-XXXX/

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

## References

- `references/square-catalog.md` - API details, category IDs
- `references/lot-tracking.md` - Lot management, cost allocation
- `references/pricing-guidelines.md` - Margin targets by category
- `references/label-format.md` - Print Master settings, style guide
- `references/info-card-template.html` - HTML template for item pages
