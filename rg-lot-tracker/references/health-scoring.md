# Lot Health Scoring & Break-Even Projections

## Health Score (0–100)

The health score distills a lot's financial performance into a single number.
It answers the question: "Is this lot on track to make money, or does it need
intervention?"

The score is relative to the lot's age — a lot acquired yesterday with no sales
isn't "unhealthy," it's just new. The score accounts for time by comparing
performance against expected milestones.

## Component Breakdown

### Cost Recovery (35 points)

The most heavily weighted component because it directly answers "are we getting
our money back?"

```
net_revenue = total_sold - total_fees
recovery_pct = net_revenue / total_lot_cost × 100

Scoring:
  100%+ recovered → 35 points (fully profitable)
  75–99%          → 28–34 points (nearly there)
  50–74%          → 18–27 points (halfway)
  25–49%          → 9–17 points (slow recovery)
  0–24%           → 0–8 points (barely started)

Formula: score = min(35, (recovery_pct / 100) × 35)
```

**Free lots (cost = $0):** Auto-score 35/35 for cost recovery since there's
nothing to recover. Any revenue is pure profit.

### Sell-Through Rate (25 points)

Measures what fraction of the lot's items have actually sold. A lot with 94
items and 1 sale has very different health than a lot with 4 items and 1 sale.

```
sell_through_pct = items_sold / items_identified × 100

Scoring:
  75%+ sold    → 25 points
  50–74%       → 18–24 points
  25–49%       → 10–17 points
  10–24%       → 4–9 points
  0–9%         → 0–3 points

Formula: score = min(25, (sell_through_pct / 75) × 25)
```

### Processing Rate (15 points)

Are items being identified and listed, or sitting in boxes? High processing rate
means the lot is being actively worked — even if nothing has sold yet, the
pipeline is being filled.

```
processing_pct = items_listed / total_estimated_items × 100

Scoring:
  80%+ processed → 15 points
  50–79%         → 10–14 points
  25–49%         → 5–9 points
  0–24%          → 0–4 points

Formula: score = min(15, (processing_pct / 80) × 15)
```

### Inventory Freshness (15 points)

How long have listed (unsold) items been sitting? Lower average days = healthier.
This component penalizes lots with stale inventory.

```
avg_days = average days on market for all currently-listed items

Scoring:
  0–30 days avg  → 15 points (all fresh)
  31–45 days     → 12–14 points
  46–60 days     → 8–11 points
  61–90 days     → 4–7 points
  90+ days       → 0–3 points

Formula: score = max(0, 15 - (avg_days / 6))
  (capped at 15, floored at 0)
```

**No items listed yet:** Score 10/15 (neutral — can't judge freshness without listings).

### Margin Quality (10 points)

Are items selling at or above target margins? This rewards lots where the
pricing strategy is working.

```
For each sold item:
  actual_multiplier = sale_price / allocated_cost
  target_multiplier = category target from pricing-guidelines.md
  margin_quality = actual_multiplier / target_multiplier

avg_margin_quality = average across all sold items

Scoring:
  120%+ of target → 10 points (exceeding targets)
  100–119%        → 8–9 points (on target)
  80–99%          → 5–7 points (slightly below)
  50–79%          → 2–4 points (well below)
  < 50%           → 0–1 points (margins are bad)

Formula: score = min(10, (avg_margin_quality / 120) × 10)
```

**No sold items yet:** Score 5/10 (neutral — no data to judge).

**Free items:** Margin quality is always 10/10 since any sale is pure profit.

## Total Score Calculation

```python
health_score = (
    cost_recovery_score +      # 0–35
    sell_through_score +        # 0–25
    processing_score +          # 0–15
    freshness_score +           # 0–15
    margin_quality_score        # 0–10
)                               # Total: 0–100
```

## Score Presentation

Always show the component breakdown so the owner understands what's dragging
the score down (and what's working):

```
## Lot IOWA-0925 — Health Score: 🟠 45/100

| Component | Score | Detail |
|-----------|-------|--------|
| Cost Recovery | 12/35 | $25.00 of $771.09 recovered (3.2%) |
| Sell-Through | 6/25 | 1 of 94 items sold (1.1%) |
| Processing | 3/15 | 4 of 94 items identified (4.3%) |
| Freshness | 14/15 | Avg 38 days (within fresh range) |
| Margin Quality | 10/10 | 3.0× avg multiplier (on target) |
```

Notice how the score tells a story: margins and freshness are great, but the
lot has 90+ unprocessed items. The fix isn't repricing — it's processing more
items to fill the pipeline.

## Break-Even Projections

### With Sales History

When at least one sale has occurred, use actual velocity:

```
daily_net_revenue = total_net_revenue / days_since_first_sale
remaining_to_recover = total_lot_cost - total_net_revenue
days_to_break_even = remaining_to_recover / daily_net_revenue
projected_date = today + days_to_break_even
```

### Without Sales (Estimation)

When no sales have happened yet but items are listed, estimate from pipeline:

```
# Use category average sell-through rates:
avg_monthly_sell_through = 0.15  # ~15% of listed items sell per month (conservative)
avg_net_margin = 0.65            # 65% net margin after fees (from pricing targets)

estimated_monthly_revenue = total_listed_value × avg_monthly_sell_through
estimated_monthly_net = estimated_monthly_revenue × avg_net_margin
months_to_break_even = remaining_cost / estimated_monthly_net
```

These estimates are rough — flag them clearly:

```
Break-Even Projection (estimated — no sales data yet)
Based on $105.00 in listed inventory and category averages:
  Est. monthly net revenue: ~$10.24
  Est. months to break even: ~19 months

This projection improves dramatically as more items get listed.
Listing 10 more items at avg $25 would cut this to ~6 months.
```

### Projection Improvements

When presenting projections, also show what-if scenarios:

```
Break-Even Scenarios for IOWA-0925 ($771.09 cost)

Current pace (1 sale/month @ $25 avg):     ~38 months
List 5 more items/month:                    ~12 months
List 10 more items/month:                   ~6 months
If a $200 showcase piece sells:             Immediately cuts 6 months off

Fastest path: batch-process the quick-flip items. Even at $10-15 each,
volume recovers cost faster than waiting for big-ticket sales.
```

## Aggregate Health (All Lots)

When reporting on all lots, include a weighted average health score:

```
overall_health = sum(lot_score × lot_cost) / sum(lot_cost)
```

Weighting by cost means expensive lots have more influence — which makes sense
because a $771 lot at 🔴 28 is a bigger problem than a $0 lot at 🟢 85.

Free lots are excluded from the weighted average (they can't drag down health
since there's no cost to recover).

```
## Overall Business Health: 🟡 58/100

| Metric | Value |
|--------|-------|
| Total Investment | $971 |
| Total Recovery | $25.00 (2.6%) |
| Active Lots | 3 |
| Items in Pipeline | 6 listed, 96 unprocessed |
| Weighted Health Score | 58/100 |
| Overall Break-Even | ~18 months at current velocity |
```
