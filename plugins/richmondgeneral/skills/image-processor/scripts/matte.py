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

ORIENTATION: right-angle rotation is lossless and matting is orientation-agnostic,
so orientation is fixed on the clean cutout AFTER bg-removal. Source images that
come in sideways with NO EXIF flag (physical pixel rotation) are the hard case:
- `--rotate {90,180,270}` = deterministic lossless CCW rotation, picked by LOOKING
  at the image (the reliable path; the agent/operator chooses).
- `--auto-upright` = best-effort OSD, applied ONLY on a confident reading. OSD is
  unreliable on ornate covers / sparse labels (a Victorian book read 180° at 0.60
  conf), so it deliberately no-ops when unsure and leaves it for the hero_qa flag.

CLI:
  matte.py --item-dir items/RG-XXXX [--source hero.png] [--model birefnet-general]
  matte.py --item-dir items/RG-XXXX --rotate 90       # came in sideways -> fix
  matte.py <input.png> <out_dir>            # ad-hoc, no label.json update
  matte.py --item-dir items/RG-XXXX --no-square   # skip a derived view
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
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


# Right-angle rotation is LOSSLESS and orientation-agnostic for matting, so we
# fix orientation AFTER the cutout (transparent corners stay clean). Auto-detect
# is OSD-based and only trustworthy on legible printed text — it is unreliable on
# ornate/decorative covers and sparse labels (observed: a Victorian book cover
# read 180° at conf 0.60; a rotated cart label gave no reading). So auto only
# fires on a CONFIDENT reading; otherwise leave it for the hero_qa flag + a
# human/agent-chosen --rotate. Don't guess.
AUTO_UPRIGHT_MIN_CONF = 1.0


def _osd_rotate(path) -> "tuple[int, float] | None":
    """Tesseract OSD via the CLI (robust to pytesseract's fragile error decode).
    Returns (rotate_cw_degrees_to_upright, confidence) or None if no reading."""
    try:
        out = subprocess.run(["tesseract", str(path), "stdout", "--psm", "0"],
                             capture_output=True, text=True, timeout=30).stdout
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    m_r = re.search(r"Rotate:\s*(\d+)", out)
    if not m_r:
        return None
    m_c = re.search(r"Orientation confidence:\s*([\d.]+)", out)
    return int(m_r.group(1)), (float(m_c.group(1)) if m_c else 0.0)


def auto_upright(cutout: "Image.Image", src_path: str):
    """Best-effort OSD upright (high-conf only). Returns (img, applied_deg, note)."""
    osd = _osd_rotate(src_path)
    if osd is None:
        return cutout, 0, "auto-upright: no OSD reading — left as-is"
    rot, conf = osd
    if rot == 0:
        return cutout, 0, f"auto-upright: OSD already upright (0°, conf {conf:.2f})"
    if rot in (90, 180, 270) and conf >= AUTO_UPRIGHT_MIN_CONF:
        return cutout.rotate(-rot, expand=True), rot, f"auto-upright: OSD {rot}° conf {conf:.2f} applied"
    return cutout, 0, f"auto-upright: OSD {rot}° conf {conf:.2f} below {AUTO_UPRIGHT_MIN_CONF} — left as-is (flag, don't guess)"


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


def update_label(item_dir: str, wrote: dict, model: str, orientation=None) -> None:
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
        "orientation": orientation or "as-shot",
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
    ap.add_argument("--rotate", type=int, choices=[90, 180, 270], default=None,
                   help="lossless CCW rotation of the cutout for items that came in sideways "
                        "(operator/agent picks it by looking — the reliable path)")
    ap.add_argument("--auto-upright", action="store_true",
                   help="best-effort OSD upright, high-conf only; no-ops on ornate/sparse imagery")
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

    # Fix orientation on the clean cutout (lossless for right angles), then re-trim.
    upright_note = None
    if a.rotate:
        cutout = trim_to_alpha(cutout.rotate(a.rotate, expand=True))
        upright_note = f"manual rotate {a.rotate}° CCW"
    elif a.auto_upright:
        cutout, applied, upright_note = auto_upright(cutout, src)
        if applied:
            cutout = trim_to_alpha(cutout)
    if upright_note:
        print(upright_note)

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
        update_label(a.item_dir, wrote, a.model, orientation=upright_note)

    print(f"matte: cutout {cutout.size} (alpha {lo}-{hi}) -> {', '.join(wrote.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
