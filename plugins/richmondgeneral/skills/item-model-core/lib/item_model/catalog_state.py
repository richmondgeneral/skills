from __future__ import annotations
from typing import List, Tuple
from .models import PageRecord, ChannelObservation


def build_catalog_state(records_with_obs: List[Tuple[PageRecord, List[ChannelObservation]]]) -> dict:
    """A defined, deterministic snapshot of current reality (no timestamp — the writer stamps mtime)."""
    items = []
    for rec, obs in records_with_obs:
        items.append({
            "sku": rec.sku,
            "reference_price": rec.reference_price,
            "sold": rec.sold,
            "listed_on": [c.value for c in rec.listed_on],
            "channels": {
                o.channel.value: {"present": o.present, "price": o.price, "sold": o.sold}
                for o in obs
            },
        })
    items.sort(key=lambda i: i["sku"])
    return {"item_count": len(items), "items": items}
