---
name: rg-full-auto
description: End-to-end 7-phase workflow for onboarding NEW items to Richmond General from acquisition through sale. Covers appraisal, lot/acquisition cost tracking, photography, Square catalog creation, fulfillment, payment links, labels, and info card publishing. Use when processing a new acquisition from scratch or doing a complete item redo. Triggers on "new item", "full workflow", "onboard", "process acquisition", "add to inventory", "process this photo". NOT for simple edits to existing items—use rg-item-update for price changes, description tweaks, or adding images.
metadata:
  version: "1.2"
  author: scottybe
  updated: "2024-12-20"
---

# Richmond General Full Auto

Complete 7-phase workflow for onboarding new vintage/antique items from acquisition to sale-ready.

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
| Working Directory | `/Users/scottybe/Workspace/items/` |

### Category Assignment (choose ONE)

| Category | ID | Use For |
|----------|----|------------|
| The Real Rarities | `FL4L42RRUE5UXMWFDLXOCNB5` | Rare, special, showcase-worthy pieces |
| The New Finds | `P34KX3L7XRZJJ5RP6W35K4YO` | Regular new inventory arrivals |

**Decision:** Is this genuinely rare/special → The Real Rarities. Standard new stock → The New Finds.

## Phase 0: Image Processing

**⚠️ CRITICAL:** Image processing runs on USER'S MAC via osascript, NOT in Claude's container. Binary files cannot transfer between environments.

**Get next SKU via Square MCP:**
```
Square:make_api_request
  service: catalog
  method: searchCatalogItems
  request: {"product_types": ["REGULAR"], "limit": 100}
```
Then find highest RG-XXXX SKU from results.

**Locate user's uploaded image:**
User uploads appear in `/mnt/user-data/uploads/` in Claude's container, but we need the file on user's Mac. Check common locations:
```applescript
do shell script "ls ~/Downloads/*.jpg ~/Downloads/*.jpeg ~/Desktop/*.jpg ~/Desktop/*.jpeg 2>/dev/null | head -10"
```

**Remove background via osascript (runs on user's Mac):**
```applescript
do shell script "source ~/.env && python3 << 'EOF'
import os
import requests

api_key = os.environ.get('REMOVEBG_API_KEY')
input_path = '/Users/scottybe/Downloads/IMAGE_NAME.jpg'
output_path = '/Users/scottybe/workspace/square/items/RG-XXXX/hero.png'

with open(input_path, 'rb') as f:
    response = requests.post(
        'https://api.remove.bg/v1.0/removebg',
        files={'image_file': f},
        data={'size': 'auto'},
        headers={'X-Api-Key': api_key},
    )
response.raise_for_status()

with open(output_path, 'wb') as out:
    out.write(response.content)
print(f'Background removed: {output_path}')
EOF
"
```

**Prerequisites:** User must have `~/.env` with `REMOVEBG_API_KEY` and image accessible on their Mac.

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

**⚠️ KNOWN LIMITATION:** Direct API image upload returns 403 Forbidden. The MCP token lacks `ITEMS_WRITE` scope for multipart uploads.

**Workarounds (choose one):**

1. **Manual upload (recommended):** Upload hero.png via Square Dashboard → Catalog → Item → Images
2. **Skip Square image:** Flipcard on GitHub Pages shows the image; Square listing works without photo
3. **Batch upload script:** User runs `upload_square_images.py` locally with full OAuth token

**If API upload is ever fixed:**
```bash
python3 ~/.claude/skills/square-image-upload/scripts/upload_image.py \
  --image ~/Workspace/items/RG-XXXX/RG-XXXX-hero.png \
  --item-id CATALOG_ITEM_ID \
  --name "RG-XXXX Hero" \
  --caption "Front view" \
  --primary
```

**⚠️ WebP not supported** - convert if needed:
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
**Repo:** /Users/scottybe/workspace/square/items/

**⚠️ CRITICAL:** All file operations for Phase 7 run on USER'S MAC via osascript. Only index.html (text) can be written via Filesystem tools.

### Step 1: Create item folder
```applescript
do shell script "mkdir -p /Users/scottybe/workspace/square/items/RG-XXXX"
```

### Step 2: Write index.html (via Filesystem tools - text file OK)
Use `Filesystem:write_file` to write the populated template to:
`/Users/scottybe/workspace/square/items/RG-XXXX/index.html`

### Step 3: Generate QR code (via osascript - binary file)
```applescript
do shell script "cd /Users/scottybe/workspace/square/items/RG-XXXX && python3 -c \"
import qrcode
qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
qr.add_data('https://square.link/u/XXXXXXXX')
qr.make(fit=True)
img = qr.make_image(fill_color='#2C2C2C', back_color='white')
img.save('qr-code.png')
print('QR code saved')
\""
```

### Step 4: Hero image (already placed in Phase 0)
Background removal output goes directly to `/Users/scottybe/workspace/square/items/RG-XXXX/hero.png`

### Step 5: Git commit and push
```applescript
do shell script "cd /Users/scottybe/workspace/square/items && git add RG-XXXX/ && git commit -m 'Add RG-XXXX: Item Title' && git push origin main 2>&1"
```

**Customer flow:** QR on label → Info card → Read story → Buy Now → Square checkout

**Brand colors:** Gold #C9A961, Cream #F5F1E8, Charcoal #2C2C2C

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

**Square 403 on image upload:**
- MCP token lacks `ITEMS_WRITE` scope for multipart uploads
- Workaround: Manual upload via Square Dashboard, or skip (flipcard shows image anyway)
- Root cause: MCP uses different OAuth flow than direct API calls

**Background removal fails:**
- Check API keys on user's Mac: `source ~/.env && echo $REMOVEBG_API_KEY`
- Ensure image is accessible on user's Mac (not just in Claude's container)

**Binary file transfer fails:**
- Binary files (PNG, JPEG) cannot transfer between Claude's container and user's Mac
- Solution: Generate binaries via osascript on user's Mac directly

**Square 401 Unauthorized:**
- Token expired: Check `$SQUARE_ACCESS_TOKEN`

**Image upload 413 Too Large:**
- Compress: `sips -Z 2000 image.jpeg`

**Item shows "sold out":**
- Missing inventory count (Phase 3 step 2)

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
