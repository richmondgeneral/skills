"""Atomic RG-XXXX SKU allocation backed by a single hidden Square sentinel object.

Square is the allocation authority: a hidden CatalogItem (variation SKU
`__RG_SKU_COUNTER__`) stores the last-allocated integer N in its name
(`RG-SKU-COUNTER:NNNN`). Allocation increments N via Square catalog-object version
compare-and-set, so independent multi-machine writers never collide. Unique-only
(gaps OK); reconcile-then-CAS folded into each allocate.

Design: docs/plans/2026-06-19-sku-allocation-design.md
"""
from __future__ import annotations

import os
import re
import subprocess
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
    # create() must tolerate a concurrent create (idempotent, or self-healing on the next read).


def allocate_sku(store: CounterStore, max_retries: int = DEFAULT_MAX_RETRIES) -> str:
    """Return a fresh RG-XXXX, reserved on Square. Raises on hard failure.

    candidate = max(stored N, live Square RG max) + 1, so the result is always
    >= 1 (never negative) given non-negative inputs. CAS on the sentinel version
    guarantees exactly one winner per increment; conflicts retry.

    A missing-sentinel self-heal consumes one retry iteration, so callers passing
    a very small max_retries should account for it.
    """
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
    """Return the current counter N without allocating; None if the sentinel is absent. Propagates SquareUnavailable."""
    return store.read().n


def _is_version_conflict(errors) -> bool:
    for e in errors or []:
        code = getattr(e, "code", None) or (e.get("code") if isinstance(e, dict) else None) or ""
        detail = getattr(e, "detail", None) or (e.get("detail") if isinstance(e, dict) else None) or ""
        if str(code).upper() == "VERSION_MISMATCH" or "version" in str(detail).lower():
            return True
    return False


def _resolve_square_token() -> Optional[str]:
    """Resolve the Square access token with NO cross-skill import, so this works
    standalone, from the orchestrator, and over the osascript bridge's bare shell.
    Order: env (SQUARE_ACCESS_TOKEN/SQUARE_TOKEN) -> macOS Keychain -> workspace .env."""
    for name in ("SQUARE_ACCESS_TOKEN", "SQUARE_TOKEN"):
        v = os.environ.get(name)
        if v:
            return v
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-a", os.environ.get("USER", ""),
             "-s", "SQUARE_ACCESS_TOKEN", "-w"],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:  # noqa: BLE001
        pass
    env_path = Path.home() / "workspace" / "richmondgeneral" / ".env"
    try:
        if env_path.exists():
            for raw in env_path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                if key.strip() in ("SQUARE_ACCESS_TOKEN", "SQUARE_TOKEN"):
                    return val.strip().strip('"').strip("'") or None
    except Exception:  # noqa: BLE001
        pass
    return None


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
                token = _resolve_square_token()
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
        existing, _, _ = self._scan()                       # tolerate concurrent create
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
                # FIXED key (not a fresh uuid): makes Square dedupe concurrent
                # self-heal creates into ONE sentinel, robust to the search_items
                # eventual-consistency lag observed during integration (M-1 contract).
                idempotency_key="rg-sku-counter-create-v1",
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


def _main(argv=None) -> int:
    import argparse
    import json
    p = argparse.ArgumentParser(description="RG SKU allocation authority (Square-backed).")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("peek", help="print current counter N")
    b = sub.add_parser("bootstrap", help="create sentinel from max(Square, items dir)")
    b.add_argument("--items-dir", default=None)
    sub.add_parser("allocate", help="allocate and print one RG-XXXX (mutates Square!)")
    args = p.parse_args(argv)
    store = SquareCounterStore()
    if args.cmd == "peek":
        print(json.dumps({"n": peek(store)}))
        return 0
    if args.cmd == "bootstrap":
        fs = 0
        if args.items_dir:
            fs = max([parse_rg_n(c.name) or 0 for c in Path(args.items_dir).glob("RG-*")] or [0])
        print(json.dumps({"n": bootstrap(store, fs_max=fs)}))
        return 0
    if args.cmd == "allocate":
        print(json.dumps({"sku": allocate_sku(store)}))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())
