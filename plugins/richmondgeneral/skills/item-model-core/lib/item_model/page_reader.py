from __future__ import annotations
import json
from pathlib import Path
from typing import Optional, Union
from .models import PageRecord, Channel
from .channel_registry import listed_on_from_registry, sold_from_label


def read_page_record(item_dir: Union[str, Path]) -> PageRecord:
    """Build a PageRecord from items/<SKU>/label.json (+ optional status.json).

    listed_on is derived from the project's `channels` registry when present;
    legacy label.json (no `channels` key) falls back to the explicit `listed_on`
    array, and an absent both yields an empty list.
    """
    item_dir = Path(item_dir)
    label = json.loads((item_dir / "label.json").read_text(encoding="utf-8"))

    sku = label["sku"]
    reference_price = float(label["price"])

    status_json: Optional[dict] = None
    status_file = item_dir / "status.json"
    if status_file.exists():
        status_json = json.loads(status_file.read_text(encoding="utf-8"))

    sold = sold_from_label(label, status_json)

    if "channels" in label:
        listed_on = listed_on_from_registry(label["channels"])
    else:
        listed_on = [Channel(c) for c in label.get("listed_on", [])]

    intended = {
        Channel(k): float(v)
        for k, v in label.get("intended_channel_prices", {}).items()
    }
    return PageRecord(
        sku=sku,
        reference_price=reference_price,
        sold=sold,
        listed_on=listed_on,
        intended_channel_prices=intended,
    )
