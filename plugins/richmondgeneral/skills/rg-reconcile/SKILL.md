---
name: rg-reconcile
description: READ-ONLY drift reconcile for Richmond General inventory. Walks each items/RG-XXXX page (label.json + status.json) and compares it against every channel the item lives on — Square (live catalog) and Whatnot (import CSV) — using the item-model field-authority rules, then writes a JSON drift report to ops/reports/. Surfaces sold-state conflicts (CRITICAL — can double-sell a unique item) and unintended price divergence (WARNING). Use to audit channel consistency, run the reconciliation sweep, check for drift, or answer "are prices/sold-state consistent across channels". Triggers on "reconcile", "drift report", "check channels", "channel consistency", "reconciliation sweep". Makes NO writes to any channel — for fixing drift, use rg-item-update (price/description) or rg-item-mark-sold (sold state).
metadata:
  version: "1.1"
  author: scottybe
  updated: "2026-06-20"
---

# Richmond General Reconcile

Read-only drift detection across the channels an item is listed on. The
`items/RG-XXXX/` page is the spine (source of truth); each channel is observed
and diffed against it per the item-model field-authority model. Nothing is
mutated — the output is a report.

## What it checks

| Field | Severity | Rule |
|-------|----------|------|
| sold_state | CRITICAL | page sold ≠ channel sold (risk of double-selling a unique item) |
| price | WARNING | channel price ≠ intended/reference price (skipped on sold items) |

> **Channel authority.** Square is *authoritative* — a live catalog that can both confirm a
> listing and report it absent (`present=false`). The Whatnot **import CSV is affirm-only**: it
> confirms a SKU's listing/price/sold, but a SKU *missing* from the CSV means "not in this export"
> (e.g. listed directly via the Whatnot UI), **not** "delisted." So this reconcile cannot surface a
> genuine Whatnot delisting — Whatnot absence is treated as "not checked," never as drift.

## Run

```bash
set -a; . /Users/scottybe/workspace/richmondgeneral/.env; set +a
uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/skills/rg-reconcile/scripts/reconcile.py
```

Options:
- `--items-dir PATH` — items root (default `$RG_ITEMS_DIR` or `~/workspace/richmondgeneral/items`)
- `--whatnot-csv PATH` — Whatnot import CSV (default `<items-dir>/rg-inventory/whatnot-import.csv`)
- `--json-out PATH` — report path (default `<items-dir>/../ops/reports/reconcile-latest.json`)

`main()` pulls the live Square catalog (read-only) and loads the Whatnot CSV,
then orchestrates the walk. `run_reconcile(items_dir, square_index,
whatnot_index)` is pure (injected indexes) and unit-testable without network.

## Report shape

```json
{
  "findings": [
    {"sku": "RG-0003", "field": "sold_state", "channel": "square",
     "severity": "critical", "expected": true, "actual": false, "message": "..."}
  ],
  "summary": {"critical": 1, "warning": 0, "info": 0}
}
```

## Acting on drift (separate skills — this one never writes)

| Finding | Fix with |
|---------|----------|
| price divergence | `rg-item-update` (propagate the correct price to all channels) |
| sold-state conflict | `rg-item-mark-sold` (retire listing, kill payment link) |
