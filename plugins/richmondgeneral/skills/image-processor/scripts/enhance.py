#!/usr/bin/env python3
"""enhance.py — one-pass faithful enhance chain: upres -> sharpen -> hero.enhanced.png.

Runs in the rg-enhance venv and imports upres + sharpen directly (same venv, no
subprocess). NON-DESTRUCTIVE on purpose: it writes a NEW hero.enhanced.png and
never overwrites the source hero — the operator reviews, then promotes it.

matte.py is intentionally a SEPARATE downstream step (it lives in the rg-matte
venv and handles RGBA alpha), run after promoting the enhanced hero — exactly as
the existing flow does (SPEC §5):

    ~/.cache/rg-enhance/bin/python enhance.py --item-dir items/RG-XXXX   # -> hero.enhanced.png
    cp items/RG-XXXX/hero.enhanced.png items/RG-XXXX/hero.png            # promote after review
    ~/.cache/rg-matte/bin/python matte.py --item-dir items/RG-XXXX
    python items/scripts/build_gallery.py --relink-cards

CLI:
  enhance.py --item-dir items/RG-XXXX [--target-w 1500] [--amount 0.6] [--deblur]
             [--skip-upres] [--skip-sharpen] [--source hero.png] [--out hero.enhanced.png]
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import enhance_common as ec  # noqa: E402
import sharpen  # noqa: E402
import upres  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="One-pass faithful enhance (upres -> sharpen)")
    ap.add_argument("--item-dir", required=True)
    ap.add_argument("--source", help="source filename in item dir (default: hero.*)")
    ap.add_argument("--out", help="output filename in item dir (default: hero.enhanced.png)")
    ap.add_argument("--target-w", type=int, default=1500)
    ap.add_argument("--amount", type=float, default=0.6)
    ap.add_argument("--deblur", action="store_true", help="NAFNet deblur instead of unsharp")
    ap.add_argument("--skip-upres", action="store_true")
    ap.add_argument("--skip-sharpen", action="store_true")
    ap.add_argument("--no-update-label", action="store_true")
    a = ap.parse_args()

    src = ec.resolve_source(a.item_dir, a.source)
    out = ec.resolve_out(src, a.out or "hero.enhanced.png", suffix="enhanced",
                         item_dir=a.item_dir)
    if a.skip_upres and a.skip_sharpen:
        ap.error("nothing to do (both stages skipped)")

    records = []
    with tempfile.TemporaryDirectory() as td:
        cur = src
        if not a.skip_upres:
            mid = os.path.join(td, "upres.png")
            records.append(upres.upres_file(cur, mid, a.target_w))
            cur = mid
        if not a.skip_sharpen:
            mid = os.path.join(td, "sharp.png")
            records.append(sharpen.sharpen_file(cur, mid, a.amount, a.deblur))
            cur = mid
        Image.open(cur).save(out)

    if not a.no_update_label:
        for r in records:
            r["out"] = os.path.basename(out)
            ec.append_pipeline(a.item_dir, r)
    print(f"enhance: {' -> '.join(r['model'] for r in records)} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
