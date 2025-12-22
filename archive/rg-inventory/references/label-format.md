# Label Format for Richmond General

## Print Master CSV Format

Labels are generated as CSV files for batch import into Print Master thermal label software.

### Standard Label Fields

| Column | Description | Example |
|--------|-------------|---------|
| Product Name | Full item title | Kings of the Forest & Kindred Tribes - W.A. Foster |
| Attributes | Era • Type • Features (bullet-separated) | Antique Book • 1892 • 235 Engravings |
| Price | Price with decimal (no $) | 34.95 |
| Condition | Grade (VG, Good, Fair, etc.) | Fair |
| Condition Notes | Brief description of condition | Cover worn, spine frayed, pages intact |
| SKU | RG-XXXX format | RG-0002 |
| QR Code URL | Info card URL for items with story (optional) | https://richmondgeneral.github.io/items/RG-0002/ |

### CSV Header Row

```csv
Product Name,Attributes,Price,Condition,Condition Notes,SKU,QR Code URL
```

### Example Row

```csv
"Kings of the Forest & Kindred Tribes - W.A. Foster","Antique Book • 1892 • 235 Engravings",34.95,Fair,"Cover worn, spine frayed, pages intact",RG-0002,https://richmondgeneral.github.io/items/RG-0002/
```

## Label Layouts (both 2" × 1")

### Default Layout - All items
```
┌─────────────────────────────────────┐
│ Product Name                        │
│ Attributes • Line • Here            │
│ $55.00              Condition       │
│ Condition notes here       RG-0003  │
└─────────────────────────────────────┘
```
Fields: Product Name, Attributes, Price, Condition, Condition Notes, SKU

### QR Layout - Interesting items with info cards
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
- QR links to info card URL (not payment link)

## QR Code Decision

**Include QR code when:**
- Antiques (pre-1950)
- Collectibles with story/provenance
- Items with info cards on GitHub Pages
- Anything worth telling a story about

**Omit QR code when:**
- Basic/common items
- Quick-flip low-value items without unique story

**QR links to info card** (not payment link directly) - customer scans → reads story → clicks Buy Now

## Workflow Order (Critical!)

```
Phase 3: Square Catalog → Get SKU assigned
                ↓
Phase 5: Payment Link → Get square.link URL
                ↓
Phase 6: Create Label → Now have both SKU and QR URL
                ↓
Add to Batch CSV → Accumulate labels
                ↓
End of Session → Batch print all labels
```

**Important:** Labels cannot be fully created until AFTER payment link exists, because the QR code URL comes from the payment link.

## Batch File Locations

- CSV: `/Users/scottybe/Workspace/items/rg-labels-batch.csv`
- Excel: `/Users/scottybe/Workspace/items/rg-labels-batch.xlsx`

## Style Guide

### Attributes Format
Use bullet separator (•) between attributes:
- `Era • Type • Feature`
- `Material • Style • Decade`
- `Maker • Pattern • Color`

### Condition Abbreviations
| Full | Abbreviation |
|------|--------------|
| Mint | Mint |
| Like New | Like New |
| Excellent | Exc |
| Very Good | VG |
| Good | Good |
| Fair | Fair |
| Poor | Poor |

### Price Format
- Always end in .95: `19.95` not `20` (pennies being eliminated)
- No dollar sign in CSV (added by template)
- No commas in numbers

## Print Master Settings

- Label size: 2" × 1" (both layouts)
- Font: Arial or Helvetica
- Product Name: 10pt bold (QR layout: truncate to ~20 chars)
- Attributes: 8pt regular
- Price: 14pt bold
- Condition: 8pt regular
- SKU: 7pt regular
- QR code size: 0.5" × 0.5" (right side of label)
