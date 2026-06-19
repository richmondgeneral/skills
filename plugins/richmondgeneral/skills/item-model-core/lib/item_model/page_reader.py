from __future__ import annotations
import json
from pathlib import Path
from typing import Union
from .models import PageRecord, Channel


def read_page_record(item_dir: Union[str, Path]) -> PageRecord:
    """Build a PageRecord from items/<SKU>/label.json (+ optional status.json)."""
    item_dir = Path(item_dir)
    label = json.loads((item_dir / "label.json").read_text(encoding="utf-8"))

    sku = label["sku"]
    reference_price = float(label["price"])

    sold = False
    status_file = item_dir / "status.json"
    if status_file.exists():
        status = json.loads(status_file.read_text(encoding="utf-8"))
        sold = str(status.get("status", "")).lower() == "sold"

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
