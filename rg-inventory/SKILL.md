---
name: rg-inventory
description: Richmond General inventory management system. Use when processing items for the store, creating Square catalog entries, pricing vintage/antique items, generating labels, or tracking purchase lots and provenance. Triggers on inventory, pricing, labeling, Square catalog, or Richmond General store tasks.
---

# Richmond General Inventory System

Complete workflow for processing vintage and antique items from acquisition through sale.

## Trigger Patterns

**FULL 7-PHASE WORKFLOW** — Run complete end-to-end automation:
- "use the inventory skill to add this"
- "new item" + uploaded photo
- "add this to inventory"
- "process this for the store"
- "full workflow for this item"

**QUICK TASKS** — Do only what's asked:
- "make a label for..." → Phase 6 only (label CSV row)
- "price this" / "what's this worth" → Phase 1 only (appraisal)
- "upload this image to Square" → Phase 2b only
- "create a payment link" → Phase 5 only
- "what's the SKU for..." → Cache lookup only

## Quick Reference

**Square Location:** B87BAEZ0NWV34 (Richmond General - ACTIVE)
**Merchant ID:** 7MM9AFJAD0XHW
**SKU Prefix:** RG-XXXX (sequential)
**GitHub Pages:** https://richmondgeneral.github.io/items/
**Repository:** github.com/richmondgeneral/items

## Full Workflow: Photo → Sale-Ready

When user uploads a photo and triggers full workflow, execute ALL phases automatically:

### Phase 0: Image Processing (Automated)

**Claude executes these on user's machine via Filesystem tools:**

**Step 1: Get next SKU**
```bash
# Check highest existing SKU in cache
cd ~/square-tools && ./bin/square_cache.sh search "RG-" | grep -oE 'RG-[0-9]+' | sort -t'-' -k2 -n | tail -1
```

**Step 2: Copy uploaded image to working directory**
```bash
# Create working directory for this item
mkdir -p ~/items/RG-XXXX
cp /path/to/uploaded/image.jpg ~/items/RG-XXXX/original.jpg
```

**Step 3: Remove background**
```bash
# Run background removal service (uses Gemini/Remove.bg)
cd ~/square-tools && ~/.pyenv/shims/python3 cache-system/bg_removal_service.py \
  ~/items/RG-XXXX/original.jpg \
  gemini \
  --output ~/items/RG-XXXX/RG-XXXX-hero.png
```

**Step 4: Verify output**
```bash
ls -la ~/items/RG-XXXX/
```

**If bg removal fails:** Fall back to original image, note in description that background removal is pending.

### Phase 1: Appraisal & Research

**Route to domain appraiser when applicable:**
- Books pre-1970 or antiquarian → Load `book-appraiser` skill
- Carnival glass (iridescent pressed glass) → Load `carnival-glass-appraiser` skill
- Maker's marks (pottery, silver, furniture) → Load `maker-mark-identifier` skill
- General vintage items → Claude analyzes image and drafts description

**From the image, determine:**
1. Item type and category
2. Estimated era/date
3. Maker if identifiable
4. Condition assessment
5. Suggested price (use pricing tiers below)

**Pricing tiers:**
| Tier | Price Range | Margin Target |
|------|-------------|---------------|
| Quick flip | $1-15 | 2-3x cost |
| Mid-range | $15-75 | 2.5-4x cost |
| Showcase | $75+ | Research-based |

**Output from Phase 1:**
- Item title
- Description (HTML with `<br>` tags)
- Price in cents
- Condition grade
- SEO title and description

### Phase 2: Square Catalog Creation

**Use Square MCP to create the item:**

```
Square:make_api_request
  service: catalog
  method: batchUpsertCatalogObjects
  request: {
    "idempotency_key": "rg-XXXX-create-{timestamp}",
    "batches": [{
      "objects": [{
        "type": "ITEM",
        "id": "#RG-XXXX",
        "present_at_all_locations": false,
        "present_at_location_ids": ["B87BAEZ0NWV34"],
        "item_data": {
          "name": "{ITEM_TITLE}",
          "description": "{DESCRIPTION}",
          "categories": [
            {"id": "3N3II4W6Q7AA43RWQGEEWELY"},
            {"id": "P34KX3L7XRZJJ5RP6W35K4YO"}
          ],
          "reporting_category": {"id": "P34KX3L7XRZJJ5RP6W35K4YO"},
          "tax_ids": ["LPKEJF7H27NOPK7EE6A5CA7V"],
          "is_taxable": true,
          "ecom_visibility": "VISIBLE",
          "ecom_seo_data": {
            "page_title": "{SEO_TITLE}",
            "page_description": "{SEO_DESC}",
            "permalink": "{URL_SLUG}"
          },
          "variations": [{
            "type": "ITEM_VARIATION",
            "id": "#RG-XXXX-var",
            "item_variation_data": {
              "item_id": "#RG-XXXX",
              "name": "Regular",
              "sku": "RG-XXXX",
              "pricing_type": "FIXED_PRICING",
              "price_money": {"amount": {PRICE_CENTS}, "currency": "USD"},
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
- `id_mappings[0].object_id` → CATALOG_ITEM_ID
- `id_mappings[1].object_id` → VARIATION_ID

### Phase 3: Set Inventory

**Use Square MCP:**

```
Square:make_api_request
  service: inventory
  method: batchChangeInventory
  request: {
    "idempotency_key": "rg-XXXX-inv-{timestamp}",
    "changes": [{
      "type": "PHYSICAL_COUNT",
      "physical_count": {
        "catalog_object_id": "{VARIATION_ID}",
        "state": "IN_STOCK",
        "location_id": "B87BAEZ0NWV34",
        "quantity": "1",
        "occurred_at": "{ISO_TIMESTAMP}"
      }
    }]
  }
```

### Phase 4: Upload Image to Square

**Execute on user's machine:**

```bash
~/.pyenv/shims/python3 ~/skills/square-image-upload/scripts/upload_image.py \
  --image ~/items/RG-XXXX/RG-XXXX-hero.png \
  --item-id {CATALOG_ITEM_ID} \
  --name "RG-XXXX Hero" \
  --caption "{ITEM_TITLE}" \
  --primary
```

**Capture:** Image URL from response for info card.

### Phase 5: Payment Link

**Use Square MCP:**

```
Square:make_api_request
  service: checkout
  method: createPaymentLink
  request: {
    "idempotency_key": "rg-XXXX-pay-{timestamp}",
    "quick_pay": {
      "name": "{ITEM_TITLE}",
      "price_money": {"amount": {PRICE_CENTS}, "currency": "USD"},
      "location_id": "B87BAEZ0NWV34"
    },
    "checkout_options": {
      "ask_for_shipping_address": true
    }
  }
```

**Capture:** `payment_link.url` for info card and QR code.

### Phase 6: Generate Label

**Output CSV row for Print Master:**

```csv
"{ITEM_TITLE}","{ERA} • {TYPE} • {FEATURE}",{PRICE},{CONDITION},"{CONDITION_NOTES}",RG-XXXX,https://richmondgeneral.github.io/items/RG-XXXX/
```

**Append to batch file:**
```bash
echo '"{ITEM_TITLE}","{ATTRIBUTES}",{PRICE},{CONDITION},"{NOTES}",RG-XXXX,https://richmondgeneral.github.io/items/RG-XXXX/' >> ~/items/rg-labels-batch.csv
```

### Phase 7: Info Card (Optional)

**For items worth a story**, create GitHub Pages card:

```bash
# Clone/update items repo
cd ~/items-site
git pull origin main

# Create item folder
mkdir -p RG-XXXX
cp template/rg-item-card-template.html RG-XXXX/index.html

# Generate QR code
~/.pyenv/shims/python3 -c "
import qrcode
qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
qr.add_data('{PAYMENT_LINK_URL}')
img = qr.make_image(fill_color='#2C2C2C', back_color='#F5F1E8')
img.save('RG-XXXX/qr-code.png')
"

# Replace placeholders in index.html
sed -i '' 's/{{SKU}}/RG-XXXX/g' RG-XXXX/index.html
# ... (additional sed commands for all placeholders)

# Commit and push
git add RG-XXXX/
git commit -m "Add RG-XXXX: {ITEM_TITLE}"
git push origin main
```

**Skip Phase 7 for:** Quick-flip items, common items without story.

---

## Workflow Summary Output

After completing full workflow, provide summary:

```
✅ NEW ITEM ADDED: RG-XXXX

📦 Square Catalog
   Item ID: {CATALOG_ITEM_ID}
   Variation: {VARIATION_ID}
   Price: ${PRICE}
   Inventory: 1 in stock

🖼️ Image
   Hero: ~/items/RG-XXXX/RG-XXXX-hero.png
   Square URL: {IMAGE_URL}

💳 Payment Link
   {PAYMENT_LINK_URL}

🏷️ Label
   Added to ~/items/rg-labels-batch.csv

📄 Info Card
   https://richmondgeneral.github.io/items/RG-XXXX/

Next: Print label, place item on floor
```

---

## Local Configuration

**Token Storage (~/.zshrc or ~/.bashrc):**
```bash
export SQUARE_ACCESS_TOKEN="your_production_token_here"
export GEMINI_API_KEY="your_gemini_key"
export REMOVEBG_API_KEY="your_removebg_key"  # optional
```

**Working Directories:**
- `/Users/scottybe/items/` — Item images and working files
- `/Users/scottybe/items-site/` — GitHub Pages repo clone
- `/Users/scottybe/square-tools/` — Background removal and cache tools

### Required Categories (BOTH must be assigned)
| Category | ID | Purpose |
|----------|----|---------|
| Timeless Treasures | `3N3II4W6Q7AA43RWQGEEWELY` | Main vintage category |
| The New Finds | `P34KX3L7XRZJJ5RP6W35K4YO` | **REQUIRED** for all new items |

---

## Quick Tasks Reference

### Just a Label
```csv
"Item Title","Era • Type • Feature",29.99,Good,"Minor wear",RG-XXXX,
```

### Just a Price Check
Route to appropriate appraiser or provide pricing tier estimate.

### Just Upload an Image
```bash
~/.pyenv/shims/python3 ~/skills/square-image-upload/scripts/upload_image.py \
  --image /path/to/image.jpg \
  --item-id CATALOG_ITEM_ID \
  --primary
```

### Just Create Payment Link
Use Square MCP checkout.createPaymentLink with item details.

---

## Related Skills

- **square-cache**: MongoDB catalog cache (100x faster searches)
- **square-image-upload**: Multipart image uploads to Square
- **carnival-glass-appraiser**: Iridescent glass identification and valuation
- **maker-mark-identifier**: Pottery, silver, furniture mark identification
- **book-appraiser**: Antiquarian book research and valuation
- **product-labeler**: Label formatting and batch CSV

## Square API Services

- `catalog`: batchUpsertCatalogObjects, searchCatalogItems
- `inventory`: batchChangeInventory
- `checkout`: createPaymentLink
- `orders`: View payment link orders

## References

- `references/square-catalog.md` — API details and category IDs
- `references/lot-tracking.md` — Lot management
- `references/pricing-guidelines.md` — Margin targets
