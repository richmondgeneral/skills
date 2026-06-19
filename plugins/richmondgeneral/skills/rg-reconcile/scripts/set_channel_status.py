#!/usr/bin/env python3
"""rg-set-channel-status write-path: transition ONE channel's status in items/<SKU>/label.json
and record its platform IDs (object_id, buy_link, ...) — the registry write the Slice-B page
writer leaves to hand-editing.

This is a local, safe write: it merges {status, **ids} onto the channel's registry entry
(preserving other keys, leaving other channels untouched), recomputes `oversize` from the
item's measurements, and writes label.json atomically (tmp -> rename). Sold is sticky — a
channel already 'sold' is never downgraded. No network / Square SDK is touched.
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

# Make the item-model-core sibling skill's lib importable (item_model.*) when run as a script.
# Under pytest, conftest.py already injects item-model-core/lib + rg-reconcile/scripts.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "item-model-core", "lib"))

from item_model.channel_registry import set_channel_status
from item_model.measurements import compute_oversize
from item_model.instance import load_instance_config  # import-safe: no network


def apply_set_channel_status(item_dir, channel, status, *, object_id=None, buy_link=None) -> dict:
    """Read label.json, set the channel's status + platform IDs, recompute oversize, write atomically.

    Returns the updated label dict. Sold-sticky and merge semantics come from
    item_model.channel_registry.set_channel_status.
    """
    item_dir = Path(item_dir)
    label_path = item_dir / "label.json"
    label = json.loads(label_path.read_text(encoding="utf-8"))

    ids = {}
    if object_id is not None:
        ids["object_id"] = object_id
    if buy_link is not None:
        ids["buy_link"] = buy_link
    label = set_channel_status(label, channel, status, **ids)
    label["oversize"] = compute_oversize(label.get("measurements_in"))

    tmp = label_path.with_suffix(label_path.suffix + ".tmp")
    tmp.write_text(json.dumps(label, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(label_path)
    return label


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Set one channel's status (+ platform IDs) in items/<SKU>/label.json.")
    ap.add_argument("sku")
    ap.add_argument("channel")
    ap.add_argument("status")
    ap.add_argument("--object-id")
    ap.add_argument("--buy-link")
    ap.add_argument("--items-dir", default=load_instance_config().items_dir)
    args = ap.parse_args(argv)
    item_dir = Path(args.items_dir) / args.sku
    label = apply_set_channel_status(
        item_dir, args.channel, args.status,
        object_id=args.object_id, buy_link=args.buy_link)
    entry = label.get("channels", {}).get(args.channel, {})
    print(f"{args.sku}: {args.channel} -> {entry.get('status')} "
          f"(oversize={label.get('oversize')}) (written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
