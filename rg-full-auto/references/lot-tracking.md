# Lot Tracking for Estate & Auction Purchases

## Overview

When purchasing items in lots (estate sales, auctions, bulk buys), track provenance and allocate costs for margin calculation.

## Lot Naming Convention

**Format:** `L##` where ## is sequential lot number

| Lot ID | Description | Date | Total Cost |
|--------|-------------|------|------------|
| L1 | Example Estate | 2024-01-15 | $150.00 |
| L2 | Peter's Estate | 2024-11-20 | $771.09 |

## Cost Allocation Methods

### Method 1: Equal Split
Divide total cost by number of items.
- **Use when:** Items are similar value
- **Example:** 94 items for $771.09 = $8.20 each

### Method 2: Value-Weighted
Allocate based on estimated resale value.
- **Use when:** Mix of high and low value items
- **Example:** $500 estimated item gets 40% of cost allocated

### Method 3: Category-Based
Allocate by category averages.
- Books: 20% of lot cost
- Glassware: 30% of lot cost
- Etc.

## ROI Calculation

```
Item ROI = (Sale Price - Allocated Cost - Fees) / Allocated Cost × 100

Lot ROI = (Total Sales - Total Cost - Total Fees) / Total Cost × 100
```

**Fee estimates:**
- Square processing: 2.9% + $0.30 per transaction
- Shipping materials: ~$2-5 per item
- Time value: Consider hourly rate for processing

## Tracking Spreadsheet Fields

| Field | Description |
|-------|-------------|
| Lot ID | L## identifier |
| Item SKU | RG-XXXX |
| Item Description | Brief description |
| Allocated Cost | Cost assigned to this item |
| List Price | Asking price |
| Sale Price | Actual sale price |
| Sale Date | When sold |
| Fees | Square + shipping |
| Net Profit | Sale - Cost - Fees |
| ROI % | Calculated return |

## Provenance Notes

For valuable items, document:
- Original owner (if known)
- How acquired (estate sale, auction house, etc.)
- Any accompanying documentation
- Chain of ownership if available

**Privacy note:** Don't include personal details of previous owners in public listings without permission.

## Best Practices

1. **Photograph lot on arrival** - Document what was received
2. **Inventory immediately** - Count and categorize items
3. **Identify quick flips** - Easy sells to recoup cost fast
4. **Set aside research items** - Potentially valuable pieces needing more work
5. **Track everything** - Even items that don't sell

## Integration with RG-Inventory

When creating Square catalog entries:
1. Include lot reference in internal notes (not public)
2. Use lot prefix in any tracking spreadsheets
3. Calculate margin based on allocated cost
