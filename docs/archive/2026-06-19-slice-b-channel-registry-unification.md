# Slice B — Unify `item_model` on the channels registry

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the Slice A `item_model` core derive its channel state from the project's established **`channels` registry** (CLAUDE.md operating rule) instead of the parallel `listed_on` field invented in Slice A — so intake and the core speak ONE schema. Add a writer that maintains the registry. Define the canonical channel-status vocabulary the derivation needs (it doesn't exist in code yet).

**Architecture:** The page (`label.json`) is the spine. Its `channels` registry is the single per-channel state record (status + platform IDs — the upsert idempotency key). `item_model.PageRecord.listed_on` becomes a **derived view** of that registry; `sold` unifies across its sources; `intended_channel_prices` stays a distinct new field. Everything is backward-compatible: legacy minimal `label.json` (no registry) → empty `listed_on` → reconcile dormant (today's behavior preserved).

**Tech Stack:** Python 3.11+ via `uv`; pytest. Builds on `plugins/richmondgeneral/skills/item-model-core/lib/item_model/`.

**Working dir for commands:** `/Users/scottybe/workspace/richmondgeneral/skills` (execution happens in a worktree — see below).
**Test runner:** `uv run --project plugins/richmondgeneral --extra dev pytest <path> -q`

---

## Canonical schema (the scoping decision this slice locks in)

`label.json` (extending the existing intake stub + CLAUDE.md rule):

- **`state`** (item lifecycle, optional): `Acquired | In Intake | Priced | Listed | Sold | Archived`. Absent ⇒ legacy/unknown.
- **`channels`**: `{ "<chan>": { "status": <str>, ...platform ids } }`, `<chan> ∈ {square, whatnot, ebay, marketplace, github_page}`.
- **Per-channel `status` vocabulary (canonical):** `not_listed | pending | listed | sold | ended`.
- **`intended_channel_prices`** (optional, top-level): `{ "<chan>": <float> }` — distinct new concept, NOT in the registry.

**Derivation rules the core applies (the heart of this slice):**
- `LISTED_STATUSES = {"listed", "active", "live"}` (canonical `listed`; `active`/`live` accepted as aliases).
- `listed_on` = registry channels **excluding `github_page`** whose `status ∈ LISTED_STATUSES`. If there's no `channels` key, fall back to an explicit top-level `listed_on` array (Slice A behavior), else empty.
- `sold` = `True` if **any** of: `status.json` `status == "sold"`; item `state ∈ {Sold, Archived}`; any channel `status == "sold"`.
- `intended_channel_prices` unchanged (explicit top-level field).

Today's stubs (`not_listed`/`pending`) ⇒ not listed ⇒ `listed_on` empty ⇒ reconcile stays dormant — so this is forward-looking and safe.

---

## Task B1: registry helpers + reader derivation

**Files:**
- Create: `.../item-model-core/lib/item_model/channel_registry.py`
- Modify: `.../item-model-core/lib/item_model/page_reader.py`
- Test: `testing/unit/test_item_model_channel_registry.py`, extend `testing/unit/test_item_model_page_reader.py`

**Step 1 — failing tests** (`test_item_model_channel_registry.py`):

```python
from item_model.channel_registry import (
    REGISTRY_CHANNEL_KEYS, LISTED_STATUSES, listed_on_from_registry, sold_from_label,
)
from item_model.models import Channel

def test_registry_keys_map_sales_channels_only():
    assert REGISTRY_CHANNEL_KEYS["square"] is Channel.SQUARE
    assert REGISTRY_CHANNEL_KEYS["whatnot"] is Channel.WHATNOT
    assert "github_page" not in REGISTRY_CHANNEL_KEYS  # the page, not a sales channel

def test_listed_on_derives_from_listed_status():
    channels = {
        "square": {"status": "listed", "object_id": "X"},
        "whatnot": {"status": "not_listed"},
        "github_page": {"status": "listed"},   # excluded
    }
    assert listed_on_from_registry(channels) == [Channel.SQUARE]

def test_listed_status_aliases_and_case_insensitive():
    channels = {"square": {"status": "Active"}, "ebay": {"status": "LIVE"}}
    got = set(listed_on_from_registry(channels))
    assert got == {Channel.SQUARE, Channel.EBAY}

def test_sold_from_state():
    assert sold_from_label({"state": "Sold"}, status_json=None) is True
    assert sold_from_label({"state": "Archived"}, status_json=None) is True
    assert sold_from_label({"state": "Listed"}, status_json=None) is False

def test_sold_from_channel_status():
    assert sold_from_label({"channels": {"square": {"status": "sold"}}}, status_json=None) is True

def test_sold_from_status_json_wins():
    assert sold_from_label({}, status_json={"status": "sold"}) is True
```

Extend `test_item_model_page_reader.py`:

```python
def test_reader_derives_listed_on_from_channels_registry(tmp_path):
    _write_item(tmp_path, "RG-0100", {
        "sku": "RG-0100", "price": "10.00",
        "channels": {"square": {"status": "listed"}, "whatnot": {"status": "not_listed"}},
    })
    rec = read_page_record(tmp_path / "RG-0100")
    assert rec.listed_on == [Channel.SQUARE]

def test_reader_state_sold_sets_sold(tmp_path):
    _write_item(tmp_path, "RG-0101", {"sku": "RG-0101", "price": "5.00", "state": "Sold"})
    assert read_page_record(tmp_path / "RG-0101").sold is True

def test_reader_legacy_listed_on_still_honored(tmp_path):
    # no channels registry → explicit listed_on still works (back-compat)
    _write_item(tmp_path, "RG-0102", {"sku": "RG-0102", "price": "5.00", "listed_on": ["square"]})
    assert read_page_record(tmp_path / "RG-0102").listed_on == [Channel.SQUARE]
```

**Step 2 — run, expect fail** (module/behavior missing).

**Step 3 — implement** `channel_registry.py`:

```python
from __future__ import annotations
from typing import Dict, List, Optional
from .models import Channel

# Registry channel keys that are SALES channels (github_page is the page itself).
REGISTRY_CHANNEL_KEYS: Dict[str, Channel] = {
    "square": Channel.SQUARE,
    "whatnot": Channel.WHATNOT,
    "ebay": Channel.EBAY,
    "marketplace": Channel.MARKETPLACE,
}
LISTED_STATUSES = {"listed", "active", "live"}   # canonical "listed"; aliases accepted
_SOLD_STATES = {"sold", "archived"}


def listed_on_from_registry(channels: dict) -> List[Channel]:
    """Channels (excluding github_page) whose status marks them actively listed."""
    out: List[Channel] = []
    for key, ch in REGISTRY_CHANNEL_KEYS.items():
        entry = channels.get(key)
        if isinstance(entry, dict) and str(entry.get("status", "")).strip().lower() in LISTED_STATUSES:
            out.append(ch)
    return out


def sold_from_label(label: dict, status_json: Optional[dict]) -> bool:
    """Unified sold-state: status.json, OR item state in {Sold,Archived}, OR any channel status 'sold'."""
    if status_json and str(status_json.get("status", "")).strip().lower() == "sold":
        return True
    if str(label.get("state", "")).strip().lower() in _SOLD_STATES:
        return True
    for entry in (label.get("channels") or {}).values():
        if isinstance(entry, dict) and str(entry.get("status", "")).strip().lower() == "sold":
            return True
    return False
```

Then rewrite `page_reader.read_page_record` to use them: load `label.json`; load `status.json` (if present) as a dict; `sold = sold_from_label(label, status_json)`; `listed_on = listed_on_from_registry(label["channels"]) if "channels" in label else [Channel(c) for c in label.get("listed_on", [])]`; `intended_channel_prices` unchanged. Keep `reference_price = float(label["price"])`.

**Step 4 — run, expect pass.** **Step 5 — commit.**

---

## Task B2: page writer (maintain the registry)

**Files:** Create `.../item-model-core/lib/item_model/page_writer.py`; Test `testing/unit/test_item_model_page_writer.py`.

**Behavior:** `write_page_record(item_dir, record, *, preserve_extras=True) -> None` — writes `label.json` atomically (tmp→rename, like `ItemState.save`). Because `PageRecord` is a *view* (it has `listed_on` but not platform IDs), the writer **merges**: it preserves all existing keys (`product_name`, `condition`, `qr_code_url`, existing `channels` IDs, `state`, …), updates `sku`/`price`(`reference_price` as `"%.2f"`)/`intended_channel_prices`, and sets each `listed_on` channel's `channels.<key>.status = "listed"` (creating the entry if absent, preserving its other fields). It does NOT downgrade channels not in `listed_on` (avoids clobbering `sold`/`ended`). Round-trip: `read_page_record(write_page_record(rec))` reproduces `sku`, `reference_price`, `listed_on`, `intended_channel_prices`.

**Tests:** minimal write (no existing file) sets `channels.square.status=listed` for `listed_on=[SQUARE]`; preserve-extras keeps `product_name`/existing `square.object_id`; round-trip read==write for the derived fields; writing does not flip an existing `whatnot.status="sold"` to listed. TDD (fail→implement→pass), commit.

---

## Task B3: verify + document

- Full unit suite: `uv run --project plugins/richmondgeneral --extra dev pytest testing/unit/ -q` — expect all green (prior 226 + new).
- Live read-only smoke: `set -a; . /Users/scottybe/workspace/richmondgeneral/.env; set +a; uv run --project plugins/richmondgeneral python plugins/richmondgeneral/skills/rg-reconcile/scripts/reconcile.py --items-dir /Users/scottybe/workspace/richmondgeneral/items` — expect **0 findings still** (real items are legacy minimal schema ⇒ listed_on empty ⇒ presence dormant). Confirms back-compat.
- Update `docs/plans/2026-06-18-richmondgeneral-monorepo-design.md` §3: record that `listed_on` is DERIVED from the `channels` registry (not a separate authored field), the canonical status vocabulary, and the unified `sold` sources. Commit.

---

## Done criteria
- `item_model` derives `listed_on` + `sold` from the established `channels` registry (canonical vocabulary defined), back-compatible with legacy minimal `label.json`.
- A writer maintains the registry (merge-preserving IDs/extras).
- Full suite green; live smoke still 0 findings.
- Canonical channel schema documented in the design doc.

## Deferred (not this slice)
- Wiring `process_batch.py`/`intake_to_item.py` to CALL `write_page_record` and to transition channel statuses to `listed` during intake (that's the intake-integration + write-path, Slice C — and it's your actively-edited code).
- Reconcile consuming per-channel platform IDs from the registry to target lookups.
