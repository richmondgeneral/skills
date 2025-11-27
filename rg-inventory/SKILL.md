---
name: rg-inventory
description: Richmond General inventory management system. Use when processing items for the store, creating Square catalog entries, pricing vintage/antique items, generating labels, or tracking purchase lots and provenance. Triggers on inventory, pricing, labeling, Square catalog, or Richmond General store tasks.
---

# Richmond General Inventory System

Complete workflow for processing vintage and antique items from acquisition through sale.

## Quick Reference

**Square Location:** B87BAEZ0NWV34 (Richmond General - ACTIVE)
**Merchant ID:** 7MM9AFJAD0XHW
**SKU Prefix:** RG-XXXX (sequential)
**GitHub Pages:** https://richmondgeneral.github.io/items/
**Repository:** github.com/richmondgeneral/items

### Required Categories (BOTH must be assigned to every item)
| Category | ID | Purpose |
|----------|----|---------|
| Timeless Treasures | `3N3II4W6Q7AA43RWQGEEWELY` | Main vintage category |
| The New Finds | `P34KX3L7XRZJJ5RP6W35K4YO` | **REQUIRED** for all new items |

**Reporting Category:** Set to `The New Finds` for sales reporting

## 7-Phase Workflow

### Phase 1: Appraisal & Research

**Route to appropriate skill:**
- Books pre-1970 or antiquarian → Load `book-appraiser` skill
- Maker's marks, pottery, glass, silver → Load `vintage-appraiser` skill
- General vintage items → Continue with this workflow

**Research checklist:**
1. Identify maker/manufacturer
2. Date the piece (era, production dates)
3. Assess condition
4. Research comparable sales (eBay sold, auction records)
5. Determine price point

**Pricing tiers:**
| Tier | Price Range | Margin Target |
|------|-------------|---------------|
| Quick flip | $1-15 | 2-3x cost |
| Mid-range | $15-75 | 2.5-4x cost |
| Showcase | $75+ | Research-based |

### Phase 2: Photography & Images

**Required shots:**
1. Hero image (front, clean background)
2. Back/bottom (marks, labels)
3. Detail shots (condition issues, unique features)
4. Scale reference if size matters

**Image processing:**
- Remove background for hero shot (transparent PNG preferred)
- Consistent lighting
- Minimum 1000px on longest edge

**File naming:** `RG-XXXX-01.png`, `RG-XXXX-02.png`, etc.

### Phase 3: Square Catalog Creation

**API Endpoint:** `catalog.batchInsertObjects` (use `batchUpdateObjects` with `sparse_update: true` for updates)

**Required fields:**
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
        {"id": "3N3II4W6Q7AA43RWQGEEWELY"},
        {"id": "P34KX3L7XRZJJ5RP6W35K4YO"}
      ],
      "reporting_category": {"id": "P34KX3L7XRZJJ5RP6W35K4YO"},
      "tax_ids": ["LPKEJF7H27NOPK7EE6A5CA7V"],
      "is_taxable": true,
      "ecom_visibility": "VISIBLE",
      "variations": [{
        "type": "ITEM_VARIATION",
        "id": "#RG-XXXX-var",
        "item_variation_data": {
          "item_id": "#RG-XXXX",
          "name": "Regular",
          "sku": "RG-XXXX",
          "pricing_type": "FIXED_PRICING",
          "price_money": {
            "amount": 1999,
            "currency": "USD"
          },
          "track_inventory": false,
          "sellable": true,
          "stockable": true
        }
      }]
    }
  }
}
```

**⚠️ CRITICAL:** Both categories AND reporting_category are REQUIRED for proper sales tracking and online visibility.

**SEO Title Formula:**
`[Era] [Maker] [Item Type] - [Key Feature] | [Condition]`

Example: `1930s Harold Gray Little Orphan Annie - Dover Reprint | Very Good`

### Phase 4: Fulfillment Setup

**Shipping decision tree:**
```
Is item fragile OR >5 lbs OR >$100?
├─ YES → Pickup only OR custom shipping quote
└─ NO → Standard shipping enabled
    └─ Fits in flat rate box?
        ├─ Small (8⅝" × 5⅜" × 1⅝") → $10.20
        ├─ Medium (11" × 8½" × 5½") → $17.10
        └─ Large (12" × 12" × 5½") → $21.90
```

**Square Dashboard steps** (manual):
1. Open catalog item
2. Enable "Available for shipping"
3. Set weight and dimensions
4. Assign shipping profile

### Phase 5: Payment Link Generation

**API Endpoint:** `checkout.createPaymentLink`

```json
{
  "idempotency_key": "unique-uuid",
  "quick_pay": {
    "name": "Item Title",
    "price_money": {
      "amount": 1999,
      "currency": "USD"
    },
    "location_id": "B87BAEZ0NWV34"
  },
  "checkout_options": {
    "ask_for_shipping_address": true
  }
}
```

**Response contains:**
- `payment_link.url` → Long checkout URL
- `payment_link.long_url` → Same
- `related_resources.orders[0].id` → Order ID

**Short link format:** `https://square.link/u/XXXXXXXX`

### Phase 6: Label & File Organization

**Label specs (thermal printer):**
- Size: 2" × 1" (standard price label)
- Fields: Item name, Price, SKU
- QR code: Payment link (NOT product URL)

**Use product-labeler skill** for generating labels.

**File organization:**
```
items-site/
├── RG-XXXX/
│   ├── index.html      ← Info card page
│   ├── qr-code.png     ← Payment link QR
│   ├── qr-code.svg     ← Vector version
│   └── images/         ← Product photos (optional)
```

### Phase 7: Info Card & Publishing

**GitHub Pages site:** https://richmondgeneral.github.io/items/

**Workflow:**
1. Copy template: `template/rg-item-card-template.html` → `RG-XXXX/index.html`
2. Replace placeholders (see below)
3. Generate QR code for payment link
4. Add to gallery grid in `index.html`
5. Commit and push to `main` branch

**Template placeholders:**
| Placeholder | Description |
|-------------|-------------|
| `{{SKU}}` | Item SKU (RG-XXXX) |
| `{{ITEM_TITLE}}` | Full item title |
| `{{ERA_LINE}}` | Era description |
| `{{PRICE}}` | Price (no $ symbol) |
| `{{STORY_TEXT}}` | History/provenance |
| `{{ERA}}` | Era for details grid |
| `{{CONDITION}}` | Condition grade |
| `{{MAKER}}` | Maker/manufacturer |
| `{{ORIGIN}}` | Origin/location |
| `{{IMAGE_URL}}` | Hero image path |
| `{{QR_CODE_URL}}` | QR code image path |
| `{{PAYMENT_LINK_URL}}` | Square payment link |
| `{{SEO_DESCRIPTION}}` | Meta description |

**QR Code generation (Python):**
```python
import qrcode
from qrcode.image.styledpil import StyledPilImage

qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
qr.add_data("https://square.link/u/XXXXXXXX")
img = qr.make_image(fill_color="#2C2C2C", back_color="#F5F1E8")
img.save("qr-code.png")
```

**Brand colors:**
- Gold: #C9A961
- Cream: #F5F1E8
- Charcoal: #2C2C2C
- Brown: #6B4423

## Customer Flow

```
Physical Store → QR on label/card
                      ↓
         richmondgeneral.github.io/items/RG-XXXX/
                      ↓
              Read story, flip card
                      ↓
              Click "Buy Now" button
                      ↓
         square.link/u/XXXXXXXX (checkout)
                      ↓
              Square processes payment
```

## Integration Points

### Related Skills
- **vintage-appraiser**: Maker's mark identification, carnival glass, pricing research
- **book-appraiser**: Antiquarian books, LOC cross-reference, edition identification
- **product-labeler**: Thermal label generation, Square catalog descriptions

### Square API Services
- `catalog`: Create/update items
- `checkout`: Generate payment links
- `inventory`: Track stock (if enabled)
- `orders`: View payment link orders

### External Resources
- **GitHub Pages**: Info cards and gallery
- **Square Dashboard**: Fulfillment config, shipping profiles
- **Print Master**: Batch label printing (CSV import)

## Lot Tracking

For estate/auction purchases, track provenance:

**Lot prefix format:** `L##-` prepended to notes

**Tracking fields:**
- Lot ID (e.g., L2 = Peter's Estate)
- Purchase date
- Total lot cost
- Item allocation (for margin calculation)

## References

- `references/square-catalog.md` - API details and category IDs
- `references/lot-tracking.md` - Lot management and allocation
- `references/pricing-guidelines.md` - Margin targets by category
