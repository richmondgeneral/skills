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
