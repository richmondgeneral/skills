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
- **Last Reconciled:** {YYYY-MM-DD or "never"}

## Items

| SKU | Item | Allocated Cost | List Price | Sale Price | Channel | Status | Listed Date |
|-----|------|----------------|------------|------------|---------|--------|-------------|
| | | | | | | | |

### Status values
- **Pending** — identified but not yet listed
- **Listed** — live on Square with payment link
- **Sold** — sold, include date (e.g., "Sold 2026-02-14")
- **Write-off** — unsellable, damaged, or donated

### Listed Date
Always populate when status changes to "Listed". Format: YYYY-MM-DD.
This date powers inventory aging analysis (Phase 6). Without it, aging
thresholds can't be calculated accurately.

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
- **Avg Days to Sell:** — (no sales yet)
- **Sell-Through Rate:** 0%
- **Lot Health Score:** — (calculated on demand, see Phase 7)
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
- **Listed Date**: The date the item went live on Square. Critical for aging
  analysis. If unknown, use the date the lot file row was added.
- **Last Reconciled**: Updated automatically by Phase 5 (Square Sales
  Auto-Reconciliation). Tracks when we last checked Square for completed
  orders against this lot.
- **Running Totals**: Recalculate after every sale or new listing.
  See `roi-formulas.md` for the math.
- **Avg Days to Sell**: Calculated from sold items only.
  `sum(sale_date - listed_date for sold items) / count(sold items)`
- **Sell-Through Rate**: `items_sold / items_identified × 100%`
- **Lot Health Score**: Not stored — calculated on demand by Phase 7.
  Reference `health-scoring.md` for the rubric.

## Migration note (v1 → v2)

If upgrading an existing lot file from v1 format:
1. Add the `Listed Date` column to the Items table
2. Add `Last Reconciled` to Acquisition Details
3. Add velocity metrics to Running Totals (Avg Days to Sell, Sell-Through Rate)
4. Backfill Listed Dates where possible (check git history or use lot acquisition date)
5. Add `Channel` column if not already present (v1.1+ has it)
