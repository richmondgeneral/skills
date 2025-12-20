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

## Local Configuration (User's Machine)

**Token Storage (~/.zshrc or ~/.bashrc):**
```bash
# Square Production Token - Richmond General
export SQUARE_ACCESS_TOKEN="your_production_token_here"
```

**Working Directory:** `/Users/scottybe/items/`
- Product images
- Upload scripts
- Converted files

### Required Categories (BOTH must be assigned to every item)
| Category | ID | Purpose |
|----------|----|---------|
| Timeless Treasures | `3N3II4W6Q7AA43RWQGEEWELY` | Main vintage category |
| The New Finds | `P34KX3L7XRZJJ5RP6W35K4YO` | **REQUIRED** for all new items |

**Reporting Category:** Set to `The New Finds` for sales reporting

## 7-Phase Workflow

### Phase 1: Appraisal & Research

**Route to domain appraiser when applicable:**
- Books pre-1970 or antiquarian → Load `book-appraiser` skill
- Carnival glass (iridescent pressed glass, marigold, amethyst, Northwood, Fenton) → Load `carnival-glass-appraiser` skill
- Other maker's marks (pottery, silver, furniture) → Load `maker-mark-identifier` skill (returns ID only; continue Phase 1 for valuation)
- General vintage items → Continue with this workflow

**When using a domain appraiser:**
- Appraiser handles full research cycle: identification → authentication → condition → valuation
- Resume workflow at Phase 2 (Photography) using appraiser's output
- Skip research checklist below (appraiser covers it)

**Research checklist (general items only):**
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

### Phase 2b: Image Upload to Square

**Use the `square-image-upload` skill** for image uploads (Square MCP doesn't support multipart form data).

**Upload hero image:**
```bash
~/.pyenv/shims/python3 ~/skills/square-image-upload/scripts/upload_image.py \
  --image RG-XXXX-hero.jpg \
  --item-id CATALOG_ITEM_ID \
  --name "Item Title - Hero" \
  --caption "Front view description" \
  --primary
```

**Upload additional images:**
```bash
~/.pyenv/shims/python3 ~/skills/square-image-upload/scripts/upload_image.py \
  --image RG-XXXX-detail.jpg \
  --item-id CATALOG_ITEM_ID \
  --name "Item Title - Detail"
```

**Prerequisites:**
- Python 3.7+ with requests: `pip install requests`
- Token set: `export SQUARE_ACCESS_TOKEN=your_token` (in ~/.zshrc)

**Image Format Requirements:**
- Square accepts: JPEG, PNG, GIF, TIFF, BMP, HEIC (max 10MB)
- **⚠️ WebP not supported** - reconvert if needed: `sips -s format jpeg file.webp --out file.jpg`

**Production Catalog Item IDs** (use `catalog.searchItems` to get current IDs):
| SKU | Item ID | Description |
|-----|---------|-------------|
| RG-0001 | `2A2VL6JA6VHOQLRLERFR5BZJ` | Little Orphan Annie |
| RG-0002 | `DLWJY2P7Q24CAY6YGAUY5JKP` | Kings of the Forest |
| RG-0003 | `QEQWAA7YTTH3T2OBFJLD2OCL` | Bar Stool |
| RG-0004 | `K4N6V6AXMDYNUNSJ2TWOYJGG` | Chase Japan Plaques |
| RG-0005 | `A55Q4TG7EJ2IJUDIFX3VHVAH` | Bears Button |
| RG-0006 | `6LNKQICZM3TAVJG3TAF4O4YB` | Disney Comics Cover |

**See `square-image-upload` skill for:** full options, replacing existing images, troubleshooting.

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
      "ecom_seo_data": {
        "page_title": "[Era] [Item Type] - [Key Feature] | Richmond General",
        "page_description": "Concise description with keywords. Include era, maker, condition. End with location for local SEO.",
        "permalink": "descriptive-url-slug-with-keywords"
      },
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
          "track_inventory": true,
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

### Phase 3b: Set Inventory Count

After creating the catalog item, set the initial stock count to 1:

**API Endpoint:** `inventory.batchChange`

```json
{
  "idempotency_key": "unique-uuid",
  "changes": [{
    "type": "PHYSICAL_COUNT",
    "physical_count": {
      "catalog_object_id": "VARIATION_ID_FROM_STEP_3",
      "state": "IN_STOCK",
      "location_id": "B87BAEZ0NWV34",
      "quantity": "1",
      "occurred_at": "2025-01-01T12:00:00Z"
    }
  }]
}
```

**⚠️ NOTE:** Do NOT include `catalog_object_type` in the request - Square sets this automatically.

**Why this matters:** Without setting inventory count, items show as "sold out" in Square Online even with `track_inventory: true`.

**SEO Fields (in ecom_seo_data):**
- `page_title`: `[Era] [Item Type] - [Key Feature] | Richmond General` (max ~60 chars)
- `page_description`: Concise, keyword-rich description ending with "Richmond, IL" for local SEO (max ~160 chars)
- `permalink`: lowercase-hyphenated-descriptive-slug

**Example:**
```json
"ecom_seo_data": {
  "page_title": "1930s Little Orphan Annie Comic Collection | Richmond General",
  "page_description": "Vintage Harold Gray Little Orphan Annie comic strip collection from the Depression era. Very good condition. Richmond, IL.",
  "permalink": "1930s-little-orphan-annie-comic-collection"
}
```

### Phase 4: Fulfillment Setup

**Use judgment** - don't apply rigid rules. Price is NOT a factor; a $200 book ships just as easily as a $5 one.

**Ships easily:**
- Books, paper goods, small collectibles
- Items that fit in a standard box without complex packing
- Sturdy items that won't break in transit
- Most things a reasonable person would drop at the post office

**Pickup/local delivery only:**
- Furniture (chairs, tables, cabinets - size and weight make shipping impractical)
- Large or awkward shapes that don't box well
- Extremely fragile items where shipping risk outweighs convenience
- Heavy items where shipping cost approaches or exceeds item value

**Flat rate box reference** (when shipping applies):
- Small (8⅝" × 5⅜" × 1⅝") → $10.20
- Medium (11" × 8½" × 5½") → $17.10  
- Large (12" × 12" × 5½") → $21.90

**Square Dashboard steps** (manual - for shippable items):
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

### Phase 6: Labels & Batch CSV

**Workflow order matters:** Labels need SKU (from Phase 3) AND payment link (from Phase 5) before they can be complete.

#### Print Master CSV Format

**Batch file:** `/Users/scottybe/items/rg-labels-batch.csv`

| Column | Description | Example |
|--------|-------------|--------|
| Product Name | Full item title | Kings of the Forest - W.A. Foster |
| Attributes | Era • Type • Features (bullet-separated) | Antique Book • 1892 • 235 Engravings |
| Price | Decimal, no $ | 34.99 |
| Condition | Grade | Fair |
| Condition Notes | Brief description | Cover worn, pages intact |
| SKU | RG-XXXX | RG-0002 |
| QR Code URL | Info card URL (for items with story) | https://richmondgeneral.github.io/items/RG-0002/ |

**CSV Header:**
```csv
Product Name,Attributes,Price,Condition,Condition Notes,SKU,QR Code URL
```

**Example Row:**
```csv
"Pressed-Back Oak Swivel Bar Stool","Early 1900s • American Oak • Victorian",55.00,Good,"Some wear to seat, finish stable",RG-0003,https://richmondgeneral.github.io/items/RG-0003/
```

#### Label Layouts (both 2" × 1")

**Default Layout** - All items:
```
┌─────────────────────────────────────┐
│ Product Name                        │
│ Attributes • Line • Here            │
│ $55.00              Condition       │
│ Condition notes here       RG-0003  │
└─────────────────────────────────────┘
```

**QR Layout** - Interesting items with info cards:
```
┌─────────────────────────────────────┐
│ Short Product Name        ┌─────┐  │
│ Attributes • Here         │ QR  │  │
│ $55.00        Condition   │     │  │
│                  RG-0003  └─────┘  │
└─────────────────────────────────────┘
```
- Drops: Condition Notes
- Shortens: Product Name (truncate to ~20 chars)
- QR links to info card URL

#### QR Code Decision

**Include QR when:**
- Antiques (pre-1950)
- Collectibles with story/provenance
- Items with info cards on GitHub Pages
- Anything worth telling a story about

**Skip QR when:**
- Basic/common items
- Quick-flip low-value items without unique story

**QR links to info card** (not payment link directly) - customer scans → reads story → clicks Buy Now

#### Attributes Format

Use bullet separator (•) between attributes:
- `Era • Type • Feature`
- `Material • Style • Decade`
- `Maker • Pattern • Color`

#### Condition Abbreviations

| Full | Abbrev |
|------|--------|
| Mint | Mint |
| Like New | Like New |
| Excellent | Exc |
| Very Good | VG |
| Good | Good |
| Fair | Fair |
| Poor | Poor |

See `references/label-format.md` for Print Master settings and full style guide.

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
- **square-image-upload**: Upload product images to Square Catalog (multipart form data)
- **carnival-glass-appraiser**: Complete appraisal for iridescent pressed glass (pattern ID, manufacturer attribution, authentication, valuation)
- **maker-mark-identifier**: Identify pottery, silver, furniture marks (defers valuation to Phase 1)
- **book-appraiser**: Antiquarian books, LOC cross-reference, edition identification
- **product-labeler**: Thermal label generation, Square catalog descriptions

### Square API Services
- `catalog`: Create/update items (batchInsertObjects, batchUpdateObjects)
- `checkout`: Generate payment links (createPaymentLink)
- `inventory`: **REQUIRED** - Set stock count after catalog creation (batchChange)
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
