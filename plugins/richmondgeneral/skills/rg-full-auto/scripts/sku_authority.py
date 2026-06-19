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
from dataclasses import dataclass
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
