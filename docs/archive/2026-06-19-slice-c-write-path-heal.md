# Slice C — Commercial write-path + safe page-side heal

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the *write* side to the item_model system, so commercial changes keep the page and channels in sync (drift prevention), and the reconcile can perform **safe, reversible, page-side** heals. Production channel writes stay gated (dry-run + confirm) and delegate to the existing tools (`safe_batch_reprice.py`, `rg-item-mark-sold`); they are NEVER auto-applied by `--heal`.

**Architecture:** Pure planners are unit-tested; production writes are thin live edges (dry-run default, `--apply` + confirm), not unit-tested; page writes reuse the Slice B `write_page_record` (already tested). Three deliverables: a defined `catalog_state.json` snapshot (retire the stale `catalog_index.jsonl`), a `rg-set-price` write-path (page reference + Square push + flag other channels), and `rg-reconcile --heal` scoped to safe page-side actions.

**Tech Stack:** Python 3.11+ via `uv`; pytest. Builds on `item_model/` (models, page_reader, page_writer, channel_registry, diff, channels/) and `rg-reconcile/scripts/reconcile.py`. Square writes delegate to `rg-item-update/scripts/safe_batch_reprice.py` (`safe_batch_update(client, {variation_id: cents}, dry_run)`).

**Working dir:** `/Users/scottybe/workspace/richmondgeneral/skills` (execution in a worktree).
**Test runner:** `uv run --project plugins/richmondgeneral --extra dev pytest <path> -q`
**Safety invariant:** no task in this slice writes to a production channel without `--apply` AND a printed dry-run first. `--heal` performs only local/page-side actions.

---

## Task C1: `catalog_state.json` snapshot (retire the stale index)

A defined, regenerated snapshot of current reality — replaces the ad-hoc `catalog_index.jsonl` (undefined `t`, no generator).

**Files:** Create `item_model/catalog_state.py`; Test `testing/unit/test_item_model_catalog_state.py`; modify `rg-reconcile/scripts/reconcile.py` to write it.

**Pure builder (unit-tested):**
```python
# catalog_state.py
def build_catalog_state(records_with_obs) -> dict:
    """records_with_obs: list of (PageRecord, [ChannelObservation]). Returns a defined snapshot."""
    items = []
    for rec, obs in records_with_obs:
        items.append({
            "sku": rec.sku,
            "reference_price": rec.reference_price,
            "sold": rec.sold,
            "listed_on": [c.value for c in rec.listed_on],
            "channels": {o.channel.value: {"present": o.present, "price": o.price, "sold": o.sold}
                         for o in obs},
        })
    items.sort(key=lambda i: i["sku"])
    return {"item_count": len(items), "items": items}
```

**Tests:** a 2-item input produces sorted items with the right derived fields; empty input → `item_count: 0`. (No timestamp in the builder — the CLI stamps the file mtime; keep the builder pure/deterministic.)

**CLI wiring:** in `reconcile.py main()`, after building the indexes and the report, also build `catalog_state` (reuse the page records + observations the run already computes — refactor `run_reconcile` to optionally return them, or recompute) and write it to `Path(items_dir).parent / "catalog_state.json"`. Commit.

---

## Task C2: `rg-set-price` write-path (page reference + Square push + flag others)

The single command to reprice an item so the page and Square never drift. Page edit reuses tested `write_page_record`; the Square push delegates to `safe_batch_reprice` and is dry-run unless `--apply`.

**Files:** Create `item_model/write_path.py` (pure planner) + `rg-reconcile/scripts/set_price.py` (CLI, lives with reconcile or in a new `rg-item-update` script — put it in `rg-reconcile/scripts/` to reuse the item_model import bootstrap). Tests: `testing/unit/test_item_model_write_path.py`.

**Pure planner (unit-tested):**
```python
# write_path.py
def plan_channel_pushes(page, channels_registry: dict, new_price: float) -> list[dict]:
    """Which channels need a price push for a new reference price.
    Square (if listed AND registry has square.variation_id) -> an actionable push with the
    variation_id + cents. Other listed channels (whatnot/ebay/marketplace) -> a 'manual' note
    (no API write-path here). Channels not listed_on are skipped."""
    pushes = []
    cents = round(new_price * 100)
    for ch in page.listed_on:
        if ch.value == "square":
            vid = (channels_registry.get("square") or {}).get("variation_id")
            if vid:
                pushes.append({"channel": "square", "mode": "api",
                               "variation_id": vid, "amount_cents": cents})
            else:
                pushes.append({"channel": "square", "mode": "manual",
                               "reason": "no variation_id in registry"})
        else:
            pushes.append({"channel": ch.value, "mode": "manual"})
    return pushes
```

**Tests:** square-listed with variation_id → one `api` push with correct cents; square-listed without variation_id → `manual`; whatnot-listed → `manual`; channel not in listed_on → absent.

**CLI `set_price.py SKU PRICE [--items-dir ...] [--apply]`:**
1. `read_page_record(item_dir)`; set `reference_price = PRICE`; `write_page_record(item_dir, rec)` (page reference updated — always done; local/safe).
2. `plan_channel_pushes(rec, registry, PRICE)`; print the plan.
3. For `api` pushes: dry-run prints "would set <sku>/<variation_id> -> $PRICE"; with `--apply`, call `safe_batch_update(client, {variation_id: cents}, dry_run=not apply)` (resolve token like the other scripts). `manual` pushes are printed as a checklist ("update PRICE on <channel> by hand — Marketplace via computer-use").
4. Print a summary. Read-only/page-only unless `--apply`.

Commit. (Per CLAUDE.md, repricing must hit every channel the item is on — this command does Square automatically and surfaces the rest as an explicit manual checklist.)

---

## Task C3: `rg-reconcile --heal` (safe, page-side only) + verify + doc

**Files:** modify `rg-reconcile/scripts/reconcile.py`; extend `testing/unit/test_reconcile_run.py`.

**`--heal` behavior (safe subset ONLY):**
- Always: regenerate `catalog_state.json` (from C1).
- For each finding, print **guidance** routing to the right confirmed tool — it does NOT auto-apply:
  - `price` WARNING → "run `rg-set-price <sku> <ref>` to push, or record the channel price as intended on the page."
  - `sold_state` CRITICAL → "run `rg-item-mark-sold <sku>` (propagates sold + deletes the payment link)."
  - `presence` INFO → "verify the listing on <channel>."
- NO production channel writes. NO auto-record-intended (that's an operator decision via the write-path). `--heal` is safe to run anytime.

**Tests:** `run_reconcile`/heal path emits guidance lines per finding and writes catalog_state.json; assert the snapshot file is produced and no channel write is attempted (inject fakes).

**Verify:** full unit suite green; live read-only smoke still 0 findings + confirm `catalog_state.json` is written and well-formed. **Update the design doc §7** to mark Slice C done (write-path + safe heal) and note the deferred bits (auto-record-intended, full production heal = future). Commit.

---

## Done criteria
- `catalog_state.json` generated from live reality (stale `catalog_index.jsonl` retired/replaced).
- `rg-set-price` updates the page reference + pushes Square (dry-run+confirm) + flags other channels manual — one command, no drift.
- `rg-reconcile --heal` does only safe page-side actions (snapshot + guidance); production writes stay in `safe_batch_reprice` / `rg-item-mark-sold`.
- Full suite green; live smoke still 0 findings.

## Deferred (future)
- Auto-record-intended on operator confirmation; full production auto-heal (C2); a Whatnot CSV write-back in `rg-set-price`; reconcile consuming registry platform IDs to target lookups.
