# RG-XXXX SKU Allocation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the race-prone filesystem-glob SKU allocator with an atomic, multi-machine-safe allocator backed by a single Square sentinel catalog object using Square's catalog-object version compare-and-set.

**Architecture:** A new `sku_authority.py` module splits into (a) **pure core** — `allocate_sku(store)` / `bootstrap(store)` / parse-format helpers, tested with an in-memory fake — and (b) an **I/O adapter** `SquareCounterStore` that talks to the live Square catalog via the official SDK (`search_items` → `batch_get` → `batch_upsert` carrying the object `version`). A hidden `CatalogItem` (stable variation SKU `__RG_SKU_COUNTER__`, value N encoded in its name `RG-SKU-COUNTER:NNNN`) is the authority. `allocate_sku` does reconcile-then-CAS-increment; version conflicts retry; Square errors hard-fail (no local fallback); a missing sentinel self-heals via `bootstrap`.

**Tech Stack:** Python 3.11+, official Square SDK (`squareup>=44.0.1`, already a dependency), `uv` for the env, `pytest` with dependency-injection-style fakes (no `@mock.patch`). Token via `item_model.instance.resolve_square_token` (env→Keychain→.env).

**Design doc:** `docs/plans/2026-06-19-sku-allocation-design.md`

---

## Conventions (read once)

- **Repo root for this work:** `/Users/scottybe/workspace/richmondgeneral/skills`
- **Module path:** `plugins/richmondgeneral/skills/rg-full-auto/scripts/sku_authority.py`
- **Test path:** `testing/unit/test_sku_authority.py` (the repo `conftest.py` already puts `rg-full-auto/scripts` and `item-model-core/lib` on `sys.path`, so `from sku_authority import ...` works with no path hacks).
- **Run tests (locked & verified — 23 existing tests pass in 0.11s):**
  ```bash
  cd /Users/scottybe/workspace/richmondgeneral/skills
  uv run --project plugins/richmondgeneral python -m pytest testing/unit/test_sku_authority.py -v
  ```
- **Commit style:** conventional commits, scope `sku-authority`. Commit after each task. End every commit message with the trailer:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- **Branch:** `skills` is on `main`. Before Task 1, create a feature branch: `git checkout -b feat/sku-authority`.
- **Worktree (optional):** for isolation, `git worktree add ../skills-sku-authority feat/sku-authority` and work there.

> ⚠️ All edits land in the **source** repo (`plugins/richmondgeneral/skills/rg-full-auto/`). The executing plugin lives at `~/.claude/plugins/cache/richmondgeneral/...`; Task 12 rebuilds it. Until then, runtime behavior is unchanged.

---

## Task 1: Exceptions + pure parse/format helpers

**Files:**
- Create: `plugins/richmondgeneral/skills/rg-full-auto/scripts/sku_authority.py`
- Test: `testing/unit/test_sku_authority.py`

**Step 1 — Write the failing test:**

```python
# testing/unit/test_sku_authority.py
import pytest
from sku_authority import (
    format_sku, format_counter_name, parse_counter_n, parse_rg_n,
    SkuAllocationError,
)

def test_format_sku_zero_pads():
    assert format_sku(31) == "RG-0031"
    assert format_sku(7) == "RG-0007"

def test_format_counter_name_roundtrips():
    assert parse_counter_n(format_counter_name(30)) == 30

def test_parse_rg_n_matches_only_real_skus():
    assert parse_rg_n("RG-0030") == 30
    assert parse_rg_n("__RG_SKU_COUNTER__") is None      # sentinel never counts
    assert parse_rg_n("RG-SKU-COUNTER:0030") is None     # counter name never counts
    assert parse_rg_n("RG-0030-test") is None

def test_parse_counter_n_rejects_garbage():
    with pytest.raises(SkuAllocationError):
        parse_counter_n("not-a-counter")
```

**Step 2 — Run, expect failure:**
```bash
uv run --project plugins/richmondgeneral python -m pytest testing/unit/test_sku_authority.py -v
```
Expected: collection/import error (`ModuleNotFoundError: sku_authority`).

**Step 3 — Implement the module's pure layer:**

```python
# plugins/richmondgeneral/skills/rg-full-auto/scripts/sku_authority.py
"""Atomic RG-XXXX SKU allocation backed by a single hidden Square sentinel object.

Square is the allocation authority: a hidden CatalogItem (variation SKU
`__RG_SKU_COUNTER__`) stores the last-allocated integer N in its name
(`RG-SKU-COUNTER:NNNN`). Allocation increments N via Square catalog-object version
compare-and-set, so independent multi-machine writers never collide. Unique-only
(gaps OK); reconcile-then-CAS folded into each allocate.

Design: docs/plans/2026-06-19-sku-allocation-design.md
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

SENTINEL_SKU = "__RG_SKU_COUNTER__"        # stable variation SKU used to locate the sentinel
COUNTER_NAME_PREFIX = "RG-SKU-COUNTER:"    # item name holds N as RG-SKU-COUNTER:NNNN
_SKU_RE = re.compile(r"^RG-(\d+)$")        # real item SKUs only
DEFAULT_MAX_RETRIES = 8


class SkuAllocationError(RuntimeError):
    """Allocation could not complete (retries exhausted or malformed counter)."""


class SquareUnavailable(RuntimeError):
    """Square could not be reached/authenticated — allocation must hard-fail."""


def format_sku(n: int) -> str:
    return f"RG-{n:04d}"


def format_counter_name(n: int) -> str:
    return f"{COUNTER_NAME_PREFIX}{n:04d}"


def parse_counter_n(name: str) -> int:
    if name and name.startswith(COUNTER_NAME_PREFIX):
        tail = name[len(COUNTER_NAME_PREFIX):]
        if tail.isdigit():
            return int(tail)
    raise SkuAllocationError(f"counter name not parseable: {name!r}")


def parse_rg_n(sku: Optional[str]) -> Optional[int]:
    m = _SKU_RE.match(sku or "")
    return int(m.group(1)) if m else None
```

**Step 4 — Run, expect pass:**
```bash
uv run --project plugins/richmondgeneral python -m pytest testing/unit/test_sku_authority.py -v
```
Expected: 4 passed.

**Step 5 — Commit:**
```bash
git add plugins/richmondgeneral/skills/rg-full-auto/scripts/sku_authority.py testing/unit/test_sku_authority.py
git commit -m "feat(sku-authority): pure parse/format helpers + exceptions"
```

---

## Task 2: Store seam + in-memory fake + `allocate_sku` clean path

The repo convention is to test pure logic against an injected fake (cf. `test_item_model_square_reader.py`). We define the `CounterStore` seam and a `FakeStore` that enforces version-CAS, then the clean allocation path.

**Files:**
- Modify: `sku_authority.py` (add `CounterState`, `CounterStore`, `allocate_sku`)
- Modify: `testing/unit/test_sku_authority.py` (add `FakeStore` + clean-path test)

**Step 1 — Write the failing test (add to the test file):**

```python
from sku_authority import allocate_sku, bootstrap, CounterState, SquareUnavailable

class FakeStore:
    """In-memory CounterStore with version-CAS semantics, for tests."""
    def __init__(self, n=None, rg_max=0, unavailable=False, always_conflict=False):
        self.n = n
        self.version = 1 if n is not None else None
        self.rg_max = rg_max
        self.unavailable = unavailable
        self.always_conflict = always_conflict
        self.conflict_once = False
        self.create_calls = 0
        self.cas_calls = 0

    def read(self) -> CounterState:
        if self.unavailable:
            raise SquareUnavailable("fake down")
        return CounterState(n=self.n, version=self.version, rg_max=self.rg_max)

    def create(self, n: int) -> None:
        self.create_calls += 1
        self.n = n
        self.version = 1

    def cas_set(self, expected_version: int, n: int) -> bool:
        self.cas_calls += 1
        if self.always_conflict:
            self.version += 1
            return False
        if self.conflict_once:
            self.conflict_once = False
            self.version += 1          # simulate another writer's commit
            return False
        if expected_version != self.version:
            return False
        self.n = n
        self.version += 1
        return True


def test_allocate_clean_path_returns_next_and_increments():
    store = FakeStore(n=30, rg_max=30)
    assert allocate_sku(store) == "RG-0031"
    assert store.n == 31
    assert store.cas_calls == 1        # no double-increment
```

**Step 2 — Run, expect failure:** `ImportError: cannot import name 'allocate_sku'`.

**Step 3 — Implement (append to `sku_authority.py`):**

```python
@dataclass(frozen=True)
class CounterState:
    n: Optional[int]        # current counter value; None if sentinel absent
    version: Optional[int]  # sentinel object version for CAS; None if absent
    rg_max: int             # max RG-#### across the live catalog (0 if none)


class CounterStore(Protocol):
    def read(self) -> CounterState: ...
    def create(self, n: int) -> None: ...
    def cas_set(self, expected_version: int, n: int) -> bool: ...
    # All three raise SquareUnavailable on I/O or auth failure.
    # cas_set returns False on a version conflict (someone else won).


def allocate_sku(store: CounterStore, max_retries: int = DEFAULT_MAX_RETRIES) -> str:
    """Return a fresh RG-XXXX, reserved on Square. Raises on hard failure."""
    for _ in range(max_retries):
        st = store.read()                          # may raise SquareUnavailable -> propagate
        if st.n is None:                           # sentinel missing -> self-heal
            store.create(st.rg_max)
            continue
        candidate = max(st.n, st.rg_max) + 1       # forward-only reconcile
        if store.cas_set(st.version, candidate):   # CAS on sentinel version
            return format_sku(candidate)
        # version conflict -> retry
    raise SkuAllocationError(f"could not allocate after {max_retries} attempts")


def bootstrap(store: CounterStore, fs_max: int = 0) -> int:
    """Idempotently ensure the sentinel exists; return its value N."""
    st = store.read()
    if st.n is not None:
        return st.n
    initial = max(st.rg_max, fs_max)
    store.create(initial)
    return initial


def peek(store: CounterStore) -> Optional[int]:
    return store.read().n
```

**Step 4 — Run, expect pass:** 5 passed.

**Step 5 — Commit:**
```bash
git add -A && git commit -m "feat(sku-authority): CounterStore seam + allocate_sku clean path"
```

---

## Task 3: Version-conflict retry

**Step 1 — Test:**
```python
def test_allocate_retries_on_version_conflict():
    store = FakeStore(n=30, rg_max=30)
    store.conflict_once = True          # first CAS loses the race
    assert allocate_sku(store) == "RG-0031"
    assert store.cas_calls == 2         # retried exactly once
```
**Step 2 — Run:** expect PASS already (logic implemented in Task 2). If it fails, fix `allocate_sku`. (This task locks the behavior with a regression test.)
**Steps 3-4:** no code change expected; confirm green.
**Step 5 — Commit:** `test(sku-authority): version-conflict retry regression`.

---

## Task 4: Reconcile-forward (out-of-band Square add)

**Step 1 — Test:**
```python
def test_allocate_reconciles_forward_when_square_is_ahead():
    # Counter says 30, but live catalog already has RG-0050 (hand-added in dashboard).
    store = FakeStore(n=30, rg_max=50)
    assert allocate_sku(store) == "RG-0051"
    assert store.n == 51

def test_allocate_never_goes_backward():
    store = FakeStore(n=99, rg_max=10)
    assert allocate_sku(store) == "RG-0100"
```
**Step 2 — Run:** expect PASS (covered by `max(st.n, st.rg_max)+1`).
**Step 5 — Commit:** `test(sku-authority): forward-only reconcile`.

---

## Task 5: Sentinel-missing self-heal + `bootstrap`

**Step 1 — Test:**
```python
def test_allocate_self_heals_when_sentinel_missing():
    store = FakeStore(n=None, rg_max=30)     # no sentinel yet
    assert allocate_sku(store) == "RG-0031"
    assert store.create_calls == 1

def test_bootstrap_initializes_to_max_of_square_and_fs():
    store = FakeStore(n=None, rg_max=30)
    assert bootstrap(store, fs_max=29) == 30
    assert store.n == 30

def test_bootstrap_is_idempotent_when_present():
    store = FakeStore(n=42, rg_max=42)
    assert bootstrap(store, fs_max=0) == 42
    assert store.create_calls == 0
```
**Step 2 — Run:** expect PASS.
**Step 5 — Commit:** `test(sku-authority): sentinel self-heal + bootstrap`.

---

## Task 6: Retries-exhausted raises; Square-unavailable propagates

**Step 1 — Test:**
```python
def test_allocate_raises_when_retries_exhausted():
    store = FakeStore(n=30, rg_max=30, always_conflict=True)
    with pytest.raises(SkuAllocationError):
        allocate_sku(store, max_retries=3)
    assert store.cas_calls == 3

def test_allocate_hard_fails_when_square_unavailable():
    store = FakeStore(unavailable=True)
    with pytest.raises(SquareUnavailable):     # NO silent local-glob fallback
        allocate_sku(store)
```
**Step 2 — Run:** expect PASS.
**Step 5 — Commit:** `test(sku-authority): exhaustion + hard-fail (no fallback)`.

---

## Task 7: Concurrency simulation (uniqueness under contention)

Real threads against a lock-guarded fake whose `read()` is unlocked (so threads can read the same version) but whose CAS mutation is atomic (mirrors Square). Asserts all SKUs unique.

**Step 1 — Test:**
```python
import threading

class ThreadSafeFakeStore(FakeStore):
    def __init__(self, n, rg_max):
        super().__init__(n=n, rg_max=rg_max)
        self._lock = threading.Lock()
    def cas_set(self, expected_version, n):
        with self._lock:                       # Square serializes the CAS
            if expected_version != self.version:
                return False
            self.n = n
            self.version += 1
            return True

def test_concurrent_allocations_are_unique():
    store = ThreadSafeFakeStore(n=0, rg_max=0)
    results, errors = [], []
    def worker():
        try:
            results.append(allocate_sku(store, max_retries=100))
        except Exception as e:                 # noqa: BLE001
            errors.append(e)
    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert not errors
    assert len(results) == 20
    assert len(set(results)) == 20             # zero collisions
```
**Step 2 — Run:** expect PASS (may exercise several retries internally).
**Step 5 — Commit:** `test(sku-authority): concurrency uniqueness sim`.

---

## Task 8: `SquareCounterStore` adapter (real SDK I/O) + version-conflict detector

Network-touching; **not** unit-tested (covered by the Task 13 sandbox check). Mirrors the verified repo pattern in `rg-item-update/scripts/safe_batch_reprice.py` (fetch via `batch_get` → patch `model_dump` → `batch_upsert` with `version`).

**Files:** Modify `sku_authority.py`.

**Step 1 — Write a thin import/contract test (no network):**
```python
def test_square_store_is_constructible_without_network():
    from sku_authority import SquareCounterStore
    store = SquareCounterStore(client=object())   # inject dummy; no calls made
    assert hasattr(store, "read") and hasattr(store, "cas_set") and hasattr(store, "create")
```

**Step 2 — Run:** expect FAIL (`cannot import name 'SquareCounterStore'`).

**Step 3 — Implement (append to `sku_authority.py`):**

```python
def _is_version_conflict(errors) -> bool:
    for e in errors or []:
        code = getattr(e, "code", None) or (e.get("code") if isinstance(e, dict) else None) or ""
        detail = getattr(e, "detail", None) or (e.get("detail") if isinstance(e, dict) else None) or ""
        if str(code).upper() == "VERSION_MISMATCH" or "version" in str(detail).lower():
            return True
    return False


class SquareCounterStore:
    """CounterStore backed by the live Square catalog via the official SDK.

    Contract: cas_set() must be preceded by read() in the same allocate attempt
    (read() caches the fetched sentinel object whose version cas_set sends back).
    """

    def __init__(self, client=None):
        self._client = client
        self._cached_obj = None

    def _client_or_make(self):
        if self._client is None:
            try:
                from square.client import Square
                from item_model.instance import resolve_square_token
                token = resolve_square_token()
                if not token:
                    raise SquareUnavailable("no Square access token resolved")
                self._client = Square(token=token)
            except SquareUnavailable:
                raise
            except Exception as e:                          # noqa: BLE001
                raise SquareUnavailable(f"cannot construct Square client: {e}") from e
        return self._client

    def _scan(self):
        """One catalog pass -> (sentinel_item_id, sentinel_name, rg_max)."""
        client = self._client_or_make()
        sentinel_id = sentinel_name = None
        rg_max = 0
        cursor = None
        try:
            while True:
                resp = (client.catalog.search_items(cursor=cursor)
                        if cursor else client.catalog.search_items())
                if getattr(resp, "errors", None):
                    raise SquareUnavailable(f"search_items errors: {resp.errors}")
                for item in (getattr(resp, "items", None) or []):
                    data = getattr(item, "item_data", None)
                    if data is None:
                        continue
                    for v in (getattr(data, "variations", None) or []):
                        vd = getattr(v, "item_variation_data", None)
                        sku = getattr(vd, "sku", None) if vd else None
                        if sku == SENTINEL_SKU:
                            sentinel_id, sentinel_name = item.id, getattr(data, "name", None)
                        else:
                            n = parse_rg_n(sku)
                            if n is not None:
                                rg_max = max(rg_max, n)
                cursor = getattr(resp, "cursor", None)
                if not cursor:
                    break
        except SquareUnavailable:
            raise
        except Exception as e:                              # noqa: BLE001
            raise SquareUnavailable(f"catalog scan failed: {e}") from e
        return sentinel_id, sentinel_name, rg_max

    def read(self) -> CounterState:
        sentinel_id, sentinel_name, rg_max = self._scan()
        self._cached_obj = None
        if sentinel_id is None:
            return CounterState(n=None, version=None, rg_max=rg_max)
        client = self._client_or_make()
        try:
            got = client.catalog.batch_get(object_ids=[sentinel_id])
            if getattr(got, "errors", None):
                raise SquareUnavailable(f"batch_get errors: {got.errors}")
            obj = (getattr(got, "objects", None) or [None])[0]
            if obj is None:
                return CounterState(n=None, version=None, rg_max=rg_max)
            self._cached_obj = obj
            return CounterState(n=parse_counter_n(sentinel_name),
                                version=getattr(obj, "version", None), rg_max=rg_max)
        except SquareUnavailable:
            raise
        except Exception as e:                              # noqa: BLE001
            raise SquareUnavailable(f"sentinel fetch failed: {e}") from e

    def cas_set(self, expected_version: int, n: int) -> bool:
        if self._cached_obj is None:
            return False                                    # force a re-read
        client = self._client_or_make()
        d = self._cached_obj.model_dump(mode="json", exclude_none=True)
        d["version"] = expected_version
        d["item_data"]["name"] = format_counter_name(n)
        try:
            r = client.catalog.batch_upsert(
                idempotency_key=str(uuid.uuid4()),          # fresh key: network-retry safe
                batches=[{"objects": [d]}],
            )
            errs = getattr(r, "errors", None)
            if errs:
                return False if _is_version_conflict(errs) else _raise_unavailable(errs)
            return True
        except SquareUnavailable:
            raise
        except Exception as e:                              # noqa: BLE001
            if "version" in str(e).lower():
                return False
            raise SquareUnavailable(f"cas upsert failed: {e}") from e

    def create(self, n: int) -> None:
        client = self._client_or_make()
        existing, _, _ = self._scan()                       # avoid duplicate sentinel
        if existing is not None:
            return
        obj = {
            "type": "ITEM", "id": "#rg-sku-counter", "present_at_all_locations": False,
            "item_data": {
                "name": format_counter_name(n),
                "variations": [{
                    "type": "ITEM_VARIATION", "id": "#rg-sku-counter-var",
                    "present_at_all_locations": False,
                    "item_variation_data": {"sku": SENTINEL_SKU, "pricing_type": "VARIABLE_PRICING"},
                }],
            },
        }
        try:
            r = client.catalog.batch_upsert(
                idempotency_key=f"rg-sku-counter-create-{uuid.uuid4()}",
                batches=[{"objects": [obj]}],
            )
            if getattr(r, "errors", None):
                raise SquareUnavailable(f"counter create errors: {r.errors}")
        except SquareUnavailable:
            raise
        except Exception as e:                              # noqa: BLE001
            raise SquareUnavailable(f"counter create failed: {e}") from e


def _raise_unavailable(errs):
    raise SquareUnavailable(f"catalog upsert errors: {errs}")


def default_next_sku() -> str:
    """Production allocator: construct a live Square-backed store and allocate."""
    return allocate_sku(SquareCounterStore())
```

**Step 4 — Run:** expect 1 new + all prior PASS.

**Step 5 — Commit:** `feat(sku-authority): SquareCounterStore SDK adapter + default_next_sku`.

> **NOTE for executor:** the exact Square version-conflict error code is detected leniently (`VERSION_MISMATCH` or any error mentioning "version"). Confirm the precise code against the Square sandbox in Task 13 and tighten `_is_version_conflict` if needed.

---

## Task 9: Module CLI (bootstrap / peek / allocate) for ops + sandbox use

**Files:** Modify `sku_authority.py` (add `if __name__ == "__main__"`).

**Step 1 — Test (argparse wiring, no network — call with `--help` exit code):**
```python
import subprocess, sys
def test_cli_help_runs():
    # The module must be importable & expose a CLI; --help exits 0.
    import sku_authority, os
    path = sku_authority.__file__
    r = subprocess.run([sys.executable, path, "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "bootstrap" in r.stdout and "peek" in r.stdout
```
**Step 2 — Run:** expect FAIL.
**Step 3 — Implement:**
```python
def _main(argv=None) -> int:
    import argparse, json
    p = argparse.ArgumentParser(description="RG SKU allocation authority (Square-backed).")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("peek", help="print current counter N")
    b = sub.add_parser("bootstrap", help="create sentinel from max(Square, items dir)")
    b.add_argument("--items-dir", default=None)
    sub.add_parser("allocate", help="allocate and print one RG-XXXX (mutates Square!)")
    args = p.parse_args(argv)
    store = SquareCounterStore()
    if args.cmd == "peek":
        print(json.dumps({"n": peek(store)})); return 0
    if args.cmd == "bootstrap":
        fs = 0
        if args.items_dir:
            fs = max([parse_rg_n(c.name) or 0 for c in Path(args.items_dir).glob("RG-*")] or [0])
        print(json.dumps({"n": bootstrap(store, fs_max=fs)})); return 0
    if args.cmd == "allocate":
        print(json.dumps({"sku": allocate_sku(store)})); return 0
    return 2

if __name__ == "__main__":
    raise SystemExit(_main())
```
**Step 4 — Run:** expect PASS.
**Step 5 — Commit:** `feat(sku-authority): bootstrap/peek/allocate CLI`.

---

## Task 10: Wire `process_batch.py` to the authority

**Files:** Modify `plugins/richmondgeneral/skills/rg-full-auto/scripts/process_batch.py`.

**Step 1 — Test (orchestrator uses the authority by default):**
```python
# add to testing/unit/test_process_batch.py
def test_orchestrator_default_next_sku_uses_authority(monkeypatch, tmp_path):
    import process_batch
    monkeypatch.setattr(process_batch, "default_next_sku", lambda: "RG-7777", raising=True)
    orch = process_batch.BatchOrchestrator(items_dir=str(tmp_path), queue_path=str(tmp_path/"q.json"))
    assert orch.next_sku() == "RG-7777"
```
**Step 2 — Run:** expect FAIL (`default_next_sku` not imported in `process_batch`).
**Step 3 — Implement:** at the import block of `process_batch.py` add `from sku_authority import default_next_sku`. Change line ~101 from
`self.next_sku = next_sku or (lambda: _default_next_sku(str(self.items_dir)))`
to
`self.next_sku = next_sku or default_next_sku`.
Leave the old `_default_next_sku` function in place but add a deprecation docstring line: `"""DEPRECATED: superseded by sku_authority.allocate_sku; retained for reference."""`.
**Step 4 — Run:** expect PASS, and re-run the full `test_process_batch.py` (existing 23 still green because they inject `next_sku`).
**Step 5 — Commit:** `feat(sku-authority): process_batch uses Square authority for SKUs`.

---

## Task 11: Remove `process_new_item.py` CWD glob

**Files:** Modify `plugins/richmondgeneral/skills/rg-full-auto/scripts/process_new_item.py` (the `Path('.').glob('RG-*')` near line 77).

**Step 1 — Read** the enclosing function to learn what it returns/consumes.
**Step 2 — Test:** if that function is unit-testable, add a test asserting it delegates to `default_next_sku`; otherwise assert via `monkeypatch` that the glob is gone (grep test):
```python
def test_process_new_item_has_no_cwd_glob():
    import pathlib, process_new_item
    src = pathlib.Path(process_new_item.__file__).read_text()
    assert "glob('RG-*')" not in src and 'glob("RG-*")' not in src
```
**Step 3 — Implement:** replace the glob-based next-SKU block with `from sku_authority import default_next_sku` + `sku = default_next_sku()`.
**Step 4 — Run:** expect PASS.
**Step 5 — Commit:** `fix(sku-authority): drop CWD-relative RG-* glob in process_new_item`.

---

## Task 12: Rewrite SKILL.md Phase 0 (Steps 0.1–0.2)

**Files:** Modify `plugins/richmondgeneral/skills/rg-full-auto/SKILL.md`.

Replace "Step 0.1 Get next SKU from cache" and "Step 0.2 Verify SKU not taken" with:

> **Step 0.1 — Allocate the SKU (authority = Square).** The scripts call
> `sku_authority.allocate_sku()`, which atomically reserves the next `RG-XXXX`
> on Square via the hidden `__RG_SKU_COUNTER__` sentinel (version compare-and-set).
> Do **not** look up the next SKU from the Square cache or by globbing the items
> dir — those are no longer sources of truth for allocation. The returned SKU is
> already reserved; no separate "verify not taken" step is needed. If Square is
> unreachable the call raises and intake stops (by design — no colliding fallback).

No test (docs). **Commit:** `docs(sku-authority): SKILL.md Phase 0 uses allocate_sku`.

---

## Task 13: Bootstrap migration, plugin rebuild, sandbox integration check

**Step 1 — Run the full suite green:**
```bash
cd /Users/scottybe/workspace/richmondgeneral/skills
uv run --project plugins/richmondgeneral python -m pytest testing/unit/test_sku_authority.py testing/unit/test_process_batch.py -v
```
Expected: all PASS.

**Step 2 — Sandbox integration (no prod writes).** Export a **sandbox** token, then:
```bash
SQUARE_ACCESS_TOKEN=<sandbox> uv run --project plugins/richmondgeneral \
  python plugins/richmondgeneral/skills/rg-full-auto/scripts/sku_authority.py bootstrap
# then two concurrent allocate loops; assert zero duplicate SKUs:
SQUARE_ACCESS_TOKEN=<sandbox> uv run --project plugins/richmondgeneral python - <<'PY'
import concurrent.futures as cf, collections
from sku_authority import allocate_sku, SquareCounterStore
def one(_): return allocate_sku(SquareCounterStore())
with cf.ThreadPoolExecutor(max_workers=8) as ex:
    skus = list(ex.map(one, range(40)))
dupes = [s for s,c in collections.Counter(skus).items() if c>1]
print("dupes:", dupes); assert not dupes, dupes
print("OK", sorted(skus)[:5], "...", sorted(skus)[-3:])
PY
```
Confirm in the sandbox dashboard that `__RG_SKU_COUNTER__` is **hidden from all locations/sites**. If the version-conflict code differs from the lenient match, tighten `_is_version_conflict` and re-commit.

**Step 3 — Production bootstrap (one-time, real token):**
```bash
uv run --project plugins/richmondgeneral \
  python plugins/richmondgeneral/skills/rg-full-auto/scripts/sku_authority.py bootstrap \
  --items-dir /Users/scottybe/workspace/richmondgeneral/items
```
Expected JSON: `{"n": 30}` (RG-0030 is current max) → first real allocate returns **RG-0031**.

**Step 4 — Rebuild the plugin so the executing cache matches source** (the cache at `~/.claude/plugins/cache/richmondgeneral/...` is what actually runs). Use the `skill-manager` packaging/version-bump flow (or reinstall the plugin from the `skills` repo). Verify:
```bash
grep -n "def allocate_sku" ~/.claude/plugins/cache/richmondgeneral/richmondgeneral/1.0.0/skills/rg-full-auto/scripts/sku_authority.py
```
Expected: the file exists in the cache.

**Step 5 — Finish the branch.** Use superpowers:finishing-a-development-branch (merge to `main` / open PR per your preference) and push.

---

## Done criteria

- `test_sku_authority.py`: all unit + concurrency tests green; `test_process_batch.py` still green.
- Sandbox: 40 concurrent allocations, zero duplicates; sentinel hidden everywhere.
- Prod sentinel bootstrapped at N=30; next allocate = RG-0031.
- `process_batch.py` / `process_new_item.py` no longer glob for SKUs; SKILL.md Phase 0 updated.
- Plugin cache rebuilt from source (also resolves the stale-`DEFAULT_ITEMS_DIR` drift found earlier).
