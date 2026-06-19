from __future__ import annotations
from typing import List
from .models import PageRecord


def plan_channel_pushes(page: PageRecord, channels_registry: dict, new_price: float) -> List[dict]:
    """Which channels need a price push for a new reference price. Pure (no I/O).

    Square (listed + registry has variation_id) -> an actionable 'api' push; otherwise 'manual'.
    Other listed channels (whatnot/ebay/marketplace) -> 'manual' (no API write-path here).
    Channels not in page.listed_on are skipped.
    """
    cents = round(new_price * 100)
    pushes: List[dict] = []
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
