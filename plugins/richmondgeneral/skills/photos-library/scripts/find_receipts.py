#!/usr/bin/env python3
"""List receipt photos Apple's Photos ML has labeled, newest first.

The queue half of the receipt sorter: psi.sqlite ("Receipt" scene label) ->
ZUUIDs -> Photos.sqlite metadata, minus already-sorted (rg-sorted). File hits
with file_receipt.py. NOTE: Photos labels lazily (overnight / on power), so a
just-shot receipt may not appear yet — the newest-labeled date is printed so
you can judge coverage.
"""

import argparse
import json
import os
import sqlite3
import sys

import photos_db
import psi_db

COCOA_EPOCH_OFFSET = 978307200
SECONDS_PER_DAY = 86400
LIBRARY = os.path.expanduser("~/Pictures/Photos Library.photoslibrary")
DB_PATH = os.path.join(LIBRARY, "database", "Photos.sqlite")


def find_receipts(db_path, psi_path, days=30, exclude_keyword=None):
    with sqlite3.connect(f"file:{psi_path}?mode=ro&immutable=1", uri=True) as conn:
        uuids = sorted(psi_db.receipt_uuids(conn))
    if not uuids:
        return [], None

    conditions = ["a.ZTRASHEDSTATE = 0", "a.ZHIDDEN = 0", "a.ZKIND = 0"]
    params = []
    placeholders = ",".join("?" for _ in uuids)
    conditions.append(f"a.ZUUID IN ({placeholders})")
    params.extend(uuids)
    if days:
        conditions.append(
            f"a.ZDATECREATED > (strftime('%s', 'now') - {COCOA_EPOCH_OFFSET} - ? * {SECONDS_PER_DAY})")
        params.append(days)

    with sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True) as conn:
        if exclude_keyword:
            frag, frag_params = photos_db.exclude_keyword_condition(conn, exclude_keyword)
            conditions.append(frag)
            params.extend(frag_params)
        where = " AND ".join(conditions)
        rows = conn.execute(
            f"SELECT a.ZUUID, aa.ZORIGINALFILENAME, a.ZDATECREATED, a.ZWIDTH, a.ZHEIGHT, "
            f"a.ZUNIFORMTYPEIDENTIFIER, "
            f"datetime(a.ZDATECREATED + {COCOA_EPOCH_OFFSET}, 'unixepoch', 'localtime') "
            f"FROM ZASSET a "
            f"LEFT JOIN ZADDITIONALASSETATTRIBUTES aa ON a.ZADDITIONALATTRIBUTES = aa.Z_PK "
            f"WHERE {where} ORDER BY a.ZDATECREATED DESC",
            params).fetchall()
        # Coverage marker: newest receipt-labeled photo regardless of the day
        # window or sorted-state (tells you how far ML labeling has caught up).
        newest = conn.execute(
            f"SELECT MAX(datetime(ZDATECREATED + {COCOA_EPOCH_OFFSET}, 'unixepoch', 'localtime')) "
            f"FROM ZASSET WHERE ZUUID IN ({placeholders})", uuids).fetchone()[0]

    photos = []
    for zuuid, filename, ts, w, h, uti, created in rows:
        path = os.path.join(LIBRARY, photos_db.original_relpath(zuuid, uti))
        photos.append({"uuid": zuuid, "filename": filename or zuuid, "created": created,
                       "width": w, "height": h, "on_disk": os.path.exists(path)})
    return photos, newest


def main():
    p = argparse.ArgumentParser(description="List ML-labeled receipt photos (the receipt queue)")
    p.add_argument("--days", type=int, default=30, help="last N days (0 = all time; default 30)")
    p.add_argument("--exclude-keyword", type=str, help="exclude photos with this keyword/tag")
    p.add_argument("--hide-sorted", action="store_true", help="exclude photos tagged rg-sorted")
    p.add_argument("--json", action="store_true")
    p.add_argument("--db", type=str, help="Path to Photos.sqlite")
    p.add_argument("--psi-db", type=str, help="Path to psi.sqlite")
    args = p.parse_args()

    if args.days < 0:
        print("Error: --days cannot be negative")
        return 1
    db_path = args.db or (DB_PATH if os.path.exists(DB_PATH) else None)
    psi_path = args.psi_db or psi_db.find_psi_db()
    if not db_path or not psi_path:
        print("Error: could not find Photos.sqlite / psi.sqlite")
        return 1

    exclude = args.exclude_keyword
    if args.hide_sorted:
        exclude = "rg-sorted"

    photos, newest = find_receipts(db_path, psi_path, days=(args.days or None),
                                   exclude_keyword=exclude)
    if args.json:
        print(json.dumps({"newest_labeled": newest, "photos": photos}, indent=2))
    else:
        days_str = f"last {args.days} days" if args.days else "all time"
        print(f"Found {len(photos)} receipt photo(s) ({days_str}"
              f"{', minus ' + exclude if exclude else ''})")
        if newest:
            print(f"ML label coverage through: {newest} "
                  f"(newer receipts may not be labeled yet)\n")
        for ph in photos:
            disk = " " if ph["on_disk"] else "☁"
            print(f"  {ph['uuid'][:8]}  {ph['created']}  {ph['width']}x{ph['height']} {disk} {ph['filename']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
