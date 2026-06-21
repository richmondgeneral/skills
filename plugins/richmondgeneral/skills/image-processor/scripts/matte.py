#!/usr/bin/env python3
"""matte.py — local, non-generative transparent cutout + uniform derived views.

Produces the "one transparent master, many views" asset set for an item:

  cutout.png   true transparent matte of the item (BiRefNet via rembg, MIT)
  square.png   cutout floated/centered on a 1:1 TRANSPARENT canvas  -> Square (crop-safe)
  card.png     cutout floated/centered on a fixed 5:7 TRANSPARENT canvas -> gallery card

Both derived views stay transparent on purpose: Square renders them clean on its
white grid, and the site card gets its background COLOR from CSS — the SAME asset
serves both, and the item's real proportions stop mattering (uniform grid).

NON-GENERATIVE: BiRefNet only computes an alpha matte; it never repaints pixels,
so it cannot fabricate a maker's mark or change composition. Deterministic.

ENV: needs `rembg` + `onnxruntime` + `pillow`, which don't ship wheels for the
plugin's Python 3.14 env. Run under the dedicated matte venv instead:

  uv venv ~/.cache/rg-matte --python 3.12
  uv pip install --python ~/.cache/rg-matte rembg onnxruntime pillow numpy
  ~/.cache/rg-matte/bin/python matte.py --item-dir items/RG-0025

CLI:
  matte.py --item-dir items/RG-XXXX [--source hero.png] [--model birefnet-general]
  matte.py <input.png> <out_dir>            # ad-hoc, no label.json update
  matte.py --item-dir items/RG-XXXX --no-square   # skip a derived view
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

# Fail early with an actionable message if the matte deps aren't present.
try:
    from rembg import new_session, remove
    from PIL import Image
except ImportError as e:  # noqa: BLE001
    sys.stderr.write(
        f"matte.py: missing dependency ({e}).\n"
        "Run under the matte venv:\n"
        "  uv venv ~/.cache/rg-matte --python 3.12\n"
        "  uv pip install --python ~/.cache/rg-matte rembg onnxruntime pillow numpy\n"
        "  ~/.cache/rg-matte/bin/python matte.py ...\n")
    raise SystemExit(3)

DEFAULT_MODEL = "birefnet-general"      # high-res matte; falls back if unavailable
MODEL_FALLBACKS = ["isnet-general-use", "u2net"]
DEFAULT_FILL = 0.86
SQUARE_PX = 1600
CARD_W = 1000                            # 5:7 -> 1000x1400


def make_cutout(src_path: str, model: str) -> Image.Image:
    session = None
    for name in [model] + MODEL_FALLBACKS:
        try:
            session = new_session(name)
            if name != model:
                sys.stderr.write(f"matte.py: model '{model}' unavailable, used '{name}'\n")
            break
        except Exception:  # noqa: BLE001
            continue
    out = remove(open(src_path, "rb").read(), session=session, post_process_mask=True)
    return Image.open(io.BytesIO(out)).convert("RGBA")


def trim_to_alpha(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    return im.crop(bbox) if bbox else im


def float_on_canvas(item: Image.Image, cw: int, ch: int, fill: float) -> Image.Image:
    iw, ih = item.size
    scale = min(cw * fill / iw, ch * fill / ih)
    nw, nh = max(1, round(iw * scale)), max(1, round(ih * scale))
    r = item.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    canvas.alpha_composite(r, ((cw - nw) // 2, (ch - nh) // 2))
    return canvas


def update_label(item_dir: str, wrote: dict, model: str) -> None:
    lj = os.path.join(item_dir, "label.json")
    if not os.path.isfile(lj):
        return
    import datetime
    data = json.load(open(lj, encoding="utf-8"))
    photos = data.setdefault("photos", {})
    for role, fname in wrote.items():
        photos[role] = fname
    data["matte"] = {
        "model": model, "tool": "image-processor/matte.py (BiRefNet/rembg)",
        "non_generative": True,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "outputs": list(wrote.values()),
    }
    with open(lj, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Local transparent cutout + uniform views")
    ap.add_argument("input", nargs="?", help="ad-hoc input image (with out_dir)")
    ap.add_argument("out_dir", nargs="?", help="ad-hoc output dir")
    ap.add_argument("--item-dir", help="items/RG-XXXX (writes into it + updates label.json)")
    ap.add_argument("--source", default=None, help="source filename in item dir (default: hero.*)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--fill", type=float, default=DEFAULT_FILL)
    ap.add_argument("--square-px", type=int, default=SQUARE_PX)
    ap.add_argument("--card-w", type=int, default=CARD_W)
    ap.add_argument("--no-square", action="store_true")
    ap.add_argument("--no-card", action="store_true")
    ap.add_argument("--no-update-label", action="store_true")
    a = ap.parse_args()

    if a.item_dir:
        item_dir = a.item_dir
        if a.source:
            src = os.path.join(item_dir, a.source)
        else:
            import glob
            hits = sorted(glob.glob(os.path.join(item_dir, "hero.*")))
            hits = [h for h in hits if h.lower().endswith((".png", ".jpg", ".jpeg"))]
            if not hits:
                sys.stderr.write(f"matte.py: no hero.* in {item_dir}\n")
                return 2
            src = hits[0]
        out_dir = item_dir
    elif a.input and a.out_dir:
        src, out_dir = a.input, a.out_dir
        os.makedirs(out_dir, exist_ok=True)
    else:
        ap.error("provide --item-dir, or both input and out_dir")

    cutout = trim_to_alpha(make_cutout(src, a.model))
    lo, hi = cutout.getchannel("A").getextrema()
    if hi == lo:
        sys.stderr.write("matte.py: matte produced no transparency — aborting (bad source?)\n")
        return 2

    wrote = {}
    cpath = os.path.join(out_dir, "cutout.png")
    cutout.save(cpath)
    wrote["cutout"] = "cutout.png"
    if not a.no_square:
        sq = float_on_canvas(cutout, a.square_px, a.square_px, a.fill)
        sq.save(os.path.join(out_dir, "square.png"))
        wrote["square"] = "square.png"
    if not a.no_card:
        card = float_on_canvas(cutout, a.card_w, round(a.card_w * 7 / 5), a.fill)
        card.save(os.path.join(out_dir, "card.png"))
        wrote["card"] = "card.png"

    if a.item_dir and not a.no_update_label:
        update_label(a.item_dir, wrote, a.model)

    print(f"matte: cutout {cutout.size} (alpha {lo}-{hi}) -> {', '.join(wrote.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
