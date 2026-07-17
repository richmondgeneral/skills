# Inventory Aging Rules & Repricing Strategy

## Aging Tiers

### 🟢 Fresh (0–30 days)
- **Action:** None. Hold at full price.
- **Rationale:** Items need time to find the right buyer. Vintage/antique items
  aren't fast-moving consumer goods — patience pays.
- **Exception:** If an item sells within hours and gets multiple inquiries, it may
  be underpriced. See "Red Flags: Priced Too Low" in pricing-guidelines.md.

### 🟡 Maturing (31–60 days)
- **Action:** Refresh the listing.
- **What "refresh" means:**
  - Update the Square description with seasonal keywords
  - Take new photos from different angles
  - Add to a themed collection or bundle grouping
  - Share on social media or cross-list on Whatnot
- **Rationale:** The item may be fine — it just hasn't found its buyer yet.
  Refreshing the listing gives it new visibility without sacrificing margin.

### 🔴 Stale (61–90 days)
- **Action:** Suggest 10–15% price reduction.
- **Calculation:**
  ```
  suggested_price = current_price × 0.85 (for 15% reduction)
  # But never below the floor:
  floor_price = allocated_cost × 1.5 + 0.30
  final_suggestion = max(suggested_price, floor_price)
  ```
- **Rationale:** At 60+ days, the item is tying up shelf space and capital.
  A modest reduction often triggers a sale without gutting the margin.
- **Present both options:** Show the math for 10% and 15% reductions so the
  owner can choose.

### ⚫ Aged (90+ days)
- **Action:** Evaluate — multiple strategies available.
- **Options to present:**
  1. **Bundle** — Combine with other stale items for a discount package
  2. **Steep discount** — 25–40% reduction (still above floor)
  3. **Whatnot auction** — Start at $1, let the market decide
  4. **Seasonal hold** — If the item is seasonal, shelve until the right time
  5. **Donate/write-off** — If floor price is barely above cost, it may not be
     worth the shelf space. Mark as write-off in lot tracking.
- **Rationale:** There's no single right answer for aged inventory. The owner
  knows the local market and may have context we don't. Present the options
  with math so they can decide.

## Seasonal Adjustments

Some items naturally sell slower because they're seasonal. Don't penalize them
for being listed at the wrong time of year.

| Season | Hot Categories | Slow Categories |
|--------|----------------|-----------------|
| Spring (Mar–May) | Garden, outdoor décor | Holiday, cozy home |
| Summer (Jun–Aug) | Americana, entertaining | Winter décor |
| Fall (Sep–Nov) | Halloween, harvest | Summer/outdoor |
| Winter (Dec–Feb) | Christmas, gifts, cozy | Garden, outdoor |

**Seasonal override:** If an item is in a "slow" category for the current season,
extend aging thresholds by 30 days:
- Fresh: 0–60 days
- Maturing: 61–90 days
- Stale: 91–120 days
- Aged: 120+ days

Note this in the aging report: "Seasonal adjustment applied — garden items
are slow sellers in winter. Extended thresholds by 30 days."

## Repricing Guardrails

### The Margin Floor

Never suggest a price below the margin floor. This protects against selling
at a loss after fees:

```
floor_price = allocated_cost × 1.5 + $0.30

Example:
  Cost: $8.20
  Floor: $8.20 × 1.5 + $0.30 = $12.60
  At $12.60: Square fee = $0.67, net = $11.93, profit = $3.73 (45%)
```

The 1.5× floor ensures at least 45% gross margin after fees. Below this,
the effort of listing, storing, and fulfilling the item isn't worth it.

### Floor Exceptions

- **Free items** (cost = $0): Floor is $3.00 (minimum viable listing price)
- **Write-off candidates**: Owner can override floor for liquidation
- **Bundle components**: Individual items in a bundle can go below floor if
  the bundle total exceeds the combined floor

### Repricing Waterfall

When suggesting reductions, present a waterfall showing the math at each level:

```
Current price:    $35.00  (4.3× on $8.20 cost)
At -10%:          $31.50  (3.8×) — still exceeds 3–4× target ✅
At -15%:          $30.00  (3.7×) — still exceeds 3–4× target ✅
At -25%:          $26.00  (3.2×) — at lower end of target range 🟡
At -40%:          $21.00  (2.6×) — below target but above floor ⚠️
Floor:            $12.60  (1.5×) — minimum viable price 🔴
```

This gives the owner a clear picture of how much room there is to negotiate
or discount while staying profitable.

## Aging Calculation

```
days_on_market = today - listed_date
```

If `listed_date` is missing from a lot file row, and the item shows "Listed":
1. Check if the lot file has a git history with the date the row was added
2. Fall back to the lot's acquisition date as a conservative estimate
3. Flag the item: "No listed date — using lot date as estimate. Update
   the lot file with the actual listing date for accurate aging."

## Bulk Aging Summary Metrics

When generating aging reports, include these aggregate metrics:

```
Total listed items: 6
Avg days on market: 52
Median days on market: 45
Stale rate: 50% (3 of 6 items over 60 days)
Capital at risk: $90.00 in stale listed value ($21.40 in allocated cost)
Estimated revenue if all stale items reduce 15%: $76.50
```
