from __future__ import annotations
import json
from pathlib import Path
from typing import Union
from .models import PageRecord
from .channel_registry import REGISTRY_CHANNEL_KEYS

_CHANNEL_TO_KEY = {ch: key for key, ch in REGISTRY_CHANNEL_KEYS.items()}


def write_page_record(item_dir: Union[str, Path], record: PageRecord,
                      *, preserve_extras: bool = True) -> None:
    """Write/merge a PageRecord into items/<SKU>/label.json, maintaining the channels registry.

    Merge semantics: preserve all existing keys (product_name, condition, channel platform
    IDs, state, ...). Update sku / price from the record. `intended_channel_prices` is set to
    the record's value, or REMOVED when the record's is empty (faithful to the view, not
    additive). For each channel in record.listed_on, set channels.<key>.status = "listed"
    (create the entry if absent, preserving its other fields). Channels NOT in listed_on are
    left untouched — never downgrade a sold/ended/pending status. The deprecated top-level
    `listed_on` array is migrated into the registry and removed (the registry is authoritative).
    Atomic write (tmp -> rename).
    """
    item_dir = Path(item_dir)
    item_dir.mkdir(parents=True, exist_ok=True)
    label_path = item_dir / "label.json"

    label: dict = {}
    if preserve_extras and label_path.exists():
        label = json.loads(label_path.read_text(encoding="utf-8"))

    label["sku"] = record.sku
    label["price"] = f"{record.reference_price:.2f}"
    if record.intended_channel_prices:
        label["intended_channel_prices"] = {
            ch.value: price for ch, price in record.intended_channel_prices.items()
        }
    else:
        label.pop("intended_channel_prices", None)

    channels = label.get("channels")
    if not isinstance(channels, dict):
        channels = {}
    for ch in record.listed_on:
        key = _CHANNEL_TO_KEY[ch]
        entry = channels.get(key)
        if not isinstance(entry, dict):
            entry = {}
        entry["status"] = "listed"
        channels[key] = entry
    if channels:
        label["channels"] = channels
    # The channels registry is authoritative; drop the deprecated top-level listed_on array.
    label.pop("listed_on", None)

    tmp = label_path.with_suffix(label_path.suffix + ".tmp")
    tmp.write_text(json.dumps(label, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(label_path)
