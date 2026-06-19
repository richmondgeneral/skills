#!/usr/bin/env python3
"""Standardize a photo into a catalog-quality PUBLIC image per the RG listing SOP.

Produces a cohesive "thematic thread" public image: **square 1:1, object centered,
color-corrected toward neutral lighting, background removed (transparent)**. It only
changes color and geometry — it never edits the object's content, so physical flaws
(chips, crazing, wear) are preserved per the honesty rule.

Pipeline: color-correct (gray-world white balance + mild auto-contrast) -> background
removal (reuses process.py's model routing/fallbacks) -> square pad + center -> resize.
Output is a transparent PNG. The raw input is never modified; results go to --output.

Run via `uv run python standardize.py ...` (Pillow lives in the uv env). Background
removal is an AI call (Gemini / remove.bg) and needs the usual keys + credits; the
color + square steps are deterministic and offline. `--no-bg` skips bg removal (e.g.
to re-square an already-transparent hero without another API call).
"""
import argparse
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageOps, ImageStat, ImageFilter
from PIL.PngImagePlugin import PngInfo

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESS_PY = os.path.join(SCRIPT_DIR, "process.py")


def _split_alpha(img):
    """(rgb, alpha-or-None) — so color ops never destroy a transparent background."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        return rgba.convert("RGB"), rgba.getchannel("A")
    return img.convert("RGB"), None


def _merge_alpha(rgb, alpha):
    if alpha is None:
        return rgb
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def gray_world_white_balance(img, clamp=(0.6, 1.7)):
    """Neutralize a lighting color cast: scale R/G/B so each channel mean matches the
    overall gray mean. Clamped so we correct the cast without wild shifts. Preserves alpha."""
    rgb, alpha = _split_alpha(img)
    r, g, b = ImageStat.Stat(rgb).mean
    gray = (r + g + b) / 3.0

    def scale(m):
        s = gray / m if m > 1e-6 else 1.0
        return max(clamp[0], min(clamp[1], s))

    sr, sg, sb = scale(r), scale(g), scale(b)
    rC, gC, bC = rgb.split()
    rC = rC.point(lambda v: min(255, int(v * sr)))
    gC = gC.point(lambda v: min(255, int(v * sg)))
    bC = bC.point(lambda v: min(255, int(v * sb)))
    return _merge_alpha(Image.merge("RGB", (rC, gC, bC)), alpha)


def color_correct(img):
    """Gray-world white balance + a mild auto-contrast (exposure tidy). Content-safe;
    preserves a transparent background."""
    rgb, alpha = _split_alpha(gray_world_white_balance(img))
    return _merge_alpha(ImageOps.autocontrast(rgb, cutoff=0.5), alpha)


def square_pad_centered(img, fill=0.85, size=2000, shadow=False, bg=(0, 0, 0, 0)):
    """Crop to the object (alpha bbox when present), then center it on a transparent
    square canvas so the longest side fills `fill` fraction of the canvas.
    Adds an optional soft drop shadow for grounding."""
    rgba = img.convert("RGBA")
    bbox = rgba.getchannel("A").getbbox() or rgba.getbbox() or (0, 0, rgba.width, rgba.height)
    obj = rgba.crop(bbox)
    w, h = obj.size
    
    # Calculate canvas side to ensure object fills `fill` of the frame
    side = int(round(max(w, h) / fill)) if fill > 0 else max(w, h)
    canvas = Image.new("RGBA", (side, side), bg)
    
    paste_x = (side - w) // 2
    paste_y = (side - h) // 2
    
    # Apply grounding shadow if requested
    if shadow:
        # 40% opacity shadow, blurred
        shadow_mask = obj.getchannel("A").point(lambda a: int(a * 0.4))
        shadow_img = Image.new("RGBA", obj.size, (0, 0, 0, 0))
        shadow_img.putalpha(shadow_mask)
        shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(10))
        # Drop it 15 pixels downwards
        canvas.paste(shadow_img, (paste_x, paste_y + 15), shadow_img)

    canvas.paste(obj, (paste_x, paste_y), obj)
    if size and side != size:
        canvas = canvas.resize((size, size), Image.LANCZOS)
    return canvas


def remove_background(src, dst, model=None, allow_rect_mask=False):
    """Reuse process.py's routing/fallbacks for the transparent cutout (same interpreter).
    Surfaces process.py's own error (rect-mask / credits / etc.) instead of swallowing it."""
    cmd = [sys.executable, PROCESS_PY, src, "-o", dst, "--task", "remove-bg"]
    if model:
        cmd += ["--model", model]
    if allow_rect_mask:
        cmd += ["--allow-rect-mask"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPT_DIR)
    if r.returncode != 0:
        raise RuntimeError("background removal failed:\n" + (r.stderr.strip() or r.stdout.strip()))


def standardize(input_path, output_path, do_color=True, do_bg=True, fill=0.85, size=2000,
                shadow=False, copyright_text=None, sku=None, model=None, allow_rect_mask=False):
    with tempfile.TemporaryDirectory() as td:
        cur = input_path
        if do_color:
            cc = os.path.join(td, "cc.png")
            color_correct(Image.open(input_path)).save(cc)
            cur = cc
        if do_bg:
            transp = os.path.join(td, "transp.png")
            remove_background(cur, transp, model=model, allow_rect_mask=allow_rect_mask)
            cur = transp
            
        final_img = square_pad_centered(Image.open(cur), fill=fill, size=size, shadow=shadow)
        
        # PIL drops GPS and device EXIF automatically when saving without `exif` kwarg.
        # We explicitly inject our provenance metadata here.
        metadata = PngInfo()
        if copyright_text:
            metadata.add_text("Copyright", copyright_text)
        if sku:
            metadata.add_text("Title", sku)
            
        final_img.save(output_path, "PNG", pnginfo=metadata)
    return output_path


def main():
    p = argparse.ArgumentParser(description="Standardize a photo into a public catalog image.")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True, help="output PNG path")
    p.add_argument("--no-color", action="store_true", help="skip color correction")
    p.add_argument("--no-bg", action="store_true", help="skip background removal (input already transparent)")
    p.add_argument("--fill", type=float, default=0.85, help="fraction of canvas the object should fill (default 0.85)")
    p.add_argument("--shadow", action="store_true", help="add a grounding drop shadow")
    p.add_argument("--copyright", type=str, help="embed copyright metadata (e.g. 'Richmond General')")
    p.add_argument("--sku", type=str, help="embed SKU metadata")
    p.add_argument("--size", type=int, default=2000, help="output square side in px (0 = keep native)")
    p.add_argument("--model", choices=["nano-banana", "gemini25", "removebg", "auto"],
                   help="bg-removal model (default auto; removebg is best for clean cutouts)")
    p.add_argument("--allow-rect-mask", action="store_true",
                   help="accept a rectangular bg-removal mask instead of failing (cluttered shots)")
    p.add_argument("--straighten", action="store_true",
                   help="(not implemented — reliable auto-deskew needs opencv, absent here; shoot straight)")
    args = p.parse_args()
    if args.straighten:
        print("warning: --straighten is not implemented (needs opencv); skipping.", file=sys.stderr)
    out = standardize(args.input, args.output, do_color=not args.no_color,
                      do_bg=not args.no_bg, fill=args.fill, size=args.size, shadow=args.shadow,
                      copyright_text=args.copyright, sku=args.sku,
                      model=args.model, allow_rect_mask=args.allow_rect_mask)
    print(out)


if __name__ == "__main__":
    main()
