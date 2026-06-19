#!/usr/bin/env python3
"""Library-based intake: pull an album/tag of originals into an item folder.

Given ``--sku`` and ``--album``/``--keyword``, this finds the matching originals
in the Photos library, converts them with ``sips`` into ``items/RG-XXXX/``
(``hero.jpeg`` + ``detail-1.jpeg`` ...), reports any iCloud-offloaded originals,
and stubs ``label.json``. It replaces the retired ``catalog_pipeline/images/``
staging folder.

This is the FIRST step of intake, not the whole thing. Per the rg-full-auto
definition of done an item isn't complete until it has a full real photo set AND
final research-based pricing. After this helper you still:
  - run image-processor on hero.jpeg for background removal (this writes the raw
    original as the hero);
  - rename detail-N.* to semantic names (detail-back / detail-mark / detail-tag);
  - research + set final pricing and fill label.json;
  - run the rg-full-auto Square / label / publish phases.
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import photos_db

DEFAULT_ITEMS_DIR = os.path.expanduser("~/workspace/richmondgeneral/items")
PAGES_BASE = "https://richmondgeneral.github.io/items"


def find_photos_library():
    p = Path.home() / "Pictures/Photos Library.photoslibrary"
    return str(p) if p.exists() else None


def sips_convert(src, dst, fmt="jpeg", quality=90, resize=None):
    """Convert/resize an image with macOS-native sips (raises on failure)."""
    cmd = ["sips", "-s", "format", fmt]
    if fmt == "jpeg":
        cmd += ["-s", "formatOptions", str(quality)]
    if resize:
        w, h = (int(n) for n in str(resize).lower().split("x"))
        cmd += ["-Z", str(max(w, h))]
    cmd += [src, "--out", dst]
    subprocess.run(cmd, check=True, capture_output=True)


def fetch_assets(conn, album, keyword, limit):
    """Matching ZASSET rows. Favorites first (hero candidate), then chronological."""
    conditions = ["a.ZTRASHEDSTATE = 0", "a.ZHIDDEN = 0", "a.ZKIND = 0"]
    params = []
    if album:
        frag, p = photos_db.album_condition(conn, album)
        conditions.append(frag)
        params.extend(p)
    if keyword:
        frag, p = photos_db.keyword_condition(conn, keyword)
        conditions.append(frag)
        params.extend(p)
    where = " AND ".join(conditions)
    query = f"""
        SELECT a.ZUUID, a.ZUNIFORMTYPEIDENTIFIER, aa.ZORIGINALFILENAME,
               a.ZWIDTH, a.ZHEIGHT, a.ZFAVORITE
        FROM ZASSET a
        LEFT JOIN ZADDITIONALASSETATTRIBUTES aa ON a.ZADDITIONALATTRIBUTES = aa.Z_PK
        WHERE {where}
        ORDER BY a.ZFAVORITE DESC, a.ZDATECREATED ASC
        LIMIT ?
    """
    params.append(limit)
    return conn.execute(query, params).fetchall()


def stub_label(sku):
    """A blank label.json matching the RG schema — values filled during intake."""
    return {
        "sku": sku,
        "product_name": "",
        "attributes": "",
        "price": "",
        "condition": "",
        "condition_notes": "",
        "eye_color": "",
        "measurements_in": {},     # {"l":.., "w":.., "h":..} when known; drives oversize
        "buyer_questions": [],     # [{"q":.., "a":.., "posted_to":[..]}]
        "oversize": False,         # recompute from measurements_in via compute_oversize
        "state": "Intake",
        "target_channels": [],
        "channels": {
            "github_page": {"status": "draft", "url": f"{PAGES_BASE}/{sku}/"},
            "square": {"status": "pending", "object_id": None, "buy_link": None},
            "ebay": {"status": "not_listed", "item_id": None, "url": None},
            "whatnot": {"status": "not_listed"},
            "marketplace": {"status": "not_listed", "url": None},
        },
        "qr_code_url": f"{PAGES_BASE}/{sku}/",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Pull an album/tag of originals into an item folder (library-based intake)"
    )
    parser.add_argument("--sku", required=True, help="Target SKU / item folder, e.g. RG-0028")
    parser.add_argument("--album", help="Source album name (e.g. an Intake album)")
    parser.add_argument("--keyword", "--tag", dest="keyword", help="Source keyword/tag")
    parser.add_argument("--items-dir", default=DEFAULT_ITEMS_DIR,
                        help=f"Items repo dir (default: {DEFAULT_ITEMS_DIR})")
    parser.add_argument("--hero", help="Substring of an original's filename to use as the hero "
                                       "(else the favorite, else the first photo)")
    parser.add_argument("--limit", type=int, default=50, help="Max photos to pull (default 50)")
    parser.add_argument("--format", default="jpeg", choices=["jpeg", "png"], help="Output format")
    parser.add_argument("--quality", type=int, default=90, help="JPEG quality 1-100 (default 90)")
    parser.add_argument("--resize", help="Bound the longest side to fit WxH (e.g. 2000x2000)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing images / label.json")
    parser.add_argument("--library", help="Path to Photos Library (auto-detected)")
    parser.add_argument("--json", action="store_true", help="Emit a JSON summary")
    args = parser.parse_args()

    if not re.match(r"^RG-\d{4}$", args.sku):
        print(f"Error: --sku must look like RG-0028 (got '{args.sku}')", file=sys.stderr)
        return 1
    if not args.album and not args.keyword:
        print("Error: provide --album or --keyword/--tag", file=sys.stderr)
        return 1
    if args.resize and not re.match(r"^\d+x\d+$", args.resize):
        print("Error: --resize must be WxH (e.g. 2000x2000)", file=sys.stderr)
        return 1
    if not 1 <= args.quality <= 100:
        print("Error: --quality must be between 1 and 100", file=sys.stderr)
        return 1

    library = args.library or find_photos_library()
    if not library:
        print("Error: Could not find Photos Library", file=sys.stderr)
        return 1
    db_path = os.path.join(library, "database/Photos.sqlite")

    item_dir = os.path.join(args.items_dir, args.sku)
    hero_name = f"hero.{args.format}"
    populated = os.path.exists(os.path.join(item_dir, hero_name)) or \
        os.path.exists(os.path.join(item_dir, "index.html"))
    if populated and not args.force:
        print(f"Error: {args.sku} already looks populated (hero/index.html present) — "
              f"use --force to overwrite.", file=sys.stderr)
        return 1

    with sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True) as conn:
        if args.album and not photos_db.album_exists(conn, args.album):
            print(f"Error: album '{args.album}' not found. Known: "
                  f"{', '.join(photos_db.list_albums(conn, 15))}", file=sys.stderr)
            return 1
        if args.keyword and not photos_db.keyword_exists(conn, args.keyword):
            print(f"Error: keyword/tag '{args.keyword}' not found.", file=sys.stderr)
            return 1
        # Fetch a generous candidate pool so offloaded originals don't crowd out
        # the on-disk ones — we then take the first --limit that are actually on
        # disk. (Favorites sort first, so the hero stays a favorite when present.)
        pool = fetch_assets(conn, args.album, args.keyword, min(max(args.limit * 4, 100), 500))

    if not pool:
        print("No matching photos found.", file=sys.stderr)
        return 1

    # Walk the pool in order; collect on-disk originals up to --limit, tracking
    # offloaded ones encountered along the way so we can report them.
    resolved, offloaded = [], []
    for uuid, ftype, orig_name, w, h, fav in pool:
        ext = ftype.split(".")[-1] if ftype else "heic"
        src = os.path.join(library, f"originals/{uuid[0].upper()}/{uuid}.{ext}")
        rec = {"src": src, "orig": orig_name or f"{uuid[:8]}.{ext}", "w": w, "h": h}
        if os.path.exists(src):
            resolved.append(rec)
            if len(resolved) >= args.limit:
                break
        else:
            offloaded.append(rec)

    # Pick the hero (explicit --hero substring → favorite/first fallback).
    hero_idx = 0
    if args.hero and resolved:
        match = next((i for i, r in enumerate(resolved)
                      if args.hero.lower() in (r["orig"] or "").lower()), None)
        if match is None:
            print(f"⚠️  --hero '{args.hero}' matched no on-disk original; using favorite/first.",
                  file=sys.stderr)
        else:
            hero_idx = match

    os.makedirs(item_dir, exist_ok=True)
    written = []
    if resolved:
        hero = resolved.pop(hero_idx)
        try:
            sips_convert(hero["src"], os.path.join(item_dir, hero_name),
                         args.format, args.quality, args.resize)
            written.append({"role": "hero", "file": hero_name, "from": hero["orig"]})
            print(f"✓ {hero_name:<14} ← {hero['orig']} ({hero['w']}x{hero['h']})")
        except subprocess.CalledProcessError as e:
            msg = e.stderr.decode()[:80] if e.stderr else "sips error"
            print(f"✗ hero failed ({hero['orig']}): {msg}", file=sys.stderr)
        for n, r in enumerate(resolved, 1):
            dst_name = f"detail-{n}.{args.format}"
            try:
                sips_convert(r["src"], os.path.join(item_dir, dst_name),
                             args.format, args.quality, args.resize)
                written.append({"role": "detail", "file": dst_name, "from": r["orig"]})
                print(f"✓ {dst_name:<14} ← {r['orig']} ({r['w']}x{r['h']})")
            except subprocess.CalledProcessError as e:
                msg = e.stderr.decode()[:80] if e.stderr else "sips error"
                print(f"✗ {dst_name} failed ({r['orig']}): {msg}", file=sys.stderr)

    if offloaded:
        print(f"\n☁︎ {len(offloaded)} original(s) offloaded to iCloud (not on disk), skipped:",
              file=sys.stderr)
        for r in offloaded[:12]:
            print(f"    - {r['orig']}", file=sys.stderr)
        if len(offloaded) > 12:
            print(f"    ...and {len(offloaded) - 12} more", file=sys.stderr)
        print('  Download in Photos (select → File ▸ "Download Originals") and re-run with --force.',
              file=sys.stderr)

    label_path = os.path.join(item_dir, "label.json")
    label_written = False
    if not os.path.exists(label_path) or args.force:
        with open(label_path, "w") as f:
            json.dump(stub_label(args.sku), f, indent=2, ensure_ascii=False)
            f.write("\n")
        label_written = True
        print(f"✓ {'label.json':<14} (stub)")
    else:
        print("· label.json exists — left as-is (use --force to overwrite)")

    summary = {
        "sku": args.sku,
        "item_dir": item_dir,
        "written": written,
        "offloaded": [r["orig"] for r in offloaded],
        "label_stubbed": label_written,
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"\n{len(written)} image(s) → {item_dir}")
        print("Not done yet (definition of done = full real photo set + final pricing):")
        print("  1. image-processor on hero.jpeg for background removal (this hero is the raw original)")
        print("  2. rename detail-N.* to semantic names (detail-back / detail-mark / detail-tag)")
        print("  3. research + set final pricing; fill label.json")
        print("  4. run rg-full-auto for Square + label + publish")
        if offloaded:
            print(f"  ⚠️  {len(offloaded)} offloaded original(s) skipped — download + re-run --force")

    return 0


if __name__ == "__main__":
    sys.exit(main())
