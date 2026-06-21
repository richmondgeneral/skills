#!/usr/bin/env python3
"""sharpen.py — deterministic unsharp mask (default) or NAFNet deblur (--deblur).

The DEFAULT path is pure PIL (no torch): a deterministic unsharp mask — faithful,
reproducible, safe to auto-run; it sharpens existing edges without inventing
content. Use it as the finishing pass after upres.py (Real-ESRGAN slightly
denoises; unsharp restores crispness).

--deblur loads a NAFNet/Restormer deblur model via spandrel (needs the rg-enhance
venv: torch + spandrel) for genuinely motion/defocus-blurred shots. It degrades
with an actionable message if the deblur weights are not installed.

CLI:
  sharpen.py --item-dir items/RG-XXXX [--amount 0.6] [--source hero.png] [--out hero.png]
  sharpen.py --item-dir items/RG-XXXX --deblur            # genuinely blurry shots
  sharpen.py <input> <output> [--amount 0.6] [--deblur]   # ad-hoc, no label.json
"""
from __future__ import annotations

import argparse
import os
import sys
import time

from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import enhance_common as ec  # noqa: E402

DEBLUR_WEIGHTS = os.path.expanduser("~/.cache/rg-enhance/weights/NAFNet-deblur.pth")


def _unsharp(img: "Image.Image", amount: float) -> "Image.Image":
    """Deterministic PIL unsharp mask. amount 0..2 maps to percent 0..200."""
    return img.convert("RGB").filter(
        ImageFilter.UnsharpMask(radius=2, percent=int(amount * 100), threshold=2))


def _deblur(img: "Image.Image") -> "Image.Image":
    if not os.path.isfile(DEBLUR_WEIGHTS):
        sys.stderr.write(
            f"sharpen.py: --deblur needs weights at {DEBLUR_WEIGHTS} (not installed).\n"
            "Use the default unsharp path, or fetch NAFNet/Restormer deblur weights into "
            "~/.cache/rg-enhance/weights/NAFNet-deblur.pth\n")
        raise SystemExit(4)
    import numpy as np
    import torch
    from spandrel import ImageModelDescriptor, ModelLoader
    model = ModelLoader().load_from_file(DEBLUR_WEIGHTS)
    if not isinstance(model, ImageModelDescriptor):
        sys.stderr.write(f"sharpen.py: unexpected model type {type(model)}\n")
        raise SystemExit(4)
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    model.to(dev).eval()
    arr = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(dev)
    with torch.no_grad():
        out = model(t).clamp(0, 1)
    out = (out.squeeze(0).permute(1, 2, 0).cpu().numpy() * 255.0).round().astype("uint8")
    return Image.fromarray(out)


def sharpen_file(src: str, out: str, amount: float, deblur: bool) -> dict:
    img = Image.open(src)
    t0 = time.time()
    result = _deblur(img) if deblur else _unsharp(img, amount)
    result.save(out)
    return {
        "tool": "sharpen.py",
        "model": "NAFNet-deblur" if deblur else "unsharp",
        "amount": None if deblur else amount,
        "src": os.path.basename(src), "out": os.path.basename(out),
        "wall_s": round(time.time() - t0, 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Unsharp mask (default) or NAFNet deblur")
    ap.add_argument("input", nargs="?", help="ad-hoc input image (with output)")
    ap.add_argument("output", nargs="?", help="ad-hoc output path")
    ap.add_argument("--item-dir", help="items/RG-XXXX (writes into it + records label.json)")
    ap.add_argument("--source", help="source filename in item dir (default: hero.*)")
    ap.add_argument("--out", help="output filename (relative to item dir); may overwrite hero")
    ap.add_argument("--amount", type=float, default=0.6, help="unsharp strength 0..2 (default 0.6)")
    ap.add_argument("--deblur", action="store_true", help="NAFNet deblur instead of unsharp")
    ap.add_argument("--no-update-label", action="store_true")
    a = ap.parse_args()

    if a.item_dir:
        src = ec.resolve_source(a.item_dir, a.source)
        out = ec.resolve_out(src, a.out, suffix="sharp", item_dir=a.item_dir)
    elif a.input and a.output:
        src, out = a.input, a.output
    else:
        ap.error("provide --item-dir, or both input and output")

    rec = sharpen_file(src, out, a.amount, a.deblur)
    if a.item_dir and not a.no_update_label:
        ec.append_pipeline(a.item_dir, rec)
    print(f"sharpen: {rec['model']} -> {out} ({rec['wall_s']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
