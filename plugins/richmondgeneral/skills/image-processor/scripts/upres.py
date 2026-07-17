#!/usr/bin/env python3
"""upres.py — faithful local super-resolution (Real-ESRGAN via spandrel, MPS).

NON-GENERATIVE: a fixed convolutional SR model (RRDBNet). It sharpens and
enlarges existing pixels; it does NOT invent label text, maker's marks, or
composition, so it is safe to auto-run on labeled goods (unlike generative
upres / SUPIR, which stays showcase-only + judge-gated).

ENV: needs the dedicated rg-enhance venv (torch + spandrel — no 3.14 wheels, so
NOT in the plugin env). Invoke by absolute interpreter path:

  uv venv ~/.cache/rg-enhance --python 3.12
  uv pip install --python ~/.cache/rg-enhance torch torchvision pillow numpy spandrel
  ~/.cache/rg-enhance/bin/python upres.py --item-dir items/RG-XXXX --target-w 1500

Weights live at ~/.cache/rg-enhance/weights/{RealESRGAN_x2plus,RealESRGAN_x4plus}.pth

CLI:
  upres.py --item-dir items/RG-XXXX [--target-w 1500] [--source hero.png] [--out hero.png]
  upres.py <input> <output> [--target-w 1500]          # ad-hoc, no label.json
"""
from __future__ import annotations

import argparse
import os
import sys
import time

WEIGHTS = os.path.expanduser("~/.cache/rg-enhance/weights")
MODEL_FOR_SCALE = {2: "RealESRGAN_x2plus.pth", 4: "RealESRGAN_x4plus.pth"}
# Tile when an output dimension would exceed this, to keep MPS memory bounded.
# 3000 lets a typical 2x hero (~1000px -> ~2400px) run whole; 4x outputs tile.
TILE_THRESHOLD_PX = 3000

try:
    from PIL import Image
    import numpy as np
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import enhance_common as ec
except ImportError as e:  # noqa: BLE001
    sys.stderr.write(
        f"upres.py: missing base dependency ({e}).\n"
        "Run under the rg-enhance venv:\n"
        "  uv venv ~/.cache/rg-enhance --python 3.12\n"
        "  uv pip install --python ~/.cache/rg-enhance torch torchvision pillow numpy spandrel\n"
        "  ~/.cache/rg-enhance/bin/python upres.py ...\n")
    raise SystemExit(3)


def _device():
    import torch
    return "mps" if torch.backends.mps.is_available() else "cpu"


def _load_model(scale: int):
    from spandrel import ImageModelDescriptor, ModelLoader
    path = os.path.join(WEIGHTS, MODEL_FOR_SCALE[scale])
    if not os.path.isfile(path):
        sys.stderr.write(f"upres.py: weights missing: {path}\n")
        raise SystemExit(4)
    model = ModelLoader().load_from_file(path)
    if not isinstance(model, ImageModelDescriptor):
        sys.stderr.write(f"upres.py: unexpected model type {type(model)}\n")
        raise SystemExit(4)
    return model.to(_device()).eval()


def _run(model, img: "Image.Image") -> "Image.Image":
    """Run the SR model whole, or tiled (with overlap) for big inputs to bound MPS memory."""
    import torch
    dev = _device()
    arr = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    h, w, _ = arr.shape
    scale = model.scale

    def infer(a):
        t = torch.from_numpy(a).permute(2, 0, 1).unsqueeze(0).to(dev)
        with torch.no_grad():
            o = model(t).clamp(0, 1)
        return o.squeeze(0).permute(1, 2, 0).cpu().numpy()

    if max(h, w) * scale <= TILE_THRESHOLD_PX:
        out = infer(arr)
    else:
        tile, pad = 512, 32
        out = np.zeros((h * scale, w * scale, 3), dtype=np.float32)
        for y in range(0, h, tile):
            for x in range(0, w, tile):
                y0, x0 = max(0, y - pad), max(0, x - pad)
                y1, x1 = min(h, y + tile + pad), min(w, x + tile + pad)
                piece = infer(arr[y0:y1, x0:x1])
                ty, tx = (y - y0) * scale, (x - x0) * scale
                hh = min(tile, h - y) * scale
                ww = min(tile, w - x) * scale
                out[y * scale:y * scale + hh, x * scale:x * scale + ww] = \
                    piece[ty:ty + hh, tx:tx + ww]
    return Image.fromarray((out * 255.0).round().astype(np.uint8))


def upres_file(src: str, out: str, target_w: int) -> dict:
    img = Image.open(src)
    src_w = img.width
    scale = ec.pick_scale(src_w, target_w)
    t0 = time.time()
    if scale == 1:
        result = img.convert("RGB")           # already >= target width
        used = "none(skip)"
    else:
        result = _run(_load_model(scale), img)
        used = MODEL_FOR_SCALE[scale]
    if result.width < target_w:               # model under-shot tiny inputs -> Lanczos up
        new_h = round(result.height * target_w / result.width)
        result = result.resize((target_w, new_h), Image.LANCZOS)
    result.save(out)
    return {
        "tool": "upres.py", "model": used, "scale": scale,
        "src": os.path.basename(src), "out": os.path.basename(out),
        "src_w": src_w, "out_w": result.width, "device": _device(),
        "wall_s": round(time.time() - t0, 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Faithful Real-ESRGAN upscale (MPS)")
    ap.add_argument("input", nargs="?", help="ad-hoc input image (with output)")
    ap.add_argument("output", nargs="?", help="ad-hoc output path")
    ap.add_argument("--item-dir", help="items/RG-XXXX (writes into it + records label.json)")
    ap.add_argument("--source", help="source filename in item dir (default: hero.*)")
    ap.add_argument("--out", help="output filename (relative to item dir); may overwrite hero")
    ap.add_argument("--target-w", type=int, default=1500, help="min output width (default 1500)")
    ap.add_argument("--no-update-label", action="store_true")
    a = ap.parse_args()

    if a.item_dir:
        src = ec.resolve_source(a.item_dir, a.source)
        out = ec.resolve_out(src, a.out, suffix="upres", item_dir=a.item_dir)
    elif a.input and a.output:
        src, out = a.input, a.output
    else:
        ap.error("provide --item-dir, or both input and output")

    rec = upres_file(src, out, a.target_w)
    if a.item_dir and not a.no_update_label:
        ec.append_pipeline(a.item_dir, rec)
    print(f"upres: {rec['src_w']}px -> {rec['out_w']}px via {rec['model']} "
          f"({rec['device']}, {rec['wall_s']}s) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
