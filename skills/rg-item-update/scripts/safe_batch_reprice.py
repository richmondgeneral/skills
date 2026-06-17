#!/usr/bin/env python3
"""Safe batch price update for Square catalog using fetch-patch-upsert pattern.

Uses the Square SDK v44+ API (square.client.Square).
Fetches full objects first to preserve SKU, name, and all other fields,
then patches only the price and upserts the complete objects back.

Usage:
  # With hardcoded targets:
  python safe_batch_reprice.py

  # With JSON file input:
  python safe_batch_reprice.py --file price_updates.json
  # JSON format: [{"variation_id": "...", "amount_cents": 1950}, ...]

  # Dry run (fetch + patch, no upsert):
  python safe_batch_reprice.py --dry-run

Requires:
  - SQUARE_ACCESS_TOKEN environment variable
  - pip install squareup
"""

import argparse
import json
import os
import subprocess
import sys
import uuid

from square.client import Square


# ── Default Targets (Variation ID -> New Price in Cents) ──────────────
# These were the penny-free pricing policy updates applied 2026-02-15.
# Override with --file to supply a different set of updates.
DEFAULT_UPDATES = {
    "UQORP6UPBOGGNDKOE4GU2M2J": 1950,  # RG-0001: $19.50
    "KNOOKEXGF37G2WSUAUX6C6PC": 3500,  # RG-0002: $35.00
    "3TGL6STUAR3JBOIWCXSV3G63": 7000,  # RG-0004: $70.00
    "TJLCXJSPHEDNS2R3OV5ZVX5I": 4500,  # RG-0006: $45.00
    "IVUV6KVYIGWYIWTEI2J52B25": 1500,  # RG-0007: $15.00
    "5JD2MEEGQBXOZUNBPLD2ZIAJ": 3000,  # RG-0008: $30.00
    "WJ7RJI2ECDTRAJW7J6WH7PTQ": 4500,  # RG-0009: $45.00
    "LQVR73GMXBDETD7PTGKME6XB": 9000,  # RG-0010: $90.00
    "DOGGZ4MLPOQNBRCIFTXTP7WN": 1500,  # RG-0011: $15.00
    "DTMHI76VCVD6JNEVZ35BWAWN": 1950,  # RG-0012: $19.50
    "AR63H4MGON7VTBQ3TZB3KOHJ": 1300,  # RG-0013: $13.00
    "EUJSMYTD4RTDN76TZUVEGRBL": 2500,  # RG-0014: $25.00
}

BATCH_SIZE = 10  # Square allows max 1000, but 10 is safe and readable


def resolve_square_cache_cli():
    """Resolve square_cache.sh location across current and legacy layouts."""
    candidates = [
        os.environ.get("SQUARE_CACHE_SH"),
        os.path.expanduser("~/workspace/square/square-tools/bin/square_cache.sh"),
        os.path.expanduser("~/Workspace/square-tools/bin/square_cache.sh"),
        "/Users/scottybe/workspace/square/square-tools/bin/square_cache.sh",
    ]
    for path in candidates:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def sync_square_cache(token: str):
    """Sync local square-cache after successful price updates."""
    cache_cli = resolve_square_cache_cli()
    if not cache_cli:
        print("⚠️  Skipped cache sync: square_cache.sh not found.")
        return False

    env = os.environ.copy()
    env["SQUARE_ACCESS_TOKEN"] = token
    env["SQUARE_TOKEN"] = token

    result = subprocess.run(
        [cache_cli, "sync"], env=env, capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"✅ Cache synced via {cache_cli}")
        return True

    print("⚠️  Cache sync failed:")
    print((result.stderr or result.stdout).strip())
    return False


def safe_batch_update(client: Square, updates: dict, dry_run: bool = False):
    """Fetch-patch-upsert: the only safe way to update Square catalog prices.

    1. FETCH complete objects via batch_get (preserves every field)
    2. PATCH only price_money in memory
    3. UPSERT complete objects back via batch_upsert
    """
    variation_ids = list(updates.keys())

    # ── FETCH ─────────────────────────────────────────────────────────
    print(f"📥 Fetching {len(variation_ids)} variations...")
    result = client.catalog.batch_get(object_ids=variation_ids)

    if hasattr(result, "errors") and result.errors:
        print(f"❌ Fetch failed: {result.errors}")
        return False

    fetched = result.objects or []
    print(f"✅ Retrieved {len(fetched)} objects")

    fetched_ids = {obj.id for obj in fetched}
    missing = set(variation_ids) - fetched_ids
    if missing:
        print(f"❌ Missing IDs: {sorted(missing)}")
        print("❌ Aborting to avoid partial repricing.")
        return False

    # ── PATCH ─────────────────────────────────────────────────────────
    patched = []
    for obj in fetched:
        d = obj.model_dump(mode="json", exclude_none=True)
        vid = d["id"]
        if vid in updates:
            old_price = d["item_variation_data"]["price_money"]["amount"]
            new_price = updates[vid]
            sku = d["item_variation_data"].get("sku", "?")
            d["item_variation_data"]["price_money"] = {
                "amount": new_price,
                "currency": "USD",
            }
            patched.append(d)
            print(f"   {sku}: ${old_price/100:.2f} → ${new_price/100:.2f}")

    if len(patched) != len(variation_ids):
        print("❌ Patch set does not match requested update count. Aborting.")
        return False

    if dry_run:
        print(f"\n🏁 Dry run complete. {len(patched)} objects patched (not sent).")
        return True

    # ── UPSERT (in batches) ───────────────────────────────────────────
    print(f"\n🚀 Upserting {len(patched)} objects in batches of {BATCH_SIZE}...")
    all_ok = True

    for i in range(0, len(patched), BATCH_SIZE):
        batch = patched[i : i + BATCH_SIZE]
        r = client.catalog.batch_upsert(
            idempotency_key=str(uuid.uuid4()),
            batches=[{"objects": batch}],
        )
        if hasattr(r, "errors") and r.errors:
            print(f"   ❌ Batch {i // BATCH_SIZE + 1} failed: {r.errors}")
            all_ok = False
        else:
            count = len(r.objects) if r.objects else 0
            print(f"   ✅ Batch {i // BATCH_SIZE + 1}: {count} objects upserted")

    if all_ok:
        print("\n✅ All prices updated successfully.")
    else:
        print("\n⚠️  Some batches failed — check output above.")

    return all_ok


def main():
    parser = argparse.ArgumentParser(
        description="Safe batch price update via fetch-patch-upsert"
    )
    parser.add_argument(
        "--file",
        help='JSON file with updates: [{"variation_id": "...", "amount_cents": N}, ...]',
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and patch but do not upsert",
    )
    parser.add_argument(
        "--token",
        help="Square access token (or set SQUARE_ACCESS_TOKEN env var)",
    )
    parser.add_argument(
        "--no-cache-sync",
        action="store_true",
        help="Skip square-cache sync after update",
    )
    args = parser.parse_args()

    token = args.token or os.environ.get("SQUARE_ACCESS_TOKEN")
    if not token:
        print("❌ Error: set SQUARE_ACCESS_TOKEN or use --token", file=sys.stderr)
        sys.exit(1)

    # Build updates dict
    if args.file:
        with open(args.file) as f:
            raw = json.load(f)
        updates = {u["variation_id"]: int(u["amount_cents"]) for u in raw}
        print(f"Loaded {len(updates)} updates from {args.file}")
    else:
        updates = DEFAULT_UPDATES
        print(f"Using {len(updates)} hardcoded default targets")

    client = Square(token=token)
    ok = safe_batch_update(client, updates, dry_run=args.dry_run)

    if ok and not args.dry_run and not args.no_cache_sync:
        sync_ok = sync_square_cache(token)
        if not sync_ok:
            ok = False

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
