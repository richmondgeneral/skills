#!/usr/bin/env python3
"""rg-set-price write-path: reprice an item so the page reference and Square never drift.

The page reference price (items/<SKU>/label.json) is updated unconditionally — that's a
local, safe write. Channels are then planned: a listed Square variation with a known
variation_id becomes an actionable API push; every other listed channel is surfaced as a
MANUAL checklist line.

LIVE EDGE: the Square price write executes ONLY with --apply. Without it (the default),
this is a dry-run — the planner runs but no Square SDK import or network call happens.
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

# Make the item-model-core sibling skill's lib importable (item_model.*), and the
# rg-item-update scripts dir importable (safe_batch_reprice) when run as a script.
# Under pytest, conftest.py already injects item-model-core/lib + rg-reconcile/scripts.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "item-model-core", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "rg-item-update", "scripts"))

from item_model.page_reader import read_page_record
from item_model.page_writer import write_page_record
from item_model.write_path import plan_channel_pushes
from item_model.instance import load_instance_config  # import-safe: no network


def apply_set_price(item_dir, new_price, *, apply: bool = False, square_client=None) -> dict:
    """Update the page reference price (always, local/safe) and plan channel pushes.

    Square 'api' pushes execute ONLY when apply=True (delegated to safe_batch_update with
    dry_run=False). On the default dry-run path no Square SDK import or network occurs.
    Returns {"sku", "page_updated": True, "pushes": [...], "applied": bool}.
    """
    item_dir = Path(item_dir)
    rec = read_page_record(item_dir)
    rec.reference_price = float(new_price)
    write_page_record(item_dir, rec)                      # page reference updated (local, safe)

    label = json.loads((item_dir / "label.json").read_text(encoding="utf-8"))
    registry = label.get("channels", {}) or {}
    pushes = plan_channel_pushes(rec, registry, float(new_price))

    api_pushes = [p for p in pushes if p["mode"] == "api"]
    if api_pushes and apply:
        # live edge — these imports + the token resolver run ONLY on --apply.
        # resolve_square_token() touches Keychain/.env, so it must never be reached
        # on the dry-run (apply=False) path.
        from safe_batch_reprice import safe_batch_update
        from square.client import Square
        from item_model.instance import resolve_square_token
        client = square_client or Square(token=resolve_square_token())
        updates = {p["variation_id"]: p["amount_cents"] for p in api_pushes}
        safe_batch_update(client, updates, dry_run=False)
    return {"sku": rec.sku, "page_updated": True, "pushes": pushes, "applied": bool(apply)}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Reprice an item: page reference + Square push + manual checklist for other channels.")
    ap.add_argument("sku")
    ap.add_argument("price", type=float)
    ap.add_argument("--items-dir", default=load_instance_config().items_dir)
    ap.add_argument("--apply", action="store_true",
                    help="Execute the Square price write (else dry-run).")
    args = ap.parse_args(argv)
    item_dir = Path(args.items_dir) / args.sku
    result = apply_set_price(item_dir, args.price, apply=args.apply)
    print(f"{result['sku']}: page reference -> ${args.price:.2f} (written)")
    for p in result["pushes"]:
        if p["mode"] == "api":
            verb = "PUSHED" if args.apply else "would push (dry-run; use --apply)"
            print(f"  square: {verb} variation {p['variation_id']} -> ${args.price:.2f}")
        else:
            print(f"  {p['channel']}: MANUAL — update to ${args.price:.2f} by hand"
                  + (" (Marketplace via computer-use)" if p['channel'] == 'marketplace' else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
