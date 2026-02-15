---
name: rg-lot-tracker
description: >
  Financial tracking for Richmond General inventory — lot creation, cost allocation,
  ROI analysis, pricing validation, and sale recording. This is the single source of
  truth for "what did we pay and are we making money." Use this skill whenever the user
  mentions lots, acquisition costs, ROI, margins, profit, pricing validation against
  cost basis, or wants to record a purchase or sale. Also triggers when rg-full-auto
  delegates lot assignment during item onboarding (Phase 1). Trigger phrases include
  "new lot", "create lot", "record purchase", "bought for $X", "allocate costs",
  "ROI report", "profit report", "how's the lot doing", "price check against cost",
  "lot status", "lot summary", "record sale", "sold for $X", "break even", "margin check".
metadata:
  version: "1.0"
  author: scottybe
  updated: "2026-02-15"
  changelog: |
    v1.0 - Metadata normalization:
    - Added required metadata fields for repository consistency checks
---

# Richmond General Lot Tracker

You manage the financial side of a vintage/antique resale business. Every item
Richmond General sells was acquired somehow — estate sale, auction, free find,
direct purchase. Your job is to track what was paid, allocate costs to individual
items, validate that pricing covers costs with healthy margins, and record sales
so the owner always knows whether they're making or losing money.

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

Two patterns:

1. **Direct** — User says "new lot", "ROI report", "record sale", etc.
2. **Delegation from rg-full-auto** — During item onboarding, Phase 1 delegates
   lot assignment and Phase 3 delegates pricing validation here.

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
| RG-0015 | Vintage milk glass vase | $8.20 | $25.00 | — | Listed |
```

Fields: SKU | Description | Allocated Cost | List Price | Sale Price | Status

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

When an item sells, update lot tracking.

### What to capture

- **Sale price** — what the buyer paid
- **Sale date**
- **Fees** — Square processing: 2.9% + $0.30 per transaction. Shipping: $2–5 (ask or use $3 default)
- **Net profit** — sale price − allocated cost − fees

See `references/roi-formulas.md` for the complete fee schedule and formulas.

### Update the lot file

Change the item's row:
```
| RG-0015 | Vintage milk glass vase | $8.20 | $25.00 | $25.00 | Sold 2026-02-14 |
```

Recalculate the Running Totals section:
```
## Running Totals
- **Total Listed Value:** $105.00
- **Total Sold:** $25.00
- **Total Fees:** $1.02
- **Net P/L:** -$176.03
- **ROI:** -88%
- **Break-even:** Need $176.03 more in net sales
```

---

## Phase 4: Lot Report

Generate a financial summary. User can ask for one lot or all lots.

### Single lot

Read the lot file, present:

```
## Lot PETER-002 — Status Report
Acquired: Nov 19, 2025 | Source: Peter's estate, visit 2 | Cost: $200.00

Items:  4 identified, 2 listed, 0 sold
List Value: $70.00 | Revenue: $0.00 | Fees: $0.00
Net P/L: -$200.00 | ROI: -100%
Break-even: Need $200.00 in net sales

| SKU | Item | Cost | Price | Status |
|-----|------|------|-------|--------|
| RG-0001 | Little Orphan Annie Comic | $5.00 | $19.50 | Listed |
| RG-0006 | Walt Disney Comics Cover | $5.00 | $50.00 | Listed |
| — | 2 items unprocessed | — | — | Pending |
```

### All-lots dashboard

Read all files in `{ops_root}/lot-tracking/`, aggregate:

```
## Richmond General — Financial Dashboard

| Lot | Cost | Listed | Sold | Net P/L | ROI |
|-----|------|--------|------|---------|-----|
| PETER-002 | $200 | $70.00 | $0 | -$200 | -100% |
| IOWA-0925 | $771 | $105.00 | $0 | -$771 | -100% |
| FREE-JERRY | $0 | $55.00 | $0 | $0 | — |
| **Total** | **$971** | **$230.00** | **$0** | **-$971** | **-100%** |

Pipeline: $230.00 in listed inventory across 4 items
Unprocessed: ~96 items across active lots
Break-even: Need $971 in net sales
```

---

## Integration with other skills

### rg-full-auto delegation

rg-full-auto calls this skill at two points:

**Phase 1 (Appraisal):** "Assign this item to a lot and give me the allocated cost."
→ Run Phase 0 (if new lot) + Phase 1. Return lot_id and allocated_cost.

**Phase 3 (Pricing):** "Validate $35.00 against $8.20 cost for mid-range vintage."
→ Run Phase 2. Return margin analysis and recommendation.

### Square

This skill doesn't touch Square directly. Prices go into Square via rg-full-auto
or rg-item-update. Sale data comes from user input ("RG-0015 sold for $25.00").

### What this skill does NOT do

- Create Square catalog entries (→ rg-full-auto)
- Edit item descriptions/prices in Square (→ rg-item-update)
- Generate labels (→ product-labeler)
- Manage the items repo or GitHub Pages
