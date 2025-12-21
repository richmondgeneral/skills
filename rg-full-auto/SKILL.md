---
name: rg-full-auto
description: End-to-end 7-phase workflow for onboarding NEW items to Richmond General from acquisition through sale. Covers appraisal, lot/acquisition cost tracking, photography, Square catalog creation, fulfillment, payment links, labels, and info card publishing. Use when processing a new acquisition from scratch or doing a complete item redo. Triggers on "new item", "full workflow", "onboard", "process acquisition", "add to inventory", "process this photo". NOT for simple edits to existing items—use rg-item-update for price changes, description tweaks, or adding images.
metadata:
  version: "1.1"
  author: scottybe
---

# Richmond General Full Auto

Complete 7-phase workflow for onboarding new vintage/antique items from acquisition to sale-ready.

## Quick Reference

| Key | Value |
|-----|-------|
| Square Location | B87BAEZ0NWV34 (Richmond General) |
| Merchant ID | 7MM9AFJAD0XHW |
| SKU Prefix | RG-XXXX (sequential) |
| GitHub Pages | https://richmondgeneral.github.io/items/ |
| Working Directory | `/Users/scottybe/Workspace/items/` |

### Category Assignment (choose ONE)

| Category | ID | Use For |
|----------|----|---------|
| The Real Rarities | `FL4L42RRUE5UXMWFDLXOCNB5` | Rare, special, showcase-worthy pieces |
| The New Finds | `P34KX3L7XRZJJ5RP6W35K4YO` | Regular new inventory arrivals |

**Decision:** Is this genuinely rare/special → The Real Rarities. Standard new stock → The New Finds.

## Phase 0: Image Processing

**Get next SKU (PRIMARY METHOD):**
Use the `square-cache` skill to lookup highest existing SKU:
```bash
# Via MCP (recommended)
Use square-cache skill to query existing SKU numbers
```

**Fallback (local directory scan):**
```bash
# If offline, scan local directory
ls ~/Workspace/items | grep -oE 'RG-[0-9]+' | sort -t'-' -k2 -n | tail -1
```

**Copy uploaded image to working directory:**
```bash
mkdir -p ~/Workspace/items/RG-XXXX
cp /path/to/uploaded/image.jpg ~/Workspace/items/RG-XXXX/original.jpg
```

**Remove background (use gemini-chat skill):**
```bash
python3 ~/.claude/skills/gemini-chat/chat.py process \
  ~/Workspace/items/RG-XXXX/original.jpg \
  --output ~/Workspace/items/RG-XXXX/RG-XXXX-hero.png \
  --quality high
```

**Alternative via scripts:**
```bash
python3 ~/.claude/skills/rg-full-auto/scripts/remove_background.py \
  ~/Workspace/items/RG-XXXX/original.jpg \
  ~/Workspace/items/RG-XXXX/RG-XXXX-hero.png
```

## Phase 1: Appraisal, Lot Assignment & Research

**First: Assign to lot and record acquisition cost**
- Lot prefix format: `L##-` (e.g., L2 = Peter's Estate)
- Record: lot ID, purchase date, total lot cost, item cost allocation
- See `references/lot-tracking.md` for full lot management

**Route to specialized skills if needed:**
- Books pre-1970 → `book-appraiser`
- Maker's marks, pottery, carnival glass → `carnival-glass-appraiser`, `maker-mark-identifier`
- General vintage → continue here

**Research checklist:**
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

See `references/pricing-guidelines.md` for category-specific margins.

## Phase 2: Photography & Images

**Required shots:**
1. Hero (front, clean background)
2. Back/bottom (marks, labels)
3. Details (condition issues, unique features)
4. Scale reference if size matters

**Specs:** Min 1000px longest edge, transparent PNG preferred for hero

**File naming:** `RG-XXXX-01.png`, `RG-XXXX-02.png`

### Image Upload

**Via square-image-upload skill (REQUIRED - do NOT use direct API calls):**
Use the `square-image-upload` skill via MCP:
```
Square:upload_image
  image_path: ~/Workspace/items/RG-XXXX/RG-XXXX-hero.png
  item_id: CATALOG_ITEM_ID
  name: "RG-XXXX Hero"
  caption: "Front view"
  primary: true
```

**⚠️ Important:**
- Do NOT use direct API calls (403 authorization error)
- Use the MCP-based square-image-upload skill instead
- MCP handles proper authentication and token scopes
- WebP not supported - convert if needed:
```bash
sips -s format jpeg RG-XXXX-hero.webp --out RG-XXXX-hero.jpeg
```

## Phase 3: Square Catalog Creation

**Use Square MCP:**
```
Square:make_api_request
  service: catalog
  method: batchUpsertCatalogObjects
```

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

**Capture from response:** `id_mappings[0].object_id` → ITEM_ID, `id_mappings[1].object_id` → VARIATION_ID

### Set Inventory Count (Required)

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

## Phase 4: Fulfillment Setup

**Use judgment** - price is NOT a factor.

**Ships easily:** Books, paper goods, small collectibles, sturdy items

**Pickup only:** Furniture, large/awkward shapes, extremely fragile, heavy items where shipping ≈ item value

**Flat rate reference:** Small $10.20 | Medium $17.10 | Large $21.90

Configure in Square Dashboard: enable shipping, set weight/dimensions, assign profile.

## Phase 5: Payment Link Generation

```json
{
  "idempotency_key": "rg-XXXX-pay-TIMESTAMP",
  "quick_pay": {
    "name": "Item Title",
    "price_money": {"amount": 1999, "currency": "USD"},
    "location_id": "B87BAEZ0NWV34"
  },
  "checkout_options": {"ask_for_shipping_address": true}
}
```

Returns: `payment_link.url` → `https://square.link/u/XXXXXXXX`

## Phase 6: Labels & Batch CSV

**Batch file:** `/Users/scottybe/Workspace/items/rg-labels-batch.csv`

```csv
Product Name,Attributes,Price,Condition,Condition Notes,SKU,QR Code URL
"Item Title","Era • Type • Feature",55.00,Good,"Wear notes",RG-0003,https://richmondgeneral.github.io/items/RG-0003/
```

**Append row:**
```bash
echo '"Item Title","Era • Type • Feature",55.00,Good,"Wear notes",RG-XXXX,https://richmondgeneral.github.io/items/RG-XXXX/' >> ~/Workspace/items/rg-labels-batch.csv
```

**Include QR when:** Antiques (pre-1950), collectibles with story, items with info cards

See `references/label-format.md` for Print Master settings.

## Phase 7: Info Card & Publishing

**Site:** https://richmondgeneral.github.io/items/

**Step 1: Place QR and images in repo**
```bash
python3 ~/.claude/skills/rg-full-auto/scripts/place_files.py \
  --sku RG-XXXX \
  --qr-base64 <base64_encoded_qr> \
  --image ~/Workspace/items/RG-XXXX/RG-XXXX-hero.png
```
This creates `RG-XXXX/` folder in repo with QR code and hero image.

**Step 2: Create info card**
1. Copy `template/rg-item-card-template.html` → `RG-XXXX/index.html`
2. Replace placeholders: `{{SKU}}`, `{{ITEM_TITLE}}`, `{{PRICE}}`, `{{STORY_TEXT}}`, etc.
3. Generate QR for payment link (brand colors: Gold #C9A961, Cream #F5F1E8, Charcoal #2C2C2C)

**Step 3: Publish**
4. Add to gallery grid in `index.html`
5. Commit and push to `main`

**Customer flow:** QR on label → Info card → Read story → Buy Now → Square checkout

## Quick Tasks (Single Phase)

| Request | Action |
|---------|--------|
| "make a label for..." | Phase 6 only |
| "price this" / "what's this worth" | Phase 1 only |
| "upload this image to Square" | Phase 2 image upload only |
| "create a payment link" | Phase 5 only |
| "what's the SKU for..." | Cache lookup only |

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
   Hero: ~/Workspace/items/RG-XXXX/RG-XXXX-hero.png
   Square URL: {IMAGE_URL}

🚚 Fulfillment: Shippable / Pickup only

💳 Payment Link: {PAYMENT_LINK_URL}

🏷️ Label: Added to rg-labels-batch.csv

📄 Info Card: https://richmondgeneral.github.io/items/RG-XXXX/

Next: Print label, place item on floor
```

## Troubleshooting

**Background removal fails:**
- Check API keys: `echo $REMOVEBG_API_KEY` or `echo $GEMINI_API_KEY`
- Try alternative model: `--model removebg` or `--model gemini25`

**Square 401 Unauthorized:**
- Token expired: `echo $SQUARE_ACCESS_TOKEN`

**Image upload 413 Too Large:**
- Compress: `sips -Z 2000 image.jpeg`

**Item shows "sold out":**
- Missing inventory count (Phase 3 step 2)

**Square 403 on image upload:**
- Do NOT use direct API calls (e.g., raw requests library)
- Use `square-image-upload` skill via MCP instead
- MCP properly handles authentication and token scopes
- Direct `SQUARE_ACCESS_TOKEN` lacks image upload permissions

**MCP vs Direct API authentication:**
- MCP requests (via `call_mcp_tool`) use different auth mechanism than direct API calls
- MCP server handles OAuth/scopes properly
- Direct API calls need specific token permissions
- Always use MCP-based skills for Square operations when available

**place_files.py fails to find repo:**
- Default path: `~/Workspace/items`
- Override with `--repo-path` argument
- Ensure directory exists: `mkdir -p ~/Workspace/items`

**QR code base64 decode fails:**
- Verify base64 string is complete (no truncation)
- Check for leading/trailing whitespace
- Ensure output PNG file has write permissions in destination directory

## Related Skills

| Skill | Use For |
|-------|---------|
| `rg-item-update` | Quick edits to existing items |
| `gemini-chat` | Background removal, image processing |
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
