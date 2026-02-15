# ROI Formulas & Fee Schedule

## Fee Schedule

### Square Payment Processing
- **Rate:** 2.9% + $0.30 per transaction
- **Applies to:** All payment link sales

### Shipping (if applicable)
- **Materials:** $2–5 per item (varies by size/weight)
- **Default estimate:** $3 if not specified
- **Note:** Many RG items are local pickup, so shipping = $0

### Time Value (optional)
- User-configurable hourly rate for processing time
- Not included in standard ROI calculations unless user requests it
- Useful for evaluating whether low-margin items are worth the effort

## Formulas

### Per-Item Calculations

```
Square Fee = (Sale Price × 0.029) + 0.30

Net Revenue = Sale Price − Square Fee − Shipping Cost

Net Profit = Net Revenue − Allocated Cost

Margin % = (Net Profit / Allocated Cost) × 100

Multiplier = Sale Price / Allocated Cost
```

**Example:**
```
Item: RG-0015 (Vintage milk glass vase)
Allocated Cost: $8.20
Sale Price: $24.99
Square Fee: ($24.99 × 0.029) + $0.30 = $1.02
Shipping: $0 (local pickup)
Net Revenue: $24.99 − $1.02 = $23.97
Net Profit: $23.97 − $8.20 = $15.77
Margin: 192%
Multiplier: 3.0×
```

### Lot-Level Calculations

```
Lot Revenue = sum(all item sale prices in lot)

Lot Fees = sum(all Square fees + shipping for lot)

Lot Net P/L = Lot Revenue − Lot Fees − Total Lot Cost

Lot ROI = (Lot Net P/L / Total Lot Cost) × 100
```

**Break-even point:**
```
Break-even Revenue = Total Lot Cost + Estimated Fees on that Revenue
```

Since fees are a percentage, solve:
```
Break-even = Total Lot Cost / (1 − 0.029) + (0.30 × estimated_number_of_sales)
```

Simplified: `Break-even ≈ Total Lot Cost × 1.03 + ($0.30 × num_items_to_sell)`

### All-Lots Aggregate

```
Total Investment = sum(all lot costs)
Total Revenue = sum(all sales across all lots)
Total Fees = sum(all fees across all lots)
Overall P/L = Total Revenue − Total Fees − Total Investment
Overall ROI = (Overall P/L / Total Investment) × 100
```

## Free Items

- Allocated cost = $0
- ROI is undefined (division by zero) — display as "—" or "∞"
- Still track revenue and fees for volume reporting
- Include in aggregate totals for overall business health

## Reporting Format

When presenting financials, always include:
1. The raw numbers (cost, price, fees, profit)
2. The percentage margin
3. The multiplier (×)
4. Comparison to target for the category
5. Break-even context for lot-level reports
