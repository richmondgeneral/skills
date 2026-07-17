#!/usr/bin/env python3
"""web_prep — normalize an item dir's PUBLIC images to web-serving size, in place.

The intake exporter used to copy full 48MP camera originals into ``items/RG-XXXX/``,
so GitHub Pages served 3–7 MB detail jpegs and 5+ MB files got uploaded to Square
(2026-07-15 audit: Listed item dirs ran 30–88 MB). The RAW ARCHIVE lives in the
Photos library (tagged by SKU) — the files in items/ are the public derivatives, so
downscaling them in place is safe and correct.

Caps (long edge, sips -Z, quality via formatOptions):
  hero.*        2000 px  q88   (matte reads it; keeps enough res for the cutout)
  detail-*.*    1600 px  q85
  square.jpg    1600 px  q85   (legacy raw squares; the pipeline square.png is untouched)

Never touched: square.png / cutout.png / card.png (pipeline products), qr-*.png,
restored.jpg, anything already within the cap AND under the byte threshold.

Usage:
  python3 web_prep.py items/RG-XXXX            # one item
  python3 web_prep.py --all items/             # every Listed item dir
  python3 web_prep.py items/RG-XXXX --dry-run  # report, change nothing

stdlib + sips only (bridge-safe, no PIL needed).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys

CAPS = (
    # (filename regex, max long edge px, jpeg quality)
    (re.compile(r"^hero\.(jpe?g|png)$", re.I), 2000, 88),
    (re.compile(r"^detail-[^/]*\.(jpe?g|png)$", re.I), 1600, 85),
    (re.compile(r"^square\.jpe?g$", re.I), 1600, 85),  # legacy raw square only
)
SKIP = re.compile(r"^(square\.png|cutout\.png|card\.png|restored\.jpe?g|qr-.*)$", re.I)
BYTE_THRESHOLD = 900_000  # files under ~0.9MB within cap are left alone


def _dims(path):
    out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", path],
                         capture_output=True, text=True, check=True).stdout
    w = h = 0
    for line in out.splitlines():
        if "pixelWidth" in line:
            w = int(line.split(":")[1])
        elif "pixelHeight" in line:
            h = int(line.split(":")[1])
    return w, h


def plan_item(item_dir):
    """Pure-ish planning: which files need work and why. Returns list of dicts."""
    work = []
    for name in sorted(os.listdir(item_dir)):
        if SKIP.match(name):
            continue
        rule = next(((rx, cap, q) for rx, cap, q in CAPS if rx.match(name)), None)
        if rule is None:
            continue
        _, cap, q = rule
        path = os.path.join(item_dir, name)
        size = os.path.getsize(path)
        try:
            w, h = _dims(path)
        except subprocess.CalledProcessError:
            continue
        long_edge = max(w, h)
        if long_edge > cap:
            # oversized → resize to cap + recompress
            work.append({"file": name, "px": long_edge, "cap": cap, "q": q,
                         "bytes": size})
        elif size > (1_200_000 if name.lower().endswith(".png") else 2_500_000):
            # within cap but heavy → recompress at current size (PNGs get pngquant)
            work.append({"file": name, "px": long_edge, "cap": long_edge, "q": q,
                         "bytes": size})
    return work


def prep_item(item_dir, dry_run=False):
    work = plan_item(item_dir)
    saved = 0
    for w in work:
        path = os.path.join(item_dir, w["file"])
        if dry_run:
            print(f"  [dry-run] {w['file']}: {w['px']}px/{w['bytes']//1024}KB "
                  f"-> cap {w['cap']}px q{w['q']}")
            continue
        if w["file"].lower().endswith(".png"):
            # PNG heroes can be transparent cutouts — resize ONLY, never convert
            # to jpeg (that would bake a background over the alpha channel).
            if w["px"] > w["cap"]:
                subprocess.run(["sips", "-Z", str(w["cap"]), path, "--out", path],
                               check=True, capture_output=True)
            # pngquant (if installed) palette-quantizes in place — keeps alpha +
            # extension, typically 60-70% smaller (2026-07-15 sweep: 63 PNGs, -83MB)
            import shutil
            if shutil.which("pngquant"):
                subprocess.run(["pngquant", "--quality=70-90", "--speed", "1",
                                "--force", "--output", path, path],
                               capture_output=True)  # rc 99 = quality floor; keep original
        else:
            subprocess.run(["sips", "-Z", str(w["cap"]),
                            "-s", "format", "jpeg", "-s", "formatOptions", str(w["q"]),
                            path, "--out", path], check=True, capture_output=True)
        new = os.path.getsize(path)
        saved += max(0, w["bytes"] - new)
        print(f"  {w['file']}: {w['bytes']//1024}KB -> {new//1024}KB")
    return {"item": os.path.basename(item_dir.rstrip('/')), "files": len(work),
            "saved_bytes": saved}


def main():
    ap = argparse.ArgumentParser(description="Normalize public item images to web size, in place.")
    ap.add_argument("target", help="items/RG-XXXX, or the items/ root with --all")
    ap.add_argument("--all", action="store_true", help="prep every Listed item dir under target")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    dirs = []
    if args.all:
        for d in sorted(glob.glob(os.path.join(args.target, "RG-*"))):
            lp = os.path.join(d, "label.json")
            if not os.path.isfile(lp):
                continue
            try:
                state = json.load(open(lp)).get("state")
            except json.JSONDecodeError:
                continue
            if state in ("Listed", "In Intake", "Priced"):
                dirs.append(d)
    else:
        dirs = [args.target]

    total = 0
    for d in dirs:
        r = prep_item(d, dry_run=args.dry_run)
        if r["files"]:
            print(f"{r['item']}: {r['files']} file(s), saved {r['saved_bytes']//1_000_000}MB")
        total += r["saved_bytes"]
    print(f"TOTAL saved: {total//1_000_000}MB across {len(dirs)} item dir(s)")


if __name__ == "__main__":
    main()
