#!/usr/bin/env python3
"""Canonical filing for the receipt sorter.

Given a cluster of receipt-photo ZUUIDs plus vendor/date/total, file them:
export originals into ``ops/receipts/YYYY-MM-DD-<vendor>.jpeg`` (never
clobbering), append a row to ``ops/receipts/receipts-log.md`` (the lot-tracker's
cost feed), add the photos to the "Receipts" album under "Richmond General
Archive", and tag them ``rg-sorted`` + ``rg-receipt`` so they drop out of both
the receipt queue and the item intake sweep. ``--plan`` dry-runs.

Companion to ``file_cluster.py`` (items); reuses its resolve/tag machinery.
"""

import argparse
import datetime
import json
import os
import re
import sqlite3

import file_cluster as fc

COCOA_EPOCH_OFFSET = 978307200
DEFAULT_OPS_DIR = os.path.expanduser("~/workspace/richmondgeneral/ops")
LEDGER_HEADER = (
    "# Receipts Log\n\n"
    "Filed by photos-library/file_receipt.py — one row per receipt "
    "(multi-page = one row, several files).\n\n"
    "| Date | Vendor | Total | Lot | File | UUIDs |\n"
    "|------|--------|-------|-----|------|-------|\n"
)


def slugify(vendor):
    s = vendor.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "receipt"


def plan_receipt_names(existing, date, vendor, count):
    """Non-clobbering output names: base.jpeg, base-2.jpeg, … (suffix keeps
    incrementing past whatever already exists on disk)."""
    base = f"{date}-{slugify(vendor)}"
    names, n = [], 0
    existing = set(existing)
    for _ in range(count):
        while True:
            n += 1
            cand = f"{base}.jpeg" if n == 1 else f"{base}-{n}.jpeg"
            if cand not in existing:
                break
        existing.add(cand)
        names.append(cand)
    return names


def append_ledger(path, date, vendor, total, lot, files, uuids):
    """Append one row; create the file with its header if absent.

    UUIDs are truncated to 13 chars (readable, still greppable) — the full
    values live on the photos themselves as keywords/album membership.
    """
    row = (f"| {date} | {vendor} | {'$' + str(total) if total else ''} | {lot or ''} "
           f"| {', '.join(files)} | {', '.join(u[:13] for u in uuids)} |\n")
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        if new:
            f.write(LEDGER_HEADER)
        f.write(row)
    return row.strip()


# --- integration (live Photos / filesystem side effects) ------------------------

def photo_dates(uuids):
    """{uuid: 'YYYY-MM-DD'} from ZASSET.ZDATECREATED (read-only, immutable)."""
    placeholders = ",".join("?" for _ in uuids)
    out = {}
    with sqlite3.connect(f"file:{fc.DB_PATH}?mode=ro&immutable=1", uri=True) as conn:
        for zuuid, ts in conn.execute(
                f"SELECT ZUUID, ZDATECREATED FROM ZASSET WHERE ZUUID IN ({placeholders})", uuids):
            if ts is not None:
                out[zuuid] = datetime.datetime.fromtimestamp(
                    ts + COCOA_EPOCH_OFFSET).strftime("%Y-%m-%d")
    return out


def export_receipts(plan, by_uuid, receipts_dir):
    os.makedirs(receipts_dir, exist_ok=True)
    written = []
    for entry in plan:
        o = by_uuid[entry["uuid"]]
        if not o["on_disk"]:
            continue
        fc.sips_convert(o["path"], os.path.join(receipts_dir, entry["out"]))
        written.append(entry["out"])
    return written


def main():
    p = argparse.ArgumentParser(description="File receipt photos into ops/receipts/ + ledger.")
    p.add_argument("--uuids", required=True, help="comma-separated ZUUIDs (one receipt, multi-page ok)")
    p.add_argument("--vendor", help='e.g. "Goodwill Crystal Lake" (required unless --dismiss)')
    p.add_argument("--dismiss", action="store_true",
                   help="personal / non-business receipt: just tag rg-sorted + rg-receipt "
                        "(no export, no ledger, no album) so it leaves the queue")
    p.add_argument("--date", help="YYYY-MM-DD (default: the photo's creation date)")
    p.add_argument("--total", help="receipt total, e.g. 12.99")
    p.add_argument("--lot", help="lot code to link, e.g. GIBA-C2")
    p.add_argument("--ops-dir", default=DEFAULT_OPS_DIR)
    p.add_argument("--plan", action="store_true", help="dry-run: print intent, mutate nothing")
    args = p.parse_args()

    uuids = [u.strip() for u in args.uuids.split(",") if u.strip()]
    if not uuids:
        p.error("--uuids was empty")
    for u in uuids:
        if not fc.UUID_RE.match(u):
            p.error(f"bad uuid {u!r}")
    if args.date and not re.match(r"^\d{4}-\d{2}-\d{2}$", args.date):
        p.error(f"bad --date {args.date!r}; expected YYYY-MM-DD")

    if args.dismiss:
        tag = fc.tag_keywords(["rg-sorted", "rg-receipt"], uuids)
        print(json.dumps({"mode": "dismiss", "tagged": len(uuids), "tag": tag}, indent=2))
        return
    if not args.vendor:
        p.error("--vendor is required (or use --dismiss for a personal receipt)")

    originals, offloaded = fc.resolve_originals(uuids)
    if not originals:
        p.error("no matching assets for the given uuids")
    by_uuid = {o["uuid"]: o for o in originals}
    on_disk = [o for o in originals if o["on_disk"]]

    date = args.date
    if not date:
        dates = photo_dates(uuids)
        date = min(dates.values()) if dates else datetime.date.today().isoformat()

    receipts_dir = os.path.join(args.ops_dir, "receipts")
    ledger_path = os.path.join(receipts_dir, "receipts-log.md")
    existing = set(os.listdir(receipts_dir)) if os.path.isdir(receipts_dir) else set()
    names = plan_receipt_names(existing, date, args.vendor, len(on_disk))
    plan = [{"uuid": o["uuid"], "out": n} for o, n in zip(on_disk, names)]

    if args.plan:
        print(f"PLAN — receipt: {args.vendor} {date}"
              f"{' $' + args.total if args.total else ''}{' lot ' + args.lot if args.lot else ''}")
        for entry in plan:
            print(f"  {entry['uuid'][:8]}  ->  ops/receipts/{entry['out']}")
        print(f"  ledger row -> {ledger_path}")
        print(f"  album add: {len(on_disk)} photo(s) -> 'Receipts' under 'Richmond General Archive'")
        print("  tag rg-sorted + rg-receipt (drops out of receipt queue AND item intake sweep)")
        if offloaded:
            print(f"  ⚠︎ OFFLOADED (download first, not filed): {', '.join(u[:8] for u in offloaded)}")
        return

    written = export_receipts(plan, by_uuid, receipts_dir)
    row = append_ledger(ledger_path, date, args.vendor, args.total, args.lot,
                        written, [o["uuid"] for o in on_disk])
    on_disk_uuids = [o["uuid"] for o in on_disk]
    album = fc.add_to_album("Receipts", on_disk_uuids)
    tag = fc.tag_keywords(["rg-sorted", "rg-receipt"], on_disk_uuids)
    print(json.dumps({"vendor": args.vendor, "date": date, "written": written,
                      "ledger": row, "album": album, "tag": tag,
                      "offloaded": offloaded}, indent=2))


if __name__ == "__main__":
    main()
