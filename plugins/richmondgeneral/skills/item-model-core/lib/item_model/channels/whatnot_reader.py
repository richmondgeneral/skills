from __future__ import annotations
import csv
from pathlib import Path
from typing import Dict, Optional, Tuple, Union
from ..models import Channel, ChannelObservation

# sku -> (price, sold). `sold` is None when the channel does not expose sold-state
# (no Status column), so the diff engine skips the sold-state check for it.
WhatnotIndex = Dict[str, Tuple[float, Optional[bool]]]


def build_whatnot_index(csv_path: Union[str, Path]) -> WhatnotIndex:
    index: WhatnotIndex = {}
    path = Path(csv_path)
    if not path.exists():
        return index
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        # Decide ONCE per file whether sold-state is exposed at all.
        has_status = bool(reader.fieldnames) and "Status" in reader.fieldnames
        for row in reader:
            sku = (row.get("SKU") or "").strip()
            if not sku:
                continue
            # Price: prefer Price, else BuyItNowPrice, else StartingPrice, else "0".
            raw_price = (
                row.get("Price")
                or row.get("BuyItNowPrice")
                or row.get("StartingPrice")
                or "0"
            )
            try:
                price = float(raw_price.strip())
            except ValueError:
                price = 0.0
            # Sold-state: only meaningful when a Status column exists.
            sold: Optional[bool]
            if has_status:
                sold = (row.get("Status") or "").strip().lower() == "sold"
            else:
                sold = None
            index[sku] = (price, sold)
    return index


def observe_whatnot(sku: str, index: WhatnotIndex) -> Optional[ChannelObservation]:
    """Positive-only: the Whatnot import CSV can AFFIRM a listing (+ price/sold) but cannot
    DENY one — items listed directly via the Whatnot UI never appear in it. So a SKU absent
    from the CSV yields None (no observation = "not checked"), NOT present=False, to avoid
    false "not present" findings. (Square, a live catalog, stays authoritative and may report
    present=False.)"""
    if sku not in index:
        return None
    price, sold = index[sku]
    return ChannelObservation(channel=Channel.WHATNOT, present=True, price=price, sold=sold)
