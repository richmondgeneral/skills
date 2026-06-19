#!/usr/bin/env python3
"""Rebuild catalog_index.jsonl (the RG-SKU dedup index) from LIVE Square.

catalog_index.jsonl is the local dedup snapshot consulted during intake. It goes
stale as items are added, so this rebuilds it from live Square
(SearchCatalogObjects), never trusting the local file. Run it after each intake
batch (and as the Square layer of the dedupe-first SOP).

Promoted 2026-06-19 from the throwaway tmp/generate_index.py. Reads
SQUARE_ACCESS_TOKEN from the workspace .env (or the environment) and writes
<root>/catalog_index.jsonl. stdlib-only — no extra deps.

    python3 generate_catalog_index.py            # default root ~/workspace/richmondgeneral
    python3 generate_catalog_index.py --root /path/to/workspace
"""

import argparse
import json
import os
import re
import sys
import urllib.request

DEFAULT_ROOT = os.path.expanduser("~/workspace/richmondgeneral")


def load_token(root):
    env = {}
    env_path = os.path.join(root, ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    token = (env.get("SQUARE_ACCESS_TOKEN") or env.get("SQUARE_TOKEN")
             or os.environ.get("SQUARE_ACCESS_TOKEN"))
    version = env.get("SQUARE_API_VERSION", "2026-04-21")
    return token, version


def api(path, token, version, method="GET", body=None):
    req = urllib.request.Request(
        "https://connect.squareup.com" + path,
        data=json.dumps(body).encode() if body else None,
        method=method,
    )
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Square-Version", version)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser(description="Rebuild catalog_index.jsonl from live Square")
    ap.add_argument("--root", default=DEFAULT_ROOT,
                    help=f"Workspace root holding .env + catalog_index.jsonl (default: {DEFAULT_ROOT})")
    ap.add_argument("--sku-pattern", default=r"^RG-\d{4}$",
                    help="SKU regex to include (default RG-#### — survives RG-0100+)")
    args = ap.parse_args()

    token, version = load_token(args.root)
    if not token:
        print("Error: SQUARE_ACCESS_TOKEN not found (workspace .env or environment)", file=sys.stderr)
        return 1

    # Pull every ITEM from live Square (paginated).
    items, cursor = [], None
    while True:
        body = {"object_types": ["ITEM"], "include_deleted_objects": False}
        if cursor:
            body["cursor"] = cursor
        res = api("/v2/catalog/search", token, version, "POST", body)
        items.extend(res.get("objects", []))
        cursor = res.get("cursor")
        if not cursor:
            break

    sku_re = re.compile(args.sku_pattern)
    rows = []
    for it in items:
        d = it.get("item_data", {})
        variations = []
        for v in d.get("variations", []):
            vd = v.get("item_variation_data", {})
            sku = vd.get("sku", "")
            if sku_re.match(sku):
                variations.append({"id": v.get("id"), "sku": sku, "t": bool(vd.get("track_inventory"))})
        if variations:
            rows.append({"id": it.get("id"), "name": d.get("name"), "v": variations})
    rows.sort(key=lambda r: r["v"][0]["sku"])

    out_path = os.path.join(args.root, "catalog_index.jsonl")
    with open(out_path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"wrote {len(rows)} RG items to {out_path}")
    if rows:
        print(f"range: {rows[0]['v'][0]['sku']} .. {rows[-1]['v'][0]['sku']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
