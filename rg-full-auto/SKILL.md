---
name: rg-full-auto
description: End-to-end 7-phase workflow for onboarding NEW items to Richmond General from acquisition through sale. Covers appraisal, lot/acquisition cost tracking, photography, Square catalog creation, fulfillment, payment links, labels, and info card publishing. Use when processing a new acquisition from scratch or doing a complete item redo. Triggers on "new item", "full workflow", "onboard", "process acquisition", "add to inventory". NOT for simple edits to existing items—use rg-item-update for price changes, description tweaks, or adding images.
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
| Working Directory | `/Users/scottybe/items/` |

### Category Assignment (choose ONE)

| Category | ID | Use For |
|----------|----|---------|
| The Real Rarities | `FL4L42RRUE5UXMWFDLXOCNB5` | Rare, special, showcase-worthy pieces |
| The New Finds | `P34KX3L7XRZJJ5RP6W35K4YO` | Regular new inventory arrivals |

**Decision:** Is this genuinely rare/special → The Real Rarities. Standard new stock → The New Finds.

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

### Image Upload (MCP Limitation)

Square MCP doesn't support multipart uploads. Generate curl commands for user to run locally where `SQUARE_ACCESS_TOKEN` is stored in `~/.zshrc`.

**⚠️ WebP not supported** - reconvert if needed:
```bash
sips -s format jpeg RG-XXXX-hero.jpeg --out RG-XXXX-hero-converted.jpeg
```

**Curl template:**
```bash
curl -X POST "https://connect.squareup.com/v2/catalog/images" \
  -H "Authorization: Bearer $SQUARE_ACCESS_TOKEN" \
  -H "Accept: application/json" \
  -F "request={
    \"idempotency_key\": \"rg-XXXX-hero-$(date +%s)\",
    \"image\": {
      \"type\": \"IMAGE\",
      \"id\": \"#temp-rg-XXXX\",
      \"image_data\": {
        \"name\": \"Item Title - Hero\",
        \"caption\": \"Front view\"
      }
    },
    \"object_id\": \"CATALOG_ITEM_ID\"
  };type=application/json" \
  -F "image_file=@RG-XXXX-hero.jpeg;type=image/jpeg"
```

## Phase 3: Square Catalog Creation

**Endpoint:** `catalog.batchInsertObjects`

```json
{
  "idempotency_key": "unique-uuid",
  "object": {
    "type": "ITEM",
    "id": "#RG-XXXX",
    "present_at_all_locations": false,
    "present_at_location_ids": ["B87BAEZ0NWV34"],
    "item_data": {
      "name": "Item Title",
      "description": "HTML description with <br> tags",
      "categories": [
        {"id": "CHOSEN_CATEGORY_ID"}
      ],
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
  }
}
```

### Set Inventory Count (Required)

**Endpoint:** `inventory.batchChange`

```json
{
  "idempotency_key": "unique-uuid",
  "changes": [{
    "type": "PHYSICAL_COUNT",
    "physical_count": {
      "catalog_object_id": "VARIATION_ID",
      "state": "IN_STOCK",
      "location_id": "B87BAEZ0NWV34",
      "quantity": "1",
      "occurred_at": "2025-01-01T12:00:00Z"
    }
  }]
}
```

Without this, items show "sold out" online.

See `references/square-catalog.md` for API details.

## Phase 4: Fulfillment Setup

**Use judgment** - price is NOT a factor.

**Ships easily:** Books, paper goods, small collectibles, sturdy items

**Pickup only:** Furniture, large/awkward shapes, extremely fragile, heavy items where shipping ≈ item value

**Flat rate reference:** Small $10.20 | Medium $17.10 | Large $21.90

Configure in Square Dashboard: enable shipping, set weight/dimensions, assign profile.

## Phase 5: Payment Link Generation

**Endpoint:** `checkout.createPaymentLink`

```json
{
  "idempotency_key": "unique-uuid",
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

**Dependency:** Needs SKU (Phase 3) + payment link (Phase 5)

**Batch file:** `/Users/scottybe/items/rg-labels-batch.csv`

```csv
Product Name,Attributes,Price,Condition,Condition Notes,SKU,QR Code URL
"Item Title","Era • Type • Feature",55.00,Good,"Wear notes",RG-0003,https://richmondgeneral.github.io/items/RG-0003/
```

**Layouts (2" × 1"):**
- Default: Full info, no QR
- QR Layout: Shortened name, drops condition notes, adds QR linking to info card

**Include QR when:** Antiques (pre-1950), collectibles with story, items with info cards

See `references/label-format.md` for Print Master settings.

## Phase 7: Info Card & Publishing

**Site:** https://richmondgeneral.github.io/items/

1. Copy `template/rg-item-card-template.html` → `RG-XXXX/index.html`
2. Replace placeholders: `{{SKU}}`, `{{ITEM_TITLE}}`, `{{PRICE}}`, `{{STORY_TEXT}}`, etc.
3. Generate QR for payment link (brand colors: Gold #C9A961, Cream #F5F1E8, Charcoal #2C2C2C)
4. Add to gallery grid in `index.html`
5. Commit and push to `main`

**Customer flow:** QR on label → Info card → Read story → Buy Now → Square checkout

## Related Skills

| Skill | Use For |
|-------|---------|
| `rg-item-update` | Quick edits to existing items |
| `book-appraiser` | Antiquarian books, LOC cross-reference |
| `carnival-glass-appraiser` | Pressed iridescent glass 1908-1930s |
| `maker-mark-identifier` | Pottery, silver, furniture marks |
| `product-labeler` | Label generation, Square descriptions |
| `square-image-upload` | Image upload via API |

## References

- `references/square-catalog.md` - API details, category IDs
- `references/lot-tracking.md` - Lot management, cost allocation
- `references/pricing-guidelines.md` - Margin targets by category
- `references/label-format.md` - Print Master settings, style guide
