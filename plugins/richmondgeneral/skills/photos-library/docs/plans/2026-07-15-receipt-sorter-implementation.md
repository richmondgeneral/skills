# Receipt Sorter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Sweep receipt photos out of the Photos library into `ops/receipts/` + a ledger, mirroring the item intake sorter.

**Architecture:** A new `psi_db.py` reads Apple's ML "Receipt" labels from the Photos search index (`psi.sqlite`); `find_receipts.py` is the queue (cross-referenced into Photos.sqlite, `rg-sorted` excluded); `file_receipt.py` is the one canonical filing step (sips export → `ops/receipts/YYYY-MM-DD-<vendor>.jpeg`, ledger append, "Receipts" album, `rg-sorted`+`rg-receipt` tags), reusing `file_cluster`'s resolve/tag machinery.

**Tech Stack:** Python 3 stdlib (sqlite3, struct, uuid), macOS `sips`/`osascript`, pytest via `uv run --project skills/plugins/richmondgeneral`.

Design: `2026-07-15-receipt-sorter-design.md` (same dir). All DB opens MUST be `mode=ro&immutable=1`.

Repo root for paths below: `~/workspace/richmondgeneral/skills`. Test command:
`uv run --project plugins/richmondgeneral --extra dev pytest plugins/richmondgeneral/skills/photos-library/tests/ -v`
(run from the `skills/` repo root; adjust `--project` path if running from elsewhere).

---

### Task 1: `psi_db.py` — UUID reconstruction (pure logic, TDD)

**Files:**
- Create: `plugins/richmondgeneral/skills/photos-library/scripts/psi_db.py`
- Test: `plugins/richmondgeneral/skills/photos-library/tests/test_psi_db.py`

**Step 1: Write the failing test**

```python
import os, sqlite3, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import psi_db


def test_asset_uuid_little_endian_halves():
    # Live-verified 2026-07-15: psi assets(uuid_0,uuid_1) little-endian halves
    # reconstruct ZASSET.ZUUID EA161386-C707-4F77-B85A-B90BCD4864C9.
    u0 = struct.unpack("<q", bytes.fromhex("8613 16EA C707 4F77".replace(" ", "")))[0]
    u1 = struct.unpack("<q", bytes.fromhex("B85A B90B CD48 64C9".replace(" ", "")))[0]
    assert psi_db.asset_uuid(u0, u1) == "EA161386-C707-4F77-B85A-B90BCD4864C9"


def _mini_psi(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE groups(category INT2, content_string TEXT, normalized_string TEXT);
        CREATE TABLE ga(groupid INT, assetid INT);
        CREATE TABLE assets(uuid_0 INT, uuid_1 INT, creationDate INT);
        """
    )
    # NB: real psi content_string carries a trailing NUL -> match normalized_string.
    conn.execute("INSERT INTO groups(rowid, category, content_string, normalized_string) "
                 "VALUES (685, 1500, 'Receipt' || char(0), 'receipt')")
    conn.execute("INSERT INTO groups(rowid, category, content_string, normalized_string) "
                 "VALUES (684, 2800, 'Receipts' || char(0), 'receipts')")
    conn.execute("INSERT INTO groups(rowid, category, content_string, normalized_string) "
                 "VALUES (1, 1500, 'Dog' || char(0), 'dog')")
    u0 = struct.unpack("<q", bytes.fromhex("861316EAC7074F77"))[0]
    u1 = struct.unpack("<q", bytes.fromhex("B85AB90BCD4864C9"))[0]
    conn.execute("INSERT INTO assets(rowid, uuid_0, uuid_1, creationDate) VALUES (55, ?, ?, 0)", (u0, u1))
    conn.execute("INSERT INTO ga(groupid, assetid) VALUES (685, 55)")
    conn.execute("INSERT INTO ga(groupid, assetid) VALUES (1, 55)")
    conn.commit()
    conn.close()


def test_receipt_uuids_from_mini_psi(tmp_path):
    db = str(tmp_path / "psi.sqlite")
    _mini_psi(db)
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        got = psi_db.receipt_uuids(conn)
    assert got == {"EA161386-C707-4F77-B85A-B90BCD4864C9"}
```

**Step 2: Run test to verify it fails**

Run: `uv run --project plugins/richmondgeneral --extra dev pytest plugins/richmondgeneral/skills/photos-library/tests/test_psi_db.py -v`
Expected: FAIL / ERROR "No module named 'psi_db'"

**Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""Photos search-index (psi.sqlite) helpers — Apple-ML label lookups.

psi.sqlite lives at ``<library>/database/search/psi.sqlite`` and maps ML labels
("Receipt", "Document", …) to assets. Open it ``mode=ro&immutable=1`` only —
same iCloud-sync safety rule as Photos.sqlite.

Schema notes (live-verified 2026-07-15):
- ``groups.content_string`` carries a trailing NUL byte -> match on
  ``normalized_string`` instead.
- ``assets.uuid_0``/``uuid_1`` are the asset UUID as two little-endian signed
  64-bit halves; reconstructed value equals ``ZASSET.ZUUID``.
- Receipt groups: category 1500 (scene label "Receipt") and 2800 ("Receipts").
"""

import struct
import uuid as _uuid
from pathlib import Path

RECEIPT_NORMALIZED = ("receipt", "receipts")
RECEIPT_CATEGORIES = (1500, 2800)


def find_psi_db():
    p = Path.home() / "Pictures/Photos Library.photoslibrary/database/search/psi.sqlite"
    return str(p) if p.exists() else None


def asset_uuid(uuid_0, uuid_1):
    """Reconstruct ZASSET.ZUUID from psi assets(uuid_0, uuid_1) int halves."""
    return str(_uuid.UUID(bytes=struct.pack("<q", uuid_0) + struct.pack("<q", uuid_1))).upper()


def receipt_uuids(conn):
    """Set of ZUUIDs the Photos ML labeled as receipts (union of both groups)."""
    ph_cat = ",".join("?" for _ in RECEIPT_CATEGORIES)
    ph_norm = ",".join("?" for _ in RECEIPT_NORMALIZED)
    rows = conn.execute(
        f"SELECT DISTINCT a.uuid_0, a.uuid_1 FROM groups g "
        f"JOIN ga ON ga.groupid = g.rowid JOIN assets a ON a.rowid = ga.assetid "
        f"WHERE g.category IN ({ph_cat}) AND g.normalized_string IN ({ph_norm})",
        (*RECEIPT_CATEGORIES, *RECEIPT_NORMALIZED),
    ).fetchall()
    return {asset_uuid(u0, u1) for u0, u1 in rows}
```

**Step 4: Run test to verify it passes** — same command, expected PASS (2 tests).

**Step 5: Commit**

```bash
git add plugins/richmondgeneral/skills/photos-library/scripts/psi_db.py \
        plugins/richmondgeneral/skills/photos-library/tests/test_psi_db.py
git commit -m "photos-library: psi_db — Apple-ML receipt labels from psi.sqlite"
```

---

### Task 2: `file_cluster.py` — generalize the keyword tagger (TDD-light refactor)

**Files:**
- Modify: `plugins/richmondgeneral/skills/photos-library/scripts/file_cluster.py:191-210` (`tag_sorted`)

**Step 1:** Refactor `tag_sorted` into a generic `tag_keywords(keywords, uuids)`; keep `tag_sorted(sku, uuids)` as a thin wrapper so existing callers/tests are untouched:

```python
def tag_keywords(keywords, uuids):
    """Union the given keywords into each photo's keywords (preserves existing)."""
    kw_list = "{" + ", ".join(f'"{k}"' for k in keywords) + "}"
    uuid_list = "{" + ", ".join(f'"{u}"' for u in uuids) + "}"
    script = f'''
tell application "Photos"
    set addKw to {kw_list}
    repeat with u in {uuid_list}
        try
            set mi to (first media item whose id starts with (contents of u))
            set kw to keywords of mi
            if kw is missing value then set kw to {{}}
            repeat with k in addKw
                if kw does not contain (k as string) then set end of kw to (k as string)
            end repeat
            set keywords of mi to kw
        end try
    end repeat
    return "tagged"
end tell'''
    return _osascript(script)


def tag_sorted(sku, uuids):
    """Union rg-sorted + <sku> into each photo's keywords (preserves existing)."""
    return tag_keywords(["rg-sorted", sku], uuids)
```

**Step 2:** Run the existing suite: `... pytest .../tests/test_file_cluster.py -v` — all PASS (pure-logic tests don't touch this, this guards imports).

**Step 3: Commit** — `git commit -m "photos-library: file_cluster — extract generic tag_keywords helper"` (explicit path add).

---

### Task 3: `file_receipt.py` pure logic — slug, filename planning, ledger (TDD)

**Files:**
- Create: `plugins/richmondgeneral/skills/photos-library/scripts/file_receipt.py`
- Test: `plugins/richmondgeneral/skills/photos-library/tests/test_file_receipt.py`

**Step 1: Write the failing tests**

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import file_receipt as fr


def test_slugify_vendor():
    assert fr.slugify("Goodwill — Crystal Lake #2") == "goodwill-crystal-lake-2"


def test_plan_receipt_names_basic():
    out = fr.plan_receipt_names(existing=set(), date="2026-07-15", vendor="Goodwill", count=2)
    assert out == ["2026-07-15-goodwill.jpeg", "2026-07-15-goodwill-2.jpeg"]


def test_plan_receipt_names_never_clobbers():
    existing = {"2026-07-15-goodwill.jpeg", "2026-07-15-goodwill-2.jpeg"}
    out = fr.plan_receipt_names(existing=existing, date="2026-07-15", vendor="Goodwill", count=1)
    assert out == ["2026-07-15-goodwill-3.jpeg"]


def test_append_ledger_creates_header_then_appends(tmp_path):
    log = tmp_path / "receipts-log.md"
    fr.append_ledger(str(log), date="2026-07-15", vendor="Goodwill", total="12.99",
                     lot="GIBA-C2", files=["2026-07-15-goodwill.jpeg"], uuids=["EA161386-C707"])
    text = log.read_text()
    assert text.startswith("# Receipts Log")
    assert "| 2026-07-15 | Goodwill | $12.99 | GIBA-C2 | 2026-07-15-goodwill.jpeg | EA161386-C707 |" in text
    fr.append_ledger(str(log), date="2026-07-16", vendor="Salvation Army", total=None,
                     lot=None, files=["a.jpeg", "b.jpeg"], uuids=["U1", "U2"])
    text = log.read_text()
    assert text.count("# Receipts Log") == 1
    assert "| 2026-07-16 | Salvation Army |  |  | a.jpeg, b.jpeg | U1, U2 |" in text
```

**Step 2:** Run — FAIL "No module named 'file_receipt'".

**Step 3: Implementation** (pure part; CLI/integration comes in Task 4):

```python
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
import sys

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


def _taken(existing, name):
    return name in existing


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
            if not _taken(existing, cand):
                break
        existing.add(cand)
        names.append(cand)
    return names


def append_ledger(path, date, vendor, total, lot, files, uuids):
    """Append one row; create the file with its header if absent."""
    row = (f"| {date} | {vendor} | {'$' + str(total) if total else ''} | {lot or ''} "
           f"| {', '.join(files)} | {', '.join(u[:13] for u in uuids)} |\n")
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        if new:
            f.write(LEDGER_HEADER)
        f.write(row)
    return row.strip()
```

Note the ledger truncates UUIDs to 13 chars (readable, still greppable) — the full
UUIDs remain in Photos keywords/album.

**Step 4:** Run — 4 tests PASS.

**Step 5: Commit** — `git commit -m "photos-library: file_receipt pure logic — slug/name-plan/ledger (TDD)"`.

---

### Task 4: `file_receipt.py` integration + CLI

**Files:**
- Modify: `plugins/richmondgeneral/skills/photos-library/scripts/file_receipt.py` (append)

**Step 1: Append integration + main** (side effects mirror `file_cluster.main`; no unit tests — exercised via `--plan` and the live smoke in Task 6):

```python
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
    p.add_argument("--vendor", required=True, help='e.g. "Goodwill Crystal Lake"')
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
```

**Step 2:** Full suite green; then a `--plan` smoke against a real receipt UUID (read-only):
`python3 scripts/file_receipt.py --plan --vendor "Test" --uuids EA161386-C707-4F77-B85A-B90BCD4864C9`
Expected: PLAN block, no writes.

**Step 3: Commit** — `git commit -m "photos-library: file_receipt CLI — export/ledger/album/tag with --plan"`.

---

### Task 5: `find_receipts.py` — the queue

**Files:**
- Create: `plugins/richmondgeneral/skills/photos-library/scripts/find_receipts.py`

Pure logic already tested via psi_db; this script is thin glue (mirrors
`find_product_clusters.py` structure), so no new unit tests — live smoke in Task 6.

**Step 1: Write it**

```python
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
from datetime import datetime

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
```

**Step 2: Live read-only smoke**

Run: `python3 scripts/find_receipts.py --days 0 | head -20` (from the skill dir)
Expected: ~280 receipts listed, newest first, coverage line printed. Then
`--days 30 --hide-sorted` runs clean too.

**Step 3: Commit** — `git commit -m "photos-library: find_receipts — ML-labeled receipt queue"`.

---

### Task 6: SKILL.md v1.8 + live end-to-end smoke

**Files:**
- Modify: `plugins/richmondgeneral/skills/photos-library/SKILL.md` (version → 1.8, changelog entry, description trigger phrases, new "Receipt Sorter" section after the Intake Photo Sorter)

**Step 1:** Bump `metadata.version` to "1.8"; prepend changelog entry:

```
v1.8 - Receipt sorter (agent loop):
- find_receipts.py: queue of receipt photos via Apple's OWN ML labels in the
  Photos search index (psi.sqlite "Receipt" scene group; psi_db.py reconstructs
  ZUUIDs from little-endian uuid halves). --hide-sorted excludes filed ones.
- file_receipt.py: the ONE canonical receipt filing step — sips-exports to
  ops/receipts/YYYY-MM-DD-<vendor>.jpeg (never clobbers), appends the ledger
  row to ops/receipts/receipts-log.md (lot-tracker's cost feed), adds to the
  "Receipts" album, tags rg-sorted + rg-receipt. --plan dry-runs.
- file_cluster.py: tag_keywords() extracted (tag_sorted now wraps it).
- Photos labels lazily (overnight/on-power) — find_receipts prints its
  coverage date; a freshly shot receipt may take a day to appear.
```

Add trigger phrases to `description`: "sort receipts", "file receipts", "receipt photos", "receipts out of the library".

**Step 2:** Add the workflow section (after "Intake Photo Sorter"):

```markdown
## Receipt Sorter (agent loop — ML-labeled queue)

Receipts from buying trips get photographed alongside products. Photos' own ML
labels them; this loop files them into `ops/receipts/` + the ledger so the
lot-tracker sees every cost. Same shape as the item sorter: sweep → look →
confirm → file.

1. **Sweep the queue** — receipt-labeled photos, already-filed excluded:
   ```bash
   python3 scripts/find_receipts.py --hide-sorted --days 30 --json
   ```
   ⚠️ Photos labels lazily (overnight / on power): the output's
   `newest_labeled` date shows coverage — a receipt shot today may not be in
   the queue until tomorrow.

2. **Look at each candidate** (real vision) — confirm it IS a purchase receipt
   and READ vendor / date / total off it:
   ```bash
   python3 scripts/extract_photos.py --uuids <uuid,…> --resize 1024x1024 -o /tmp/rg-receipts
   ```

3. **Confirm with the user** — vendor, date, total, lot code (if this receipt
   belongs to a tracked lot, e.g. GIBA-C2). Multi-page receipt = one filing
   with several uuids.

4. **File it** — the ONE canonical step (dry-run first if unsure):
   ```bash
   python3 scripts/file_receipt.py --plan --uuids <uuids> --vendor "Goodwill" --total 12.99
   python3 scripts/file_receipt.py --uuids <uuids> --vendor "Goodwill" \
       --total 12.99 [--date YYYY-MM-DD] [--lot GIBA-C2]
   ```
   Exports to `ops/receipts/YYYY-MM-DD-<vendor>.jpeg`, appends the row to
   `ops/receipts/receipts-log.md`, adds to the "Receipts" album, and tags
   `rg-sorted` + `rg-receipt` — the photo drops out of this queue AND the item
   intake sweep. After filing, offer to record the cost against the lot
   (rg-lot-tracker).
```

**Step 3: Live end-to-end smoke (ONE real receipt, with owner-visible output):**
- `find_receipts.py --hide-sorted --json` → pick one candidate
- `extract_photos.py --uuids <u> --resize 1024x1024` → Read it, confirm receipt, read vendor/total
- `file_receipt.py --plan …` → verify intent
- `file_receipt.py …` (real) → verify: file in `ops/receipts/`, ledger row, album add, tags
- Re-run `find_receipts.py --hide-sorted` → the filed photo is GONE from the queue

**Step 4:** Full test suite green:
`uv run --project plugins/richmondgeneral --extra dev pytest plugins/richmondgeneral/skills/photos-library/tests/ -v`

**Step 5: Commit** — `git commit -m "photos-library v1.8: receipt sorter — SKILL.md loop + live smoke"`.

---

### Task 7: Release via the plugin marketplace loop

Per root CLAUDE.md (plugin sync rule, 2026-07-14):

**Step 1:** Bump `plugins/richmondgeneral/.claude-plugin/plugin.json` `version` 1.5.0 → **1.6.0** (no bump = no reinstall).
**Step 2:** `claude plugin validate .` from the `skills/` repo root — must pass (js-yaml strictness: check the new SKILL.md description quoting).
**Step 3:** Commit the bump; then `git fetch && git log origin/main..main` (expect possibly-foreign commits — verify coherent, never --force), push on clean fast-forward.
**Step 4:** `claude plugin marketplace update richmondgeneral && claude plugin update richmondgeneral@richmondgeneral`.
**Step 5:** Verify cache: `ls ~/.claude/plugins/cache/richmondgeneral/richmondgeneral/1.6.0/skills/photos-library/scripts/` contains the three new/changed scripts.
