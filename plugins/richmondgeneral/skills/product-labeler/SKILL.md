---
name: product-labeler
description: Generate product labels for Richmond General Square inventory. Use when creating thermal printer labels (CSV for Print Master batch import), Square catalog descriptions, or price tags. Handles imported Asian snacks, vintage items, and wellness products. Supports batch label generation, style guide compliance, and measurement conversions.
metadata:
  version: "1.2"
  author: scottybe
  updated: "2026-07-15"
  changelog: |
    v1.2 - RG-era alignment: two-QR price tags (qr-info.png), RG-XXXX SKUs first-class,
    Mac-native output path (the /mnt/user-data path was Cowork-container-only).

    v1.1 - Anthropic skills update:
    - Added author and updated fields
---

# Product Labeler for Richmond General Square

Generate professional product labels for thermal printing and Square catalog listings.

> **RG-era updates (2026-07):** unique RG items use **RG-XXXX** SKUs (minted by the Square
> CAS authority — never invent one here); the legacy SNACK-/COOKIE-/VINT- prefixes below apply
> to consumable/snack restock only. **Price tags for RG items carry the `qr-info.png` QR**
> (→ the GitHub item page; already generated in the item dir by intake/rg-full-auto Phase 7 —
> reference it, don't regenerate). The buy QR (`qr-buy.png`) belongs on the item card, not the
> price tag.

## Workflow Overview

1. **Determine label type**: Thermal printer CSV, Square description, or price tag
2. **Identify product category**: Imported snacks, vintage items, or wellness products
3. **Gather product details**: Name, size, price, origin, description
4. **Generate output**: Format according to target (CSV for Print Master, HTML for Square)

## Label Types

### Interactive Label Cards (Default for Review)
When generating labels for review or manual entry, create a React artifact using the template in `assets/label-card-template.jsx`. Each label displays as a card with **copy buttons** for each field, making it easy to grab text for Square listings or other uses.

**Always use interactive cards when:**
- User needs to copy text into Square catalog
- Reviewing/proofing labels before printing
- Creating descriptions for individual products
- User asks for "labels with copy buttons"

### Thermal Printer Labels (CSV for Print Master)
Output CSV file when user specifically needs batch printing. Print Master supports up to 100 rows per batch.

**Standard price label CSV format:**
```csv
Product Name,Price,SKU
Lay's Korean Honey Mustard 1.2oz,4.99,SNACK-LKH-34
```

**Detailed label CSV format:**
```csv
Product Name,Price,Size,Origin,SKU
Lay's Korean Honey Mustard 1.2oz (34g),4.99,1.2oz,Taiwan Import,SNACK-LKH-34
```

### Square Catalog Descriptions
Use HTML formatting with `<br>` tags for spacing. See `references/style-guide.md` for full guidelines.

**Quick reference - Product name format:**
`[Brand] [Flavor] [Imperial Size] ([Metric Size]) - [Country] Import`

**Quick reference - Common conversions:**
- 34g = 1.2oz | 40g = 1.4oz | 48g = 1.7oz | 80g = 2.8oz | 100g = 3.5oz
- 500ml = 16.9 fl oz | 350ml = 11.8 fl oz

## Product Categories

### Imported Snacks & Beverages
- Lead with imperial measurements (oz, fl oz)
- Include cultural context explaining why flavor exists
- Highlight texture/ingredient differences from US versions
- Emphasize exclusivity ("Never released in the US")
- For Chinese products: Note production date display convention

### Vintage Items
- Use lot-based SKU prefixes (e.g., L2- for Peter's Estate Lot)
- Include authentication notes when applicable
- Note condition grade if relevant
- Research market values before pricing

### Wellness Products (Sage, Crystals, etc.)
- Include intended use/benefit
- Note bundle contents if applicable
- Use descriptive variation names

## Interactive Label Cards Workflow

When creating labels for Square catalog entry or review:

1. Use the React template in `assets/label-card-template.jsx`
2. Replace the `PRODUCTS` array with actual product data
3. Each card displays:
   - Product name with copy button
   - Price, SKU, Size, Origin (each with individual copy buttons)
   - Full HTML description with toggle between preview/HTML view
   - "Copy Description" button for the full HTML
4. "Copy All as CSV" button at top for quick export

**Product object structure:**
```javascript
{
  id: 1,
  name: "Product Name 1.2oz (34g) - Country Import",
  price: "4.99",
  sku: "SNACK-XXX-34",
  size: "1.2oz (34g)",
  origin: "Country Import",
  description: "<p>HTML description...</p>"
}
```

## Batch Label Generation

To generate CSV for batch printing:

1. Collect product list with all required fields
2. Generate CSV with headers in row 1
3. Keep to 100 rows max per file (Print Master limit)
4. Save as UTF-8 encoded CSV
5. Output next to the item (`items/RG-XXXX/`) or a workspace `labels/` dir on the Mac (`/mnt/user-data/outputs/` is Cowork-container-only — invalid on the Mac)

**Example batch output:**
```csv
Product Name,Price,Size,Origin,SKU
Lay's Korean Honey Mustard 1.2oz (34g),4.99,1.2oz,Taiwan,SNACK-LKH-34
Doritos Garlic Steak 1.4oz (40g),4.99,1.4oz,Taiwan,SNACK-DGS-40
Fanta White Peach 16.9 fl oz (500ml),3.99,16.9 fl oz,China,BEV-FWP-500
```

## Style Guide Reference

For detailed formatting rules, read `references/style-guide.md`. Key principles:
- Customer-facing language only (no wholesale terms)
- Imperial units first, metric in parentheses
- Speak directly to customer using "you"
- Be educational about international products
- Emphasize discovery and exclusivity

## SKU Conventions

**Format:** `[CATEGORY]-[PRODUCT CODE]-[SIZE/VARIANT]`

Categories:
- `SNACK` - Chips, crackers, savory snacks
- `COOKIE` - Cookies and sweet baked goods  
- `CANDY` - Candy and confections
- `BEV` - Beverages
- `SAGE` - Sage bundles
- `VINT` - Vintage items
- `WELL` - Wellness products

Lot prefixes for estate purchases: `L1-`, `L2-`, etc.
