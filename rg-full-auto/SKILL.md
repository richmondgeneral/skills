---
name: rg-full-auto
description: End-to-end 8-phase workflow for onboarding NEW items to Richmond General from acquisition through sale. Covers appraisal, lot/acquisition cost tracking, photography, Square catalog creation, image upload, payment links, labels, and info card publishing. Use when processing a new acquisition from scratch or doing a complete item redo. Triggers on "new item", "full workflow", "onboard", "process acquisition", "add to inventory", "process this photo". NOT for simple edits to existing items—use rg-item-update for price changes, description tweaks, or adding images.
metadata:
  version: "1.7"
  author: scottybe
  updated: "2025-12-21"
---

# Richmond General Full Auto

Complete 8-phase workflow for onboarding new vintage/antique items from acquisition to sale-ready.

## Architecture Note

**Two environments exist:**
1. **Claude's container** - Linux environment where Claude runs. Has `/mnt/user-data/uploads/` for user uploads, `/mnt/skills/` for skills. Can write TEXT files to user's Mac via Filesystem tools.
2. **User's Mac** - Where binary operations (image processing, QR generation) must run via osascript. Has `~/.env` with API keys, git repos, and full filesystem access.

**Rule:** Text files (HTML, CSV, MD) → Filesystem tools. Binary files (PNG, JPEG) → osascript on user's Mac.

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

- If results empty → SKU is safe, proceed
- If results contain this SKU → increment and check again
- Repeat until finding an unused SKU

### Step 0.3: Create item folder

```applescript
do shell script "mkdir -p /Users/scottybe/workspace/square/items/RG-XXXX"
```

### Step 0.4: Locate user's image

User uploads appear in `/mnt/user-data/uploads/` in Claude's container, but we need the file on user's Mac. Check common locations:
```applescript
do shell script "ls ~/Downloads/*.jpg ~/Downloads/*.jpeg ~/Downloads/*.png ~/Desktop/*.jpg ~/Desktop/*.jpeg 2>/dev/null | head -10"
```

### Step 0.5: Remove background

```applescript
do shell script "source ~/.local/bin/env && source ~/.env && uv run --project ~/.claude/skills python ~/.claude/skills/rg-new-item/scripts/remove_background.py '/Users/scottybe/Downloads/IMAGE_NAME.jpg' '/Users/scottybe/workspace/square/items/RG-XXXX/hero.png'"
```

**Prerequisites:** `~/.env` must have `REMOVEBG_API_KEY`. Note: Must `source ~/.env` to load API key.

**If bg removal fails:** Fall back to original image, note in description that background removal is pending.

---

## Phase 1: Appraisal & Research

### Step 1.1: Assign lot & record acquisition cost

- Lot prefix format: `L##-` (e.g., L2 = Peter's Estate)
- Record: lot ID, purchase date, total lot cost, item cost allocation
- See `references/lot-tracking.md` for full lot management

### Step 1.2: Route to specialized appraiser if needed

- Books pre-1970 → `book-appraiser`
- Carnival glass → `carnival-glass-appraiser`
- Maker's marks (pottery, silver, furniture) → `maker-mark-identifier`
- General vintage → continue here

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
  method: batchInsertObjects
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
- `id_mappings[0].object_id` → ITEM_ID
- `id_mappings[1].object_id` → VARIATION_ID

---

## Phase 3: Set Inventory

**Use Square MCP:**
```
Square:make_api_request
  service: inventory
  method: batchChange
```

```json
{
  "idempotency_key": "rg-XXXX-inv-TIMESTAMP",
  "changes": [{
    "type": "PHYSICAL_COUNT",
    "physical_count": {
      "catalog_object_id": "VARIATION_ID",
      "state": "IN_STOCK",
      "location_id": "B87BAEZ0NWV34",
      "quantity": "1",
      "occurred_at": "ISO_TIMESTAMP"
    }
  }]
}
```

Without this, items show "sold out" online.

---

## Phase 4: Upload Image to Square

**Execute on user's Mac via osascript:**
```applescript
do shell script "source ~/.local/bin/env && source ~/.env && uv run --project ~/.claude/skills python ~/.claude/skills/square-image-upload/scripts/upload_image.py --image '/Users/scottybe/workspace/square/items/RG-XXXX/hero.png' --item-id 'CATALOG_ITEM_ID' --name 'RG-XXXX Hero' --caption 'Front view' --primary"
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

```bash
echo '"Item Title","Era • Type • Feature",55.00,Good,"Wear notes",RG-XXXX,https://richmondgeneral.github.io/items/RG-XXXX/' >> ~/workspace/square/items/rg-labels-batch.csv
```

**Every item gets a QR code** on its label, linking to the info card. This is the customer experience—scan, read the story, buy.

See `references/label-format.md` for Print Master settings.

---

## Phase 7: Info Card & Publishing

**Site:** https://richmondgeneral.github.io/items/
**Repo:** /Users/scottybe/workspace/square/items/

### Step 7.1: Write index.html

Use `Filesystem:write_file` to write the populated template to:
`/Users/scottybe/workspace/square/items/RG-XXXX/index.html`

(Item folder already exists from Phase 0.2)

### Step 7.2: Generate QR code (payment link)

```applescript
do shell script "source ~/.local/bin/env && cd /Users/scottybe/workspace/square/items/RG-XXXX && uv run --project ~/.claude/skills python -c \"import qrcode; qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2); qr.add_data('https://square.link/u/XXXXXXXX'); qr.make(fit=True); img = qr.make_image(fill_color='#2C2C2C', back_color='white'); img.save('qr-code.png'); print('QR code saved')\""
```

### Step 7.3: Git commit and push

```applescript
do shell script "cd /Users/scottybe/workspace/square/items && git add RG-XXXX/ && git commit -m 'Add RG-XXXX: Item Title' && git push origin main 2>&1"
```

**Customer flow:** QR on label → Info card → Read story → Buy Now → Square checkout

**Brand colors:** Gold #C9A961, Cream #F5F1E8, Charcoal #2C2C2C

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

**Image upload fails:**
- Ensure catalog item created FIRST (need ITEM_ID for image upload)
- Check token: `source ~/.env && echo $SQUARE_ACCESS_TOKEN`
- Verify image is PNG or JPEG (WebP not supported)

**Background removal fails:**
- Check API keys on user's Mac: `source ~/.env && echo $REMOVEBG_API_KEY`
- Ensure image is accessible on user's Mac (not just in Claude's container)

**Binary file transfer fails:**
- Binary files (PNG, JPEG) cannot transfer between Claude's container and user's Mac
- Solution: Generate binaries via osascript on user's Mac directly

**Square 401 Unauthorized:**
- Token expired: Check `$SQUARE_ACCESS_TOKEN`

**Image upload 413 Too Large:**
- Compress: `sips -Z 2000 image.png`

**Item shows "sold out":**
- Missing inventory count (Phase 3)

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
