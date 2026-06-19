from __future__ import annotations
import csv
from pathlib import Path
from typing import Dict, Tuple, Union
from ..models import Channel, ChannelObservation

WhatnotIndex = Dict[str, Tuple[float, bool]]   # sku -> (price, sold)


def build_whatnot_index(csv_path: Union[str, Path]) -> WhatnotIndex:
    index: WhatnotIndex = {}
    path = Path(csv_path)
    if not path.exists():
        return index
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            sku = (row.get("SKU") or "").strip()
            if not sku:
                continue
            try:
                price = float((row.get("Price") or "0").strip())
            except ValueError:
                price = 0.0
            sold = (row.get("Status") or "").strip().lower() == "sold"
            index[sku] = (price, sold)
    return index


def observe_whatnot(sku: str, index: WhatnotIndex) -> ChannelObservation:
    if sku not in index:
        return ChannelObservation(channel=Channel.WHATNOT, present=False)
    price, sold = index[sku]
    return ChannelObservation(channel=Channel.WHATNOT, present=True, price=price, sold=sold)
