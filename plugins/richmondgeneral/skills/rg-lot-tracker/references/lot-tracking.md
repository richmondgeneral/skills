# Lot Tracking for Estate & Auction Purchases

## Overview

When purchasing items in lots (estate sales, auctions, bulk buys), track provenance
and allocate costs for margin calculation. Every dollar needs to be accounted for
so the business knows its true profitability.

## Lot Naming Convention

Format encodes the source type:

| Lot Type | Format | Example |
|----------|--------|---------|
| Person/Estate | NAME-NNN | PETER-002 (2nd visit to Peter) |
| Location/Auction | LOCATION-MMYY | IOWA-0925 (Iowa, Sept 2025) |
| Free/Found | FREE-NAME | FREE-JERRY (gift from Jerry) |
| Direct purchase | DIRECT-YYYYMMDD | DIRECT-20251215 |

## Cost Allocation Methods

### Method 1: Equal Split
Divide total cost by number of items.
- **Best when:** Items are similar value
- **Example:** 94 items for $771.09 = $8.20 each
- **Downside:** Overcharges cheap items, undercharges valuable ones

### Method 2: Value-Weighted
Allocate based on estimated resale value.
- **Best when:** Mix of high and low value items
- **Example:** $500 estimated item gets larger share of cost
- **Formula:** `item_cost = lot_total × (item_value / sum_all_values)`

### Method 3: Category-Based
Allocate by category averages.
- **Best when:** Large diverse lots, per-item estimates impractical
- **Example:** Books 20%, Glassware 40%, Misc 40% of lot cost

### Method 4: Manual Override
User specifies exact allocation.
- **Best when:** Direct purchase, or standout piece with known cost

## Best Practices

1. **Photograph lot on arrival** — Document what was received before unpacking
2. **Inventory immediately** — Count and categorize, even roughly
3. **Identify quick flips** — Easy sells to recoup cost fast and reduce exposure
4. **Set aside research items** — Potentially valuable pieces that need more work
5. **Track everything** — Even items that don't sell (write-offs affect lot ROI)
6. **Update lot file after each sale** — Keep running totals current

## Provenance Notes

For valuable items, document:
- Original owner (if known and with permission)
- How acquired (estate sale, auction house, etc.)
- Any accompanying documentation or certificates
- Chain of ownership if available

**Privacy:** Don't include personal details of previous owners in public listings.
Provenance notes stay in lot tracking (ops repo), not on item cards (items repo).

## Integration with Square

When creating Square catalog entries via rg-full-auto:
1. Lot reference goes in internal notes only (not customer-visible)
2. Use lot prefix in tracking spreadsheets
3. Calculate margin based on allocated cost before setting price
