---
name: rg-lot-tracker
description: >
  Financial tracking and intelligence for Richmond General inventory — lot creation,
  cost allocation, ROI analysis, pricing validation, sale recording, Square sales
  auto-reconciliation, inventory aging alerts, and lot health scoring. Single source
  of truth for "what did we pay and are we making money." Triggers on "new lot",
  "record purchase", "ROI report", "profit", "margin check", "record sale",
  "reconcile sales", "stale inventory", "aging report", "lot health", "lot score",
  "velocity report", "what needs repricing".
metadata:
  version: "2.0"
  author: scottybe
  updated: "2026-02-16"
  changelog: |
    v2.0 - Aging, health scoring, and enhanced reporting:
    - Added Phase 5: Square Sales Auto-Reconciliation (MCP query patterns for order matching)
    - Added Phase 6: Inventory Aging & Health Monitor (days-on-market, stale alerts, repricing)
    - Added Phase 7: Lot Health Scoring & Break-Even Projections (velocity-based forecasting)
    - Enhanced Phase 0: Smart allocation method recommendation based on lot characteristics
    - Enhanced Phase 4: Category-level performance analytics, health scores, auto-run reconciliation+aging
    - Added Listed Date column to item table (powers aging analysis)
    - Added velocity metrics to Running Totals (Avg Days to Sell, Sell-Through Rate)
    - New reference: aging-rules.md (aging thresholds, seasonal adjustments, repricing guardrails)
    - New reference: health-scoring.md (lot scoring rubric, velocity formulas, break-even projections)
    - Updated lot-file-template with Listed Date, Last Reconciled, velocity metrics

    v1.1 - Multi-channel awareness + auto-detect sales:
    - Added channel field (Square / Whatnot / Local / Other) to sale recording
    - Added channel-branched fee calculations (Whatnot 12.9%, Square 2.9%+$0.30, Local $0)
    - Added auto-detect sales from Square completed orders (now Phase 5)
    - Removed hardcoded Active Lots table from references (dynamic dashboard handles this)
    - Updated lot-file-template with Channel column
    - Updated roi-formulas.md with Whatnot fee schedule and branched examples

    v1.0 - Metadata normalization:
    - Added required metadata fields for repository consistency checks
---

# Richmond General Lot Tracker

You manage the financial intelligence for a vintage/antique resale business. Every item
Richmond General sells was acquired somehow — estate sale, auction, free find,
direct purchase. Your job is to track what was paid, allocate costs to individual
items, validate that pricing covers costs with healthy margins, record sales,
auto-reconcile with Square, monitor inventory aging, and score lot health — so the
owner always knows whether they're making or losing money, and what needs attention.

## Where the data lives

All financial data lives in the **private ops repo** (richmondgeneral/ops).
The canonical local path is `~/workspace/square/ops`.

```
ops/
├── lot-tracking/          # One markdown file per acquisition lot
│   ├── PETER-002.md
│   ├── IOWA-0925.md
│   ├── FREE-JERRY.md
│   └── ...
├── inventory/
│   └── rg-inventory-tracker.xlsx   # Master spreadsheet (optional)
```

### Resolving the ops repo path (REQUIRED)

Before any read or write, locate the ops repo root. Check in order:

1. `~/workspace/square/ops` (standard location)
2. A sibling `ops/` directory next to the current repo root
3. Ask the user: "Where is the ops repo cloned?"

**If the ops repo cannot be found, STOP.** Do not write lot files to the current
directory, a temp folder, or anywhere else. Financial data written outside the
private ops repo risks leaking acquisition costs and margins into a public repo.

Tell the user: "I need the ops repo path to save lot data. Is it at
`~/workspace/square/ops`, or somewhere else?"

Once resolved, store the path and use it as the base for all `lot-tracking/`
and `inventory/` paths throughout the session.

## How this skill gets called

Three patterns:

1. **Direct** — User says "new lot", "ROI report", "record sale", "stale inventory", etc.
2. **Delegation from rg-full-auto** — During item onboarding, Phase 1 delegates
   lot assignment and Phase 3 delegates pricing validation here.
3. **Proactive** — When running a lot report (Phase 4), automatically check for
   unreconciled Square sales (Phase 5) and aging issues (Phase 6) to surface
   actionable insights without being asked.

When delegated, you receive an item SKU, description, and proposed price.
Return: lot ID, allocated cost, and margin analysis.

---

## Phase 0: Create or Select a Lot

When a new acquisition arrives, create a lot to track it.

### Lot ID format

The ID encodes the source so it's easy to find later:

| Source | Format | Example | When |
|--------|--------|---------|------|
| Person/Estate | NAME-NNN | PETER-002 | Buying from an individual (NNN = visit #) |
| Location/Auction | LOCATION-MMYY | IOWA-0925 | Auction or location-based purchase |
| Free/Found | FREE-NAME | FREE-JERRY | Items received for free |
| Direct purchase | DIRECT-YYYYMMDD | DIRECT-20251215 | One-off store/online buys |

If a lot already exists, ask: "Add to existing lot **{LOT_ID}**, or create new?"

### Create the lot file

Read `references/lot-file-template.md` and fill it in. Key fields:

- **Source** — who/where (e.g., "Peter's estate, 2nd visit")
- **Date** — acquisition date
- **Total Cost** — what was paid for the entire lot
- **Item Count** — estimated items (approximate is fine for large lots)
- **Allocation Method** — how costs divide among items (see Phase 1)

Save to `{ops_root}/lot-tracking/{LOT_ID}.md` (where `{ops_root}` is the
resolved ops repo path from the "Resolving the ops repo path" step above).

Even if the user says "I don't know the cost" — prompt once more: "Rough
estimate? Even a ballpark helps track margins. Or I can mark it TBD."

### Smart allocation recommendation

When creating a lot, analyze the characteristics and recommend the best allocation method:

| Lot Characteristics | Recommended Method | Why |
|--------------------|--------------------|-----|
| < 10 items, similar category | Equal Split | Items likely similar value |
| Mixed high/low value items | Value-Weighted | Prevents overcharging cheap items |
| 20+ items, diverse categories | Category-Based | Per-item estimates impractical |
| Single item or known price | Manual Override | Exact cost is known |
| Free items | N/A (cost = $0) | Track for volume only |

Present your recommendation with reasoning, but let the owner decide:

```
Allocation Recommendation: Value-Weighted

This lot has 12 items ranging from a $5 paperback to a $200 vintage lamp.
Equal split ($25 each) would overcharge the books and hide the lamp's true
cost basis. Value-weighted gives each item a cost proportional to its
estimated resale value, so margin calculations stay honest.

Want to use value-weighted, or prefer a different method?
```

---

## Phase 1: Allocate Cost to an Item

When an item gets onboarded, assign it a cost from its lot. This number drives
all margin calculations — get it right.

### Allocation methods

**Equal Split** (default for bulk lots)
```
allocated_cost = total_lot_cost / item_count
```
Simple and fair when items are similar value. Example: 94 items for $771.09 → $8.20 each.

**Value-Weighted**
```
item_share = item_estimated_value / sum(all_estimated_values)
allocated_cost = total_lot_cost × item_share
```
Use when the lot has a mix of $5 items and $50 items — equal split would
overcharge the cheap ones and undercharge the valuable ones.

**Category-Based**
Allocate by category percentages (e.g., books 20%, glassware 40%, misc 40%).
Useful for large diverse lots where per-item estimates aren't practical.

**Manual Override**
User specifies exact cost. Use for direct purchases or standout pieces.

**Free items** — cost is $0. Still track for volume and revenue reporting.

### Update the lot file

Add a row to the Items table:

```
| RG-0015 | Vintage milk glass vase | $8.20 | $25.00 | — | — | Listed | 2026-02-14 |
```

Fields: SKU | Description | Allocated Cost | List Price | Sale Price | Channel | Status | Listed Date

**Important:** Always include the Listed Date when status is "Listed". This powers
the aging analysis in Phase 6. Without it, aging can't be calculated.

---

## Phase 2: Validate Pricing

Before an item goes live, check that the price makes business sense against cost.

### Margin targets

Quick reference (full details in `references/pricing-guidelines.md`):

| Category | Cost Range | Target Multiplier |
|----------|------------|-------------------|
| Quick flip | $1–5 | 2.5–3× |
| Mid-range vintage | $5–25 | 3–4× |
| Showcase pieces | $25+ | Research-based |
| Books (common) | $1–5 | 3–5× |
| Books (collectible) | $10+ | Research-based |
| Carnival glass | $5–50 | 2.5–3.5× |

### Present the analysis

Always show the math — the owner wants to see the numbers:

```
Allocated cost:     $8.20
Proposed price:     $35.00
Gross margin:       $26.80 (327%)
Multiplier:         4.3×
Square fees (est):  $1.32  (2.9% + $0.30)
Net after fees:     $25.48
Net margin:         311%

✅ GOOD — exceeds 3–4× target for mid-range vintage
```

### Price formatting rules

- Under $20 → price in `.50` increments (e.g., `$8.50`, `$13.50`, `$19.50`)
- $20+ → whole-dollar prices (`$35.00`, `$85.00`, `$125.00`)
- Do not use `.99` endings
- Keep stored values numeric with two decimals for platform compatibility

### Below-target warnings

If margin is below target, flag it clearly but don't block:
```
⚠️ $13.50 on $8.20 cost = 1.6× (target: 3–4×). Suggest $25.00+.
```

The owner might have reasons (quick flip, shelf space, bundling) — just make
sure they see the math before deciding.

---

## Phase 3: Record a Sale

When an item sells, update lot tracking. For bulk reconciliation against Square,
see Phase 5.

### Manual entry

User tells you directly: "RG-0015 sold for $25.00" or "record sale".

### What to capture

- **Sale price** — what the buyer paid
- **Sale date**
- **Channel** — where the sale happened:
  | Channel | Fees |
  |---------|------|
  | Square | 2.9% + $0.30 |
  | Whatnot | 12.9% (9.9% seller + 3% payment) |
  | Local Pickup / Cash | $0 |
  | Other | Ask user |
- **Shipping** — $2–5 if shipped (ask or use $3 default); $0 for local/Whatnot
- **Net profit** — sale price − allocated cost − fees − shipping
- **Days on market** — sale date − listed date (for velocity analysis)

See `references/roi-formulas.md` for the complete fee schedule and formulas.

### Update the lot file

Change the item's row:
```
| RG-0015 | Vintage milk glass vase | $8.20 | $25.00 | $25.00 | Square | Sold 2026-02-14 | 2026-01-15 |
```

Recalculate the Running Totals section (now includes velocity metrics):
```
## Running Totals
- **Items Identified:** 4
- **Items Listed:** 2
- **Items Sold:** 1
- **Total Listed Value:** $105.00
- **Total Sold:** $25.00
- **Total Fees:** $1.02
- **Net P/L:** -$176.03
- **ROI:** -88%
- **Break-even:** Need $176.03 more in net sales
- **Avg Days to Sell:** 30
- **Sell-Through Rate:** 25% (1 of 4 identified)
- **Last Reconciled:** 2026-02-16
```

---

## Phase 4: Lot Report (Enhanced)

Generate a financial summary with category analytics. User can ask for one lot or all lots.

**Before generating any report, automatically run Phase 5 (reconcile) and Phase 6 (aging)** to ensure data is current and surface actionable insights.

### Single lot

Read the lot file, present:

```
## Lot PETER-002 — Status Report
Acquired: Nov 19, 2025 | Source: Peter's estate, visit 2 | Cost: $200.00
Lot Health Score: 🟡 62/100 (see Phase 7)

Items:  4 identified, 2 listed, 1 sold
List Value: $70.00 | Revenue: $25.00 | Fees: $1.02
Net P/L: -$176.03 | ROI: -88%
Break-even: Need $176.03 in net sales

Velocity & Aging
Avg days to sell: 30 | Sell-through: 25%
Projected break-even: ~4 months at current velocity

| SKU | Item | Cost | Price | Channel | Status | Days |
|-----|------|------|-------|---------|--------|------|
| RG-0001 | Orphan Annie Comic | $5.00 | $19.50 | — | Listed | 88 ⚠️ |
| RG-0006 | Disney Comics Cover | $5.00 | $50.00 | — | Listed | 45 |
| RG-0015 | Milk glass vase | $8.20 | $25.00 | Square | Sold (30d) | — |
| — | 1 item unprocessed | — | — | — | Pending | — |

⚠️ RG-0001: 88 days — consider price reduction (see aging report)
```

### All-lots dashboard

Aggregate all lots plus category performance breakdown:

```
## Richmond General — Financial Dashboard

### Lot Summary
| Lot | Cost | Listed | Sold | Net P/L | ROI | Health |
|-----|------|--------|------|---------|-----|--------|
| PETER-002 | $200 | $70.00 | $25.00 | -$176 | -88% | 🟡 62 |
| IOWA-0925 | $771 | $105.00 | $0 | -$771 | -100% | 🔴 28 |
| FREE-JERRY | $0 | $55.00 | $0 | $0 | — | 🟢 85 |
| **Total** | **$971** | **$230.00** | **$25.00** | **-$947** | **-97%** | |

### Category Performance
| Category | Items | Avg Price | Avg Margin | Avg Days | Revenue |
|----------|-------|-----------|------------|----------|---------|
| Books | 2 | $35.00 | 285% | 45 | $25.00 |
| Glassware | 1 | $25.00 | 205% | — | $0 |
| Furniture | 1 | $55.00 | ∞ (free) | — | $0 |

### Action Items
🔴 2 items past 60-day threshold — reprice or bundle
🟡 96 items unprocessed — $771 in unrecovered cost
💰 Pipeline: $230.00 in listed inventory
📈 Break-even: Need $947 in net sales
```

---

## Phase 5: Square Sales Auto-Reconciliation

The automated bridge between Square and lot tracking. Instead of waiting for
the user to manually report sales, proactively check Square for completed orders.

### When to run

- **Automatically** before generating any lot report (Phase 4)
- **On demand** when user says "what's sold", "reconcile sales", "check Square"

### How it works

1. **Query Square orders** for completed sales at Richmond General's location:

Use the Square MCP `make_api_request` (Square-Version `2026-04-21`). Discover the
exact shape first with `get_service_info`/`get_type_info` for the `orders` service.

```
mcp__mcp_square_api__make_api_request
  service: orders
  method: search          # SearchOrders
  request:
    location_ids: ["B87BAEZ0NWV34"]
    query:
      filter:
        state_filter:
          states: ["COMPLETED"]
        date_time_filter:
          created_at:
            start_at: "{last_reconciliation_date or 30_days_ago}"
      sort:
        sort_field: "CREATED_AT"   # must match the date_time_filter field
        sort_order: "DESC"
    return_entries: false   # return full Order objects
    limit: 50
```

The response returns full `Order` objects; read `id`, `created_at`, `state`,
`line_items[].name`, `line_items[].catalog_object_id`, `line_items[].quantity`,
`line_items[].total_money`, and `tenders[].type` from each.

2. **Match against lot files** — For each order line item:
   - Look up catalog_object_id via `square_cache_mcp:square_cache_get_item` to get SKU
   - Match SKU against lot file item tables
   - If no catalog ID, fuzzy-match item name against descriptions

3. **Identify unreconciled sales** — Items showing "Listed" in lot files but
   "COMPLETED" in Square orders.

4. **Present findings for confirmation**:

```
🔍 Square Reconciliation — Found 2 unrecorded sales

| SKU | Item | Lot | Sale Price | Sale Date | Tender |
|-----|------|-----|------------|-----------|--------|
| RG-0015 | Milk glass vase | IOWA-0925 | $25.00 | Feb 10 | Card |
| RG-0006 | Disney Comics Cover | PETER-002 | $45.00 | Feb 12 | Cash |

Record these sales? (I'll update lot files and recalculate totals)
```

5. **On confirmation** — Run Phase 3 for each, using appropriate channel/fee calculation
   (card via Square = 2.9% + $0.30, cash = $0 fees).

6. **Update `Last Reconciled` date** in each affected lot file.

---

## Phase 6: Inventory Aging & Health Monitor

Stale inventory ties up capital and shelf space. This phase monitors how long
items have been listed and surfaces actionable recommendations.

See `references/aging-rules.md` for complete thresholds, seasonal adjustments,
and repricing strategy.

### When to run

- **Automatically** as part of any lot report (Phase 4)
- **On demand** when user says "stale inventory", "aging report", "what needs repricing"

### Aging tiers

| Tier | Days Listed | Action |
|------|------------|--------|
| 🟢 Fresh | 0–30 | Hold at full price |
| 🟡 Maturing | 31–60 | Refresh listing (new photos/description) |
| 🔴 Stale | 61–90 | Suggest 10–15% price reduction |
| ⚫ Aged | 90+ | Bundle, steep discount, or hold for seasonal |

### Aging report format

```
## Inventory Aging Report — 2026-02-16

🔴 Needs Attention (3 items, $90.00 listed)
| SKU | Item | Price | Cost | Days | Suggested Action |
|-----|------|-------|------|------|-----------------|
| RG-0001 | Orphan Annie Comic | $19.50 | $5.00 | 88 | Reduce to $16.50 (still 3.3×) |

🟡 Maturing (2 items, $75.00 listed)
| RG-0006 | Disney Comics | $50.00 | $5.00 | 45 | Refresh listing |

🟢 Fresh (1 item, $55.00 listed) — no action needed

Summary: Avg 52 days | 50% stale rate | $90.00 at risk
```

### Repricing guardrails

Never suggest below the margin floor: `floor = cost × 1.5 + $0.30`

If a suggested price hits the floor, flag it so the owner can make an informed call.
See `references/aging-rules.md` for the full repricing waterfall.

---

## Phase 7: Lot Health Scoring & Break-Even Projections

Each lot gets a health score (0–100) that synthesizes multiple signals into a
single number. See `references/health-scoring.md` for the complete rubric.

### Health score components

| Component | Weight | Measures |
|-----------|--------|----------|
| Cost Recovery | 35% | % of lot cost recovered through net sales |
| Sell-Through Rate | 25% | % of identified items sold |
| Processing Rate | 15% | % of items listed vs total estimated |
| Inventory Freshness | 15% | Inverse of avg days on market |
| Margin Quality | 10% | Actual margins vs category targets |

### Score interpretation

| Score | Grade | Meaning |
|-------|-------|---------|
| 80–100 | 🟢 | Healthy — on track to profit |
| 60–79 | 🟡 | Needs attention — some items stale or under-margin |
| 40–59 | 🟠 | At risk — slow velocity, capital tied up |
| 0–39 | 🔴 | Critical — unlikely to break even without intervention |

### Break-even projection

With sales history: `days_to_break_even = remaining_cost / daily_net_revenue`

Without sales: estimate from listed value × category sell-through rate.

```
## Lot IOWA-0925 — Health: 🟠 45/100

Cost Recovery: 12/35 | Sell-Through: 6/25 | Processing: 3/15
Freshness: 14/15 | Margin Quality: 10/10

📈 At current velocity ($0.83/day), break-even in ~929 days.
   To break even in 6 months: list 15 items/month at avg $25.
💡 90 unprocessed items — batch-process quick-flips to recover cost fast.
```

---

## Integration with other skills

### rg-full-auto delegation

rg-full-auto calls this skill at two points:

**Phase 1 (Appraisal):** "Assign this item to a lot and give me the allocated cost."
→ Run Phase 0 (if new lot) + Phase 1. Return lot_id and allocated_cost.

**Phase 3 (Pricing):** "Validate $35.00 against $8.20 cost for mid-range vintage."
→ Run Phase 2. Return margin analysis and recommendation.

### Square (v2.0)

This skill reads from Square for sales reconciliation (Phase 5). It uses:
- `mcp__mcp_square_api__make_api_request` (service `orders`, method `search`,
  Square-Version `2026-04-21`) for querying completed orders
- `square_cache_mcp:square_cache_get_item` for SKU lookups
- `square_cache_mcp:square_cache_search` for fuzzy matching

It still does NOT write to Square — prices and catalog entries go through
rg-full-auto or rg-item-update.

### What this skill does NOT do

- Create Square catalog entries (→ rg-full-auto)
- Edit item descriptions/prices in Square (→ rg-item-update)
- Generate labels (→ product-labeler)
- Manage the items repo or GitHub Pages
