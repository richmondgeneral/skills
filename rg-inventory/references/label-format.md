# Label Format for Richmond General

## Print Master CSV Format

Labels are generated as CSV files for batch import into Print Master thermal label software.

### Standard Label Fields

| Column | Description | Example |
|--------|-------------|---------|
| Product Name | Full item title | Kings of the Forest & Kindred Tribes - W.A. Foster |
| Attributes | Era • Type • Features (bullet-separated) | Antique Book • 1892 • 235 Engravings |
| Price | Price with decimal (no $) | 34.99 |
| Condition | Grade (VG, Good, Fair, etc.) | Fair |
| Condition Notes | Brief description of condition | Cover worn, spine frayed, pages intact |
| SKU | RG-XXXX format | RG-0002 |
| QR Code URL | Payment link for "interesting" items (optional) | https://square.link/u/aug0H4mL |

### CSV Header Row

```csv
Product Name,Attributes,Price,Condition,Condition Notes,SKU,QR Code URL
```

### Example Row

```csv
"Kings of the Forest & Kindred Tribes - W.A. Foster","Antique Book • 1892 • 235 Engravings",34.99,Fair,"Cover worn, spine frayed, pages intact",RG-0002,https://square.link/u/aug0H4mL
```

## Label Types

### Standard Price Tag (2" × 1")
- Product Name (truncated if needed)
- Price (large, left-aligned)
- SKU (small, right-aligned)
- No QR code

### Interesting Item Tag (2" × 2" or larger)
- Full product name
- Attributes line
- Price
- Condition + notes
- SKU
- QR code linking to payment

## QR Code Decision

**Include QR code when:**
- Antiques (pre-1950)
- Collectibles with story/provenance
- Higher-value items ($25+)
- Items with info cards on GitHub Pages

**Omit QR code when:**
- Basic/common items
- Quick-flip low-value items
- Items without unique story

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

- CSV: `/Users/scottybe/items/rg-labels-batch.csv`
- Excel: `/Users/scottybe/items/rg-labels-batch.xlsx`

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
- Always include cents: `19.99` not `20`
- No dollar sign in CSV (added by template)
- No commas in numbers

## Print Master Settings

- Label size: 2" × 1" (standard) or 2" × 2" (with QR)
- Font: Arial or Helvetica
- Price font size: 24pt bold
- SKU font size: 8pt
- QR code size: 0.75" × 0.75"
