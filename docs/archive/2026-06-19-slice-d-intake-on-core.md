# Slice D (part 2) — Intake on the core + item-attribute schema

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the remaining half of Phase 1's "intake is reliable" outcome — make intake write the canonical item schema through the tested `item_model` writer, add the item-attribute fields reconciles keep needing, sync the cache before pricing, and stage scratch safely. (The SKU-allocation half is a separate, parallel branch — see *Coordination* below.)

**Architecture:** The page (`label.json`) stays the spine; its `channels` registry is the per-channel state record. Today `intake_to_item.stub_label()` writes `label.json` directly and the rg-full-auto phases (`process_batch.py`) are agent-driven stubs that hand-edit channel state. This slice (a) extends the intake stub + a pure `compute_oversize` helper with the attribute fields, (b) adds a `square_cache_sync` pricing preflight, (c) moves extraction scratch out of the item folder, and (d) routes channel-status transitions through a small write-path over the Slice-B `page_writer`, so intake stops hand-editing the registry. Pure helpers are unit-tested; the one live edge (cache sync) is a thin wrapper.

**Tech Stack:** Python 3.11+ via `uv`; `pytest` with dependency-injection fakes (no `mock.patch`). Builds on `item_model/` (`page_reader`, `page_writer`, `channel_registry`) and `photos-library/scripts/intake_to_item.py`.

**Reference design:** `docs/plans/2026-06-18-richmondgeneral-monorepo-design.md` §7 (Slice D). Sources: the 2026-06-19 RG-0009, RG-0028/0029, RG-0030 postmortems under `ops/reports/`.

---

## Conventions (read once)

- **Repo root for this work:** `/Users/scottybe/workspace/richmondgeneral/skills/.worktrees/slice-d-intake-on-core` (this worktree; branch `feat/slice-d-intake-on-core`, based on `feat/sku-authority`).
- **Module paths:**
  - item-model core: `plugins/richmondgeneral/skills/item-model-core/lib/item_model/`
  - intake: `plugins/richmondgeneral/skills/photos-library/scripts/intake_to_item.py`
  - orchestrator: `plugins/richmondgeneral/skills/rg-full-auto/scripts/process_batch.py`
  - tests: `testing/unit/` (the repo `conftest.py` already puts `item-model-core/lib` and `photos-library/scripts` on `sys.path`, so `from item_model... import` and `import intake_to_item` work with no path hacks).
- **Test runner (run from the repo root above):**
  ```bash
  uv run --project plugins/richmondgeneral python -m pytest testing/unit/ -q
  ```
- **Commit style:** conventional commits, scope `intake-core`. Commit after each task. End every commit message with the trailer:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

> ⚠️ **Coordination — `process_batch.py` overlaps the SKU branch.** `feat/sku-allocation` (the parallel SKU-authority work) rewrites `_default_next_sku` / the orchestrator's `next_sku`. This slice does **not** touch SKU allocation. Keep edits here to the *schema*, *cache-sync*, *scratch*, and *channel-status* surfaces; rebase onto the SKU branch (or resolve the small `process_batch.py` overlap) at merge time. Don't re-implement allocation.

---

## Task 1: `compute_oversize` pure helper (box dim > 24 in)

A confirmed maker's mark or a 26" box materially changes shipping economics (RG-0009: 26" length → oversize surcharge). Make the rule a pure, tested function so intake and the pricing report agree.

**Files:**
- Create: `plugins/richmondgeneral/skills/item-model-core/lib/item_model/measurements.py`
- Test: `testing/unit/test_item_model_measurements.py`

**Step 1 — Write the failing test:**

```python
# testing/unit/test_item_model_measurements.py
from item_model.measurements import compute_oversize, OVERSIZE_THRESHOLD_IN

def test_threshold_is_24():
    assert OVERSIZE_THRESHOLD_IN == 24.0

def test_no_dims_is_not_oversize():
    assert compute_oversize(None) is False
    assert compute_oversize({}) is False

def test_long_side_over_24_is_oversize():
    assert compute_oversize({"l": 26, "w": 12, "h": 7}) is True   # RG-0009 box

def test_all_within_24_is_not_oversize():
    assert compute_oversize({"l": 18, "w": 11, "h": 7}) is False

def test_exactly_24_is_not_oversize():
    assert compute_oversize({"l": 24, "w": 24, "h": 24}) is False  # strictly greater

def test_accepts_list_form_and_strings():
    assert compute_oversize([26, 12, 7]) is True
    assert compute_oversize({"l": "26", "w": "12", "h": "7"}) is True
```

**Step 2 — Run, expect fail:** `ModuleNotFoundError: No module named 'item_model.measurements'`.

**Step 3 — Implement:**

```python
# item_model/measurements.py
from __future__ import annotations
from typing import Optional, Union

OVERSIZE_THRESHOLD_IN = 24.0  # any single box dimension strictly greater => oversize

def _dims(box) -> list[float]:
    if box is None:
        return []
    vals = box.values() if isinstance(box, dict) else box
    out = []
    for v in vals:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out

def compute_oversize(box: Optional[Union[dict, list]]) -> bool:
    """True if any box dimension (inches) is strictly greater than 24."""
    return any(d > OVERSIZE_THRESHOLD_IN for d in _dims(box))
```

**Step 4 — Run, expect pass:** 6 passed.

**Step 5 — Commit:** `feat(intake-core): compute_oversize helper (box dim > 24in)`.

---

## Task 2: Item-attribute fields in the intake stub

Promote the reconcile-surfaced fields (RG-0009: `eye_color`, `measurements_in`, `buyer_questions[]`; oversize) into `stub_label()` so every new item carries them and reconciles are uniform.

**Files:**
- Modify: `plugins/richmondgeneral/skills/photos-library/scripts/intake_to_item.py` (`stub_label`)
- Test: `testing/unit/test_intake_to_item_stub.py`

**Step 1 — Write the failing test:**

```python
# testing/unit/test_intake_to_item_stub.py
import intake_to_item

def test_stub_has_attribute_fields():
    s = intake_to_item.stub_label("RG-0099")
    assert s["sku"] == "RG-0099"
    # new item-attribute fields, blank/defaults at stub time
    assert s["eye_color"] == ""
    assert s["measurements_in"] == {}          # filled during intake
    assert s["buyer_questions"] == []
    assert s["oversize"] is False
    # existing canonical schema preserved
    assert s["state"] == "Intake"
    assert set(s["channels"]) >= {"github_page", "square", "ebay", "whatnot", "marketplace"}
```

**Step 2 — Run, expect fail:** `KeyError: 'eye_color'`.

**Step 3 — Implement:** in `stub_label`, add to the returned dict (after `condition_notes`):
```python
        "eye_color": "",
        "measurements_in": {},     # {"l":.., "w":.., "h":..} when known; drives oversize
        "buyer_questions": [],     # [{"q":.., "a":.., "posted_to":[..]}]
        "oversize": False,         # recompute from measurements_in via compute_oversize
```

**Step 4 — Run, expect pass.**

**Step 5 — Commit:** `feat(intake-core): stub carries eye_color/measurements_in/buyer_questions/oversize`.

> Note: `oversize` stays `False` at stub time (no dims yet). It is recomputed when `measurements_in` is filled — see Task 5 (the channel-status / page-write path recomputes it) and the reconcile, which should surface a stale `oversize` as a finding.

---

## Task 3: `square_cache_sync` pricing preflight

RG-0030 priced against a stale cache ($75 vs the real $45). Make a cache sync a Phase-0 precondition for any pricing/SKU read so stale data can't mislead.

**Files:**
- Create: `plugins/richmondgeneral/skills/rg-full-auto/scripts/pricing_preflight.py` (thin wrapper)
- Modify: `plugins/richmondgeneral/skills/rg-full-auto/SKILL.md` (Phase 1 appraisal: run preflight first)
- Test: `testing/unit/test_pricing_preflight.py`

**Step 1 — Write the failing test (inject a fake syncer; no network):**

```python
# testing/unit/test_pricing_preflight.py
from pricing_preflight import ensure_fresh_cache

class _FakeSync:
    def __init__(self, ok=True): self.ok, self.calls = ok, 0
    def __call__(self): self.calls += 1; return {"ok": self.ok, "synced": 3}

def test_runs_sync_and_reports():
    f = _FakeSync()
    res = ensure_fresh_cache(sync=f)
    assert f.calls == 1 and res["ok"] is True

def test_surfaces_sync_failure_without_raising():
    res = ensure_fresh_cache(sync=_FakeSync(ok=False))
    assert res["ok"] is False        # caller decides; never silently trust stale cache
```

**Step 2 — Run, expect fail.**

**Step 3 — Implement** `ensure_fresh_cache(sync=None)`: default `sync` resolves the real `square_cache` sync entrypoint lazily (import inside the function so unit tests need no MCP); returns `{"ok": bool, ...}`. No raise — returns status so the appraisal phase can warn and proceed or stop.

**Step 4 — Run, expect pass.** **Step 5 — Commit:** `feat(intake-core): square_cache_sync pricing preflight`.
Then add one line to SKILL.md Phase 1: "Run `pricing_preflight.ensure_fresh_cache()` before reading any cached price." (docs; same commit or a `docs(...)` follow-up.)

---

## Task 4: Stage extraction scratch outside the item folder

RG-0030 RC4: stool scratch contaminated another item's `items/RG-XXXX/`. Stage intake scratch in a sibling `rg-pending/<sku>/` (gitignored), never inside `items/RG-XXXX/` until the SKU is confirmed.

**Files:**
- Modify: `plugins/richmondgeneral/skills/photos-library/scripts/intake_to_item.py` (add `--staging-dir`, default `rg-pending/<sku>` alongside `items/`; `--promote` to move a confirmed set into `items/<sku>/`)
- Modify: `items/.gitignore` (add `rg-pending/`) — *(items repo; commit there separately per the per-repo rule)*
- Test: extend `testing/unit/test_intake_to_item_stub.py`

**Step 1 — Test:** `resolve_staging_dir(items_dir, sku, staging_dir=None)` returns `<items_dir>/../rg-pending/<sku>` by default and the override when given; it never returns a path inside `items/<sku>/`.

**Step 2-4 — TDD** the pure `resolve_staging_dir` (path logic only; no FS writes in the unit test).

**Step 5 — Commit:** `feat(intake-core): stage intake scratch in rg-pending/, not the item folder`.

> The `--promote` move + `items/.gitignore` edit are wiring around the tested path function; verify by a manual dry-run, and commit the `items/.gitignore` change in the **items** repo (explicit path, per the multi-repo rule).

---

## Task 5: Channel-status write-path over `page_writer` (DESIGN-FIRST)

The Slice-B writer sets `listed_on` channels to `status=listed` but does **not** record a *specific* channel's platform IDs (`object_id`, `buy_link`, `item_id`, `url`) or transition one channel at a time — intake still hand-edits the registry for that. This task closes Slice B's deferred "transition channel statuses during intake" item.

**Open design point (resolve in Step 0):** `PageRecord` is a derived *view* without platform IDs, so the per-channel transition must operate at the `label.json` / `channel_registry` level, not via `PageRecord`. Decide between (a) a new `channel_registry.set_channel_status(label, channel, status, **ids)` pure merge helper that the existing `write_page_record` round-trips, or (b) a dedicated `page_writer.write_channel_status(item_dir, channel, status, **ids)`. **Prefer (a)** — a pure registry merge + reuse the tested atomic write — unless reading `page_writer.py` shows a cleaner seam.

**Step 0 — Read** `item_model/page_writer.py` and `item_model/channel_registry.py` to confirm the seam; write the failing test against the chosen API.

**Step 1 — Failing test (pure merge):**
```python
# testing/unit/test_channel_registry_set_status.py
from item_model.channel_registry import set_channel_status

def test_sets_status_and_ids_preserving_others():
    label = {"sku":"RG-1","channels":{"square":{"status":"pending","object_id":None},
                                       "ebay":{"status":"not_listed"}}}
    out = set_channel_status(label, "square", "listed", object_id="ABC", buy_link="sq.link/x")
    assert out["channels"]["square"] == {"status":"listed","object_id":"ABC","buy_link":"sq.link/x"}
    assert out["channels"]["ebay"] == {"status":"not_listed"}     # untouched

def test_never_downgrades_a_sold_channel():
    label = {"sku":"RG-1","channels":{"square":{"status":"sold"}}}
    out = set_channel_status(label, "square", "listed")
    assert out["channels"]["square"]["status"] == "sold"          # sold is sticky
```

**Steps 2-4 — TDD** `set_channel_status` (merge-preserving; sold is sticky — mirror `page_writer`'s "never downgrade a sold channel"). Add a thin CLI `rg-set-channel-status SKU CHANNEL STATUS [--object-id ..] [--buy-link ..]` that reads label.json, applies the helper, recomputes `oversize` from `measurements_in` (Task 1), and writes atomically (reuse `page_writer`'s tmp→rename).

**Step 5 — Commit:** `feat(intake-core): channel-status write-path (set status + platform IDs via the registry)`.

---

## Verify + finish

- Full unit suite green: `uv run --project plugins/richmondgeneral python -m pytest testing/unit/ -q` (prior tests + the new ones).
- Live read-only smoke: `rg-reconcile` over real `items/` still **0 findings** (these changes are additive to the stub schema and don't list anything).
- Update `docs/plans/2026-06-18-richmondgeneral-monorepo-design.md` §7: mark Slice D's intake-on-core half **DONE** (schema + cache-sync + scratch + channel-status write-path), leaving SKU allocation to `feat/sku-allocation`.
- **Finish the branch:** use superpowers:finishing-a-development-branch (merge to `main` / PR per preference). Coordinate the `process_batch.py` overlap with `feat/sku-allocation` before merge.

## Done criteria
- `compute_oversize` + the attribute fields land in the intake stub; `oversize` recomputes from `measurements_in`.
- Pricing reads run behind a cache-sync preflight.
- Intake scratch stages in `rg-pending/`, never inside `items/RG-XXXX/`.
- A channel's status + platform IDs are set through a tested registry merge (intake stops hand-editing the registry).
- Full suite green; live smoke still 0 findings.

## Deferred (not this slice)
- SKU allocation (the `feat/sku-allocation` branch — `sku_authority.py`).
- Auto-promoting `rg-pending/` → `items/` inside `process_batch.py` phases (this slice ships the path helper + manual `--promote`).
- eBay/Marketplace API write-paths (separate channel-adapter work; see §9 operational backlog).
