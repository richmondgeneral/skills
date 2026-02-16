# Lot File Template

Use this template when creating a new lot tracking file. Copy the markdown below
and fill in the bracketed fields.

---

```markdown
# Lot: {LOT_ID}

## Acquisition Details

- **Source:** {description — who/where, e.g., "Peter's estate, 2nd visit"}
- **Date:** {YYYY-MM-DD}
- **Total Cost:** ${amount}
- **Items:** {count} (estimated)
- **Allocation Method:** {equal | value-weighted | category-based | manual}
- **Notes:** {any relevant context — negotiation details, condition of lot, etc.}

## Items

| SKU | Item | Allocated Cost | List Price | Sale Price | Channel | Status |
|-----|------|----------------|------------|------------|---------|--------|
| | | | | | | |

### Status values
- **Pending** — identified but not yet listed
- **Listed** — live on Square with payment link
- **Sold** — sold, include date (e.g., "Sold 2026-02-14")
- **Write-off** — unsellable, damaged, or donated

## Running Totals

- **Items Identified:** 0
- **Items Listed:** 0
- **Items Sold:** 0
- **Total Listed Value:** $0.00
- **Total Sold:** $0.00
- **Total Fees:** $0.00
- **Net P/L:** -${total_cost}
- **ROI:** -100%
- **Break-even:** Need ${total_cost} in net sales
```

---

## Field notes

- **Allocated Cost**: Calculated per the allocation method. For equal split,
  it's `total_cost / item_count`. Update if item count changes.
- **List Price**: The asking price on Square. Should pass margin validation
  (see SKILL.md Phase 2).
- **Sale Price**: What the buyer actually paid. May differ from list price
  if discounted.
- **Channel**: Where the sale happened — `Square`, `Whatnot`, `Local`, or `Other`.
  Determines fee calculation (see `roi-formulas.md`). Leave blank until sold.
- **Running Totals**: Recalculate after every sale or new listing.
  See `roi-formulas.md` for the math.
